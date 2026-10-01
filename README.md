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
[FastAPI]  ──> [faster-Whisper ASR]   - transkrypcja
   │
   v
[ChromaDB] ──> [sentence-transformers] - embeddingi
   │
   v
[LLM Generator] (Gemini / OpenAI)  - odpowiedź RAG
```

## Stack

| Komponent      | Technologia                              |
|----------------|------------------------------------------|
| API            | FastAPI 0.111 + Pydantic v2              |
| Transkrypcja   | faster-whisper 1.0.3 (model: small)      |
| Embeddingi     | paraphrase-multilingual-MiniLM-L12-v2    |
| Baza wektorowa | ChromaDB (osobny kontener/pod)           |
| LLM            | Google Gemini 3.8 Flash / GPT-3.5        |
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
Poniższe zależności są potrzebne tylko do pobierania nagrań na komputerze, nie do
uruchomienia API w Dockerze. Kontener API instaluje `ffmpeg` podczas budowania obrazu.

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
## Uruchomienie lokalne z Docker Compose

### Wymagania

- Docker Desktop lub Docker Engine z Docker Compose
- Minimum 8 GB RAM; dla `WHISPER_MODEL=small` zalecane jest więcej
- Wolne miejsce na dysku dla modeli, obrazów Docker, ChromaDB i plików audio
- Opcjonalnie klucz Gemini lub OpenAI do endpointu `/rag/answer`

### 1. Przygotuj konfigurację

```bash
cp .env.example .env
```

Edytuj lokalny plik `.env`:

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=twoj_klucz_api
MAX_FILE_SIZE_MB=350
WHISPER_MODEL=small
```

Nie commituj `.env`.

### 2. Uruchom API i ChromaDB

```bash
docker compose up -d --build
```

Przy pierwszym uruchomieniu obraz API pobiera modele Whisper i Sentence Transformers.
Może to potrwać kilka minut.

Podgląd logów:

```bash
docker compose logs -f api chromadb
```

API jest gotowe, gdy log zawiera:

```text
API gotowe.
Application startup complete.
```

### 3. Sprawdź status

```bash
docker compose ps

curl -s http://127.0.0.1:8000/health | python -m json.tool
```

Przykładowy wynik:

```json
{
  "status": "ok",
  "components": {
    "api": "ok",
    "chromadb": "ok (0 dokumentow)",
    "whisper": "loaded",
    "embeddings": "loaded",
    "llm": "gemini"
  }
}
```

`ok (0 dokumentow)` oznacza, że ChromaDB działa, lecz nie zawiera jeszcze
zaindeksowanych transkrypcji.

### 4. Otwórz dokumentację API

```text
http://127.0.0.1:8000/docs
```

Endpoint `/` nie jest zdefiniowany, dlatego `GET /` zwraca `404 Not Found`.

### 5. Zatrzymanie

```bash
docker compose down
```

To zatrzymuje kontenery, ale zachowuje named volume `chroma_data`.

> Nie uruchamiaj `docker compose down -v`, jeśli chcesz zachować indeks ChromaDB.

## Indeksowanie audio

ChromaDB nie indeksuje plików z `sample_data/` automatycznie. Dane są dodawane po:

```text
audio upload
→ faster-Whisper
→ transkrypcja
→ chunking
→ embeddingi
→ ChromaDB
```

### Test na jednym pliku

```bash
python scripts/upload_to_api.py \
  --input sample_data/ \
  --ext wav \
  --limit 1 \
  --api http://127.0.0.1:8000 \
  --results upload_results_test.json
```

Po zakończeniu sprawdź indeks:

```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```

Liczba dokumentów w `components.chromadb` powinna być większa niż `0`.

### Upload małej partii

```bash
python scripts/upload_to_api.py \
  --input sample_data/ \
  --ext wav \
  --limit 3 \
  --api http://127.0.0.1:8000 \
  --results upload_results_batch_01.json
```

### Upload wszystkich plików

Po udanym teście:

```bash
python scripts/upload_to_api.py \
  --input sample_data/ \
  --ext wav \
  --api http://127.0.0.1:8000 \
  --results upload_results.json
```

Skrypt wysyła pliki sekwencyjnie i zapisuje wyniki po każdym pliku.

## Zarządzanie miejscem na dysku

Przed większym importem sprawdź wykorzystanie dysku:

```bash
df -h
docker system df
docker system df --verbose
du -sh sample_data 2>/dev/null
```

Bezpieczne czyszczenie nieużywanego cache Docker:

```bash
docker compose down
docker system prune -f
docker builder prune -af
```

Aby całkowicie wyczyścić Docker i zacząć od zera:

```bash
docker system prune -a --volumes -f
```

> To polecenie usuwa również niewykorzystywane wolumeny, w tym potencjalnie dane
> ChromaDB. Uruchamiaj je tylko, jeśli świadomie chcesz skasować lokalny indeks.

### Masowy upload do API

```bash
# Upload wszystkich pobranych plików WAV
python scripts/upload_to_api.py --input sample_data/ --ext wav

# Tylko kilka plików (test)
python scripts/upload_to_api.py --input sample_data/ --ext wav --limit 5
```

Skrypt czeka na zakończenie każdej transkrypcji i zapisuje wyniki do `upload_results.json`.

---
### Lokalnie bez Dockera
```bash 
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

docker run --rm -it \
  --name audio-rag-chromadb \
  -p 8001:8000 \
  -v chroma_data:/chroma/chroma \
  chromadb/chroma:0.6.3

source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
# a w przeglądarce otwórz:

http://localhost:8000/docs

```
## Uruchomienie lokalne (docker-compose)

```bash
# 1. Przygotuj konfigurację
test -f .env || cp .env.example .env
# W pliku .env ustaw:
# LLM_PROVIDER=gemini
# GEMINI_API_KEY=<klucz z Google AI Studio>

# 2. Zbuduj obraz i uruchom API oraz ChromaDB
# Upewnij się, że działa Docker Desktop lub daemon Dockera
docker info
docker ps
docker compose up --build

# 3. W drugim terminalu sprawdź status
docker compose ps
curl http://localhost:8000/health
```

Otwórz `http://localhost:8000/docs`, aby korzystać z API. Przy pierwszym starcie
API pobiera modele Whisper i embeddingów; może to potrwać kilka minut. Klucz Gemini
jest potrzebny do `/rag/answer`, nie do samego uruchomienia kontenerów.
W Codespaces API używa domyślnego bridge Dockera, ponieważ DNS sieci Compose może
nie rozwiązywać `huggingface.co`. API łączy się z ChromaDB przez
`host.docker.internal:8001`. `DOCKER_DNS_SERVER` wskazuje DNS hosta; poza Azure
ustaw w `.env` resolver używany przez hosta.

Logi sprawdzisz poleceniem `docker compose logs -f api chromadb`. Zatrzymanie:
`docker compose down` (dane ChromaDB pozostają w wolumenie). 

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
│   ├── download_ecb_soundcloud.py   - pobieranie konferencji EBC
│   └── upload_to_api.py             - masowy upload do API
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

### Dla modelu lokalnego
W pliku .env ustaw:

LLM_PROVIDER=local
LOCAL_LLM_HOST=http://localhost:11434
LOCAL_LLM_MODEL=llama3.2:1b
Następnie uruchom lokalny serwer modelu, np. przez Ollama.

``` bash
# Instalacja Ollama
curl -fsSL https://ollama.com/install.sh | sh

ollama --version

ollama serve
```
Pozostaw pierwszy terminal otwarty. Ollama powinna działać pod adresem:
http://localhost:11434
W drugim terminalu pobierz model i sprawdź jego działanie:

```bash
ollama pull llama3.2:1b

ollama run llama3.2:1b "Reply only: OK"

curl http://localhost:11434

ollama list
```
