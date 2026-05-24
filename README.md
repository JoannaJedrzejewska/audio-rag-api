# Audio RAG API

REST API do transkrypcji nagrań audio i semantycznego przeszukiwania treści z użyciem podejścia RAG.

> **Dane źródłowe:** Konferencje prasowe Europejskiego Banku Centralnego (EBC/ECB).
> Po każdym posiedzeniu Rady Prezesów prezes EBC wygłasza konferencję prasową,
> na której ogłaszane są decyzje dotyczące stóp procentowych i perspektyw polityki pieniężnej.
> Nagrania dostępne są publicznie na [SoundCloud EBC](https://soundcloud.com/europeancentralbank).
> Aplikacja transkrybuje te nagrania (faster-Whisper ASR), indeksuje semantycznie (ChromaDB)
> i umożliwia zadawanie pytań do zgromadzonej bazy wiedzy (RAG + LLM).

## Architektura

```
[Klient]
   │
   v
[FastAPI]  ──► [faster-Whisper ASR]   → transkrypcja
   │
   v
[ChromaDB] ──► [sentence-transformers] → embeddingi
   │
   v
[LLM Generator] (Gemini / OpenAI)  → odpowiedź RAG
```

## Stack

| Komponent      | Technologia                              |
|----------------|------------------------------------------|
| API            | FastAPI 0.111 + Pydantic v2              |
| Transkrypcja   | faster-whisper 1.0.3 (model: small)      |
| Embeddingi     | paraphrase-multilingual-MiniLM-L12-v2    |
| Baza wektorowa | ChromaDB (osobny kontener/pod)           |
| LLM            | Google Gemini 1.5 Flash / GPT-3.5        |
| Orkiestracja   | Kubernetes (Minikube lokalnie)           |

## Endpointy

| Metoda | Endpoint               | Opis                           |
|--------|------------------------|--------------------------------|
| GET    | `/health`              | Status aplikacji i komponentów |
| POST   | `/audio/transcribe`    | Upload pliku audio             |
| GET    | `/audio/jobs/{job_id}` | Status zadania transkrypcji    |
| POST   | `/rag/search`          | Wyszukiwanie semantyczne       |
| POST   | `/rag/answer`          | Pytanie RAG z odpowiedzią LLM  |

---

## Dane — konferencje prasowe EBC

### Źródło

EBC publikuje nagrania każdej konferencji prasowej na SoundCloud:
`https://soundcloud.com/europeancentralbank`

Skrypt automatycznie pobiera wszystkie dostępne konferencje prasowe i pomija
inne materiały (podcasty, wywiady, przemówienia).

### Pobieranie danych (SoundCloud)

```bash
# Wymagania
pip install yt-dlp
sudo apt-get install -y ffmpeg   # Ubuntu/Codespaces
# brew install ffmpeg            # macOS

# Podgląd — co zostanie pobrane (bez pobierania)
python scripts/download_ecb_soundcloud.py --dry-run

# Pobierz wszystkie konferencje prasowe jako WAV
python scripts/download_ecb_soundcloud.py --output sample_data/
```

### Własne pliki z Google Drive

Jeśli masz nagrania zapisane na Google Drive (inne konto):

```bash
# 1. Zainstaluj rclone
curl https://rclone.org/install.sh | sudo bash

# 2. Skonfiguruj dostęp (jednorazowo)
rclone config
# n → gdrive2 → drive → autoryzuj przez przeglądarkę

# 3. Zsynchronizuj nagrania
rclone copy "gdrive2:Folder z filmami EBC" data/ecb_videos/ --progress

# 4. Uploaduj do API
python scripts/upload_to_api.py --input data/ecb_videos/ --ext mp4
```

### Masowy upload do API

```bash
# Upload wszystkich pobranych plików WAV
python scripts/upload_to_api.py --input sample_data/ --ext wav

# Tylko kilka plików (test)
python scripts/upload_to_api.py --input sample_data/ --ext wav --limit 5
```

Skrypt czeka na zakończenie każdej transkrypcji i zapisuje wyniki do `upload_results.json`.

---

## Uruchomienie lokalne (docker-compose)

```bash
# 1. Skopiuj i uzupełnij konfigurację
cp .env.example .env
# Ustaw GEMINI_API_KEY lub OPENAI_API_KEY

# 2. Uruchom (pierwsze uruchomienie ~5-10 min — pobiera modele)
docker compose up --build

# 3. Sprawdź
curl http://localhost:8000/health
```

---

## Uruchomienie na Minikube

### Wymagania
- [Minikube](https://minikube.sigs.k8s.io/) >= 1.32
- [kubectl](https://kubernetes.io/docs/tasks/tools/) >= 1.28
- Docker

### Krok 1 — Uruchom Minikube

```bash
minikube start --memory=8192 --cpus=4 --driver=docker
```

> faster-whisper (model small) potrzebuje ~2 GB RAM. Minimum 6 GB dla całego klastra.

### Krok 2 — Zbuduj obraz w Minikube

```bash
eval $(minikube docker-env)
docker build -t audio-rag-api:latest .
```

### Krok 3 — Uzupełnij Secret

```bash
# Zakoduj klucz API w base64
echo -n "twoj-klucz-gemini" | base64
# Wstaw wynik do k8s/secret.yaml w polu GEMINI_API_KEY
# NIGDY nie commituj pliku z prawdziwymi kluczami!
```

### Krok 4 — Zaaplikuj manifesty

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/chromadb/pvc.yaml
kubectl apply -f k8s/chromadb/deployment.yaml
kubectl apply -f k8s/chromadb/service.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/api/deployment.yaml
kubectl apply -f k8s/api/service.yaml
kubectl apply -f k8s/api/hpa.yaml
minikube addons enable ingress
kubectl apply -f k8s/ingress.yaml
```

### Krok 5 — Sprawdź stan podów

```bash
# Poczekaj aż STATUS = Running
kubectl get pods -n audio-rag -w

kubectl get svc -n audio-rag
kubectl describe pod -n audio-rag <nazwa-poda>   # diagnostyka
```

### Krok 6 — Dostęp do API

**Opcja A — port-forward (najszybsza)**
```bash
kubectl port-forward -n audio-rag svc/audio-rag-api-service 8000:80
# API dostępne na http://localhost:8000
```

**Opcja B — NodePort**
```bash
minikube service audio-rag-api-service -n audio-rag --url
```

**Opcja C — Ingress**
```bash
echo "$(minikube ip)  audio-rag.local" | sudo tee -a /etc/hosts
# API dostępne na http://audio-rag.local
```

### Zatrzymanie klastra

```bash
minikube stop
kubectl delete namespace audio-rag   # usuwa wszystkie zasoby
minikube delete                       # usuwa klaster
```

---

## Zmienne środowiskowe

| Zmienna              | Domyślna                                | Opis                          |
|----------------------|-----------------------------------------|-------------------------------|
| `CHROMADB_HOST`      | `localhost`                             | Adres ChromaDB                |
| `CHROMADB_PORT`      | `8001`                                  | Port ChromaDB                 |
| `CHROMA_COLLECTION`  | `transcriptions`                        | Nazwa kolekcji                |
| `WHISPER_MODEL`      | `small`                                 | tiny / base / small / medium  |
| `EMBEDDING_MODEL`    | `paraphrase-multilingual-MiniLM-L12-v2` | Model embeddingów             |
| `LLM_PROVIDER`       | `gemini`                                | `gemini` / `openai` / `local` |
| `GEMINI_API_KEY`     | —                                       | Klucz API Gemini              |
| `OPENAI_API_KEY`     | —                                       | Klucz API OpenAI              |
| `MAX_FILE_SIZE_MB`   | `25`                                    | Maks. rozmiar pliku audio     |

---

## Przykłady użycia

```bash
# Upload audio
curl -X POST http://localhost:8000/audio/transcribe \
  -F "file=@sample_data/sample_00.wav"

# Sprawdź status transkrypcji
curl http://localhost:8000/audio/jobs/<job_id>

# Wyszukiwanie semantyczne
curl -X POST http://localhost:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{"query": "deposit facility rate", "top_k": 5}'

# Pytanie RAG
curl -X POST http://localhost:8000/rag/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "What was the ECB interest rate decision in March 2024?", "top_k": 3}'
```

---

## Testy

```bash
pip install -r requirements-test.txt
pytest                              # wszystkie testy
pytest --cov=app --cov-report=html  # z pokryciem kodu
pytest tests/test_audio.py -v       # tylko audio
```

---

## Struktura projektu

```
audio-rag-api/
├── app/
│   ├── main.py
│   ├── core/config.py
│   ├── schemas/models.py
│   ├── routers/
│   │   ├── audio.py
│   │   └── rag.py
│   └── services/
│       ├── transcription.py
│       ├── embeddings.py
│       ├── vector_store.py
│       └── llm.py
├── k8s/
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── ingress.yaml
│   ├── chromadb/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── pvc.yaml
│   └── api/
│       ├── deployment.yaml
│       ├── service.yaml
│       └── hpa.yaml
├── scripts/
│   ├── download_ecb_soundcloud.py   ← pobieranie konferencji EBC
│   └── upload_to_api.py             ← masowy upload do API
├── sample_data/
│   └── README.md
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```
## Przykłady użycia

### Upload i transkrypcja

```bash
curl -X POST http://localhost:8000/audio/transcribe \
  -F "file=@sample_data/conference.wav"
```

**Odpowiedź:**
```json
{
  "job_id": "801f954a-aeab-4188-bf62-b0f744c6818d",
  "status": "queued",
  "message": "Zadanie transkrypcji zostało przyjęte."
}
```

### Sprawdzenie statusu

```bash
curl http://localhost:8000/audio/jobs/801f954a-aeab-4188-bf62-b0f744c6818d
```

**Odpowiedź po zakończeniu:**
```json
{
  "job_id": "801f954a-aeab-4188-bf62-b0f744c6818d",
  "status": "completed",
  "filename": "conference.wav",
  "excerpt": "You're listening to the ECB podcast..."
}
```

### Pytanie RAG

```bash
curl -X POST http://localhost:8000/rag/answer \
  -H "Content-Type: application/json" \
  -d '{"question": "What was the ECB interest rate decision in June 2025?", "top_k": 3}'
```
## Development

### Uruchomienie testów

```bash
pip install -r requirements-test.txt
pytest tests/ -v
pytest tests/ --cov=app --cov-report=html
```

### Zmienne środowiskowe (lokalne)

```bash
cp .env.example .env
# Uzupełnij GEMINI_API_KEY lub OPENAI_API_KEY
```
### Uwagi
- `MAX_FILE_SIZE_MB` ustaw na min. 200 dla plików EBC (domyślne nagrania to 100–300 MB)
- Transkrypcja na CPU zajmuje ok. 15–40 min na plik — rozważ model `tiny` do testów