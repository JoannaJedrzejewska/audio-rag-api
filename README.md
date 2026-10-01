# Audio RAG API

REST API do transkrypcji nagrań audio i semantycznego przeszukiwania treści z użyciem podejścia Retrieval-Augmented Generation (RAG).

> **Dane źródłowe:** konferencje prasowe Europejskiego Banku Centralnego (EBC/ECB).  
> Po każdym posiedzeniu Rady Prezesów prezes EBC przedstawia decyzje dotyczące polityki pieniężnej i perspektyw gospodarczych. Aplikacja pobiera publicznie dostępne nagrania, transkrybuje je przez faster-Whisper, zapisuje embeddingi fragmentów tekstu w ChromaDB i udostępnia wyszukiwanie semantyczne oraz odpowiedzi RAG.

Nagrania EBC są dostępne na [SoundCloud EBC](https://soundcloud.com/europeancentralbank).

## Architektura

```text
Klient
  │
  ▼
FastAPI
  ├── faster-Whisper ── transkrypcja audio
  ├── sentence-transformers ── embeddingi tekstu
  ├── ChromaDB ── przechowywanie fragmentów i wyszukiwanie wektorowe
  └── Gemini / OpenAI / local LLM ── generowanie odpowiedzi RAG
```

## Stack

| Komponent | Technologia |
|---|---|
| API | FastAPI 0.115.12 + Pydantic v2 |
| Transkrypcja | faster-whisper 1.1.1, domyślny model `small` |
| Embeddingi | sentence-transformers 3.4.1 + `paraphrase-multilingual-MiniLM-L12-v2` |
| Baza wektorowa | ChromaDB 0.6.3 |
| LLM | Gemini, OpenAI lub provider lokalny |
| Konteneryzacja | Docker Compose |
| Orkiestracja | Kubernetes / Minikube |

## Endpointy

| Metoda | Endpoint | Opis |
|---|---|---|
| `GET` | `/health` | Status API, ChromaDB, Whisper i embeddingów |
| `POST` | `/audio/transcribe` | Upload pliku audio i utworzenie zadania transkrypcji |
| `GET` | `/audio/jobs/{job_id}` | Status i wynik zadania transkrypcji |
| `POST` | `/rag/search` | Wyszukiwanie semantyczne w transkrypcjach |
| `POST` | `/rag/answer` | Odpowiedź RAG wygenerowana przez LLM |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/openapi.json` | Specyfikacja OpenAPI |

> Endpoint `/` nie jest zdefiniowany. `GET /` zwraca `404 Not Found`; użyj `/docs` albo `/health`.

## Konfiguracja

### Plik `.env`

Utwórz lokalną konfigurację:

```bash
test -f .env || cp .env.example .env
```

Przykładowy `.env`:

```dotenv
CHROMADB_HOST=127.0.0.1
CHROMADB_PORT=8001
CHROMA_COLLECTION=transcriptions

WHISPER_MODEL=small
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2

LLM_PROVIDER=gemini
GEMINI_API_KEY=twoj_klucz_api
OPENAI_API_KEY=

MAX_FILE_SIZE_MB=350
PORT=8000
```

Nie commituj `.env` i nie publikuj kluczy API. `.gitignore` powinien zawierać:

```gitignore
.env
.env.*
!.env.example
```

### Zmienne środowiskowe

| Zmienna | Domyślna | Opis |
|---|---:|---|
| `CHROMADB_HOST` | `localhost` | `127.0.0.1` dla API uruchamianego na hoście; `chromadb` dla API uruchamianego w Docker Compose |
| `CHROMADB_PORT` | `8001` | `8001` z hosta; `8000` przy komunikacji między kontenerami |
| `CHROMA_COLLECTION` | `transcriptions` | Nazwa kolekcji ChromaDB |
| `WHISPER_MODEL` | `small` | `tiny`, `base`, `small`, `medium`, `large` |
| `EMBEDDING_MODEL` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | Model embeddingów |
| `LLM_PROVIDER` | `gemini` | `gemini`, `openai` lub `local` |
| `GEMINI_API_KEY` | — | Klucz Gemini używany przez `/rag/answer` |
| `OPENAI_API_KEY` | — | Klucz OpenAI używany przez `/rag/answer` |
| `MAX_FILE_SIZE_MB` | `25` | Maksymalny rozmiar pliku audio w MB |
| `PORT` | `8000` | Port FastAPI |

Dla konferencji EBC ustaw `MAX_FILE_SIZE_MB=350` lub większą wartość, jeśli największe pliki tego wymagają.

## GitHub Codespaces

### Dlaczego osobny wariant?

W GitHub Codespaces Docker Compose może nie rozwiązywać `huggingface.co` wewnątrz kontenera API. Modele Whisper i Sentence Transformers są pobierane z Hugging Face, dlatego zalecana konfiguracja Codespaces uruchamia:

```text
ChromaDB: Docker, 127.0.0.1:8001
FastAPI: host Codespace / Python virtual environment, 127.0.0.1:8000
```

Dzięki temu API używa działającego DNS hosta Codespace, a ChromaDB zachowuje trwałe dane w wolumenie Docker.

### Terminal 1 — ChromaDB

```bash
cd /workspaces/audio-rag-api

docker compose up -d chromadb

docker compose ps

curl -s http://127.0.0.1:8001/api/v2/heartbeat
```

### Terminal 2 — środowisko Python i API

```bash
cd /workspaces/audio-rag-api

python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel

python -m pip install \
  --timeout 120 \
  --retries 10 \
  -r requirements.txt
```

Jeżeli instalacja PyTorch kończy się błędem dotyczącym niedostępnej wersji `torch==2.7.1+cpu`, zmień w `requirements.txt`:

```text
torch==2.7.1+cpu
```

na wersję dostępną w aktualnym indeksie PyTorch, np.:

```text
torch==2.9.1+cpu
```

Następnie ponów instalację:

```bash
python -m pip install \
  --timeout 120 \
  --retries 10 \
  -r requirements.txt
```

Sprawdź instalację:

```bash
python - <<'PY'
import torch
import chromadb
from faster_whisper import WhisperModel
from sentence_transformers import SentenceTransformer

print("torch:", torch.__version__)
print("chromadb:", chromadb.__version__)
print("CUDA available:", torch.cuda.is_available())
print("Imports: OK")
PY
```

Uruchom API:

```bash
export CHROMADB_HOST=127.0.0.1
export CHROMADB_PORT=8001
export MAX_FILE_SIZE_MB=350

uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Przy pierwszym uruchomieniu pobierane są modele Whisper i Sentence Transformers. API jest gotowe po komunikatach:

```text
API gotowe.
Application startup complete.
Uvicorn running on http://127.0.0.1:8000
```

Nie zamykaj terminala z Uvicornem podczas uploadu albo trwającej transkrypcji.

### Terminal 3 — health check

```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```

Przykładowa odpowiedź:

```json
{
  "status": "ok",
  "version": "1.0.0",
  "components": {
    "api": "ok",
    "chromadb": "ok (0 dokumentow)",
    "whisper": "loaded",
    "embeddings": "loaded",
    "llm": "gemini"
  }
}
```

`ok (0 dokumentow)` oznacza, że ChromaDB działa, ale nie zawiera jeszcze danych.

### Swagger UI

Lokalnie:

```text
http://127.0.0.1:8000/docs
```

W Codespaces otwórz zakładkę **Ports**, znajdź port `8000`, wybierz **Open in Browser**, a następnie użyj ścieżki:

```text
/docs
```

## Lokalnie bez Docker Compose

Ten wariant uruchamia ChromaDB w Dockerze, a API na hoście.

### Terminal 1 — ChromaDB

```bash
docker run --rm -it \
  --name audio-rag-chromadb \
  -p 8001:8000 \
  -v chroma_data:/chroma/chroma \
  -e IS_PERSISTENT=TRUE \
  -e ANONYMIZED_TELEMETRY=FALSE \
  chromadb/chroma:0.6.3
```

### Terminal 2 — API

```bash
python -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

export CHROMADB_HOST=127.0.0.1
export CHROMADB_PORT=8001
export MAX_FILE_SIZE_MB=350

uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Otwórz:

```text
http://127.0.0.1:8000/docs
```

## Standardowy Docker Compose

Na lokalnym komputerze z poprawnym Docker DNS można uruchomić zarówno API, jak i ChromaDB w kontenerach.

API musi wtedy łączyć się z ChromaDB przez wewnętrzną nazwę usługi:

```yaml
environment:
  CHROMADB_HOST: chromadb
  CHROMADB_PORT: "8000"
```

Uruchomienie:

```bash
docker compose up -d --build
docker compose ps

curl -s http://127.0.0.1:8000/health | python -m json.tool
```

W kontenerze API nie używaj `localhost`, `127.0.0.1` ani `host.docker.internal` do połączenia z ChromaDB. Te adresy nie wskazują kontenera `chromadb`.

## Dane EBC

### Pobieranie nagrań

Skrypt używa `yt-dlp` i wymaga `ffmpeg` na hoście:

```bash
python -m pip install yt-dlp

sudo apt-get update
sudo apt-get install -y ffmpeg
```

Na macOS:

```bash
brew install ffmpeg
python -m pip install yt-dlp
```

Podgląd plików bez pobierania:

```bash
python scripts/download_ecb_soundcloud.py --dry-run
```

Pobranie konferencji do `sample_data/`:

```bash
python scripts/download_ecb_soundcloud.py --output sample_data/
```

### Uwaga o dużych plikach

WAV konferencji EBC są duże. W Codespaces nie pobieraj pełnego archiwum i nie indeksuj wszystkich plików naraz, jeśli dysk jest ograniczony.

Bezpieczny workflow:

```text
pobierz lub skopiuj 1 plik
→ zaindeksuj
→ zweryfikuj wynik
→ usuń źródłowy WAV
→ przejdź do kolejnego pliku
```

## Indeksowanie audio

ChromaDB nie indeksuje automatycznie plików z `sample_data/`. Każdy plik przechodzi przez pipeline:

```text
WAV
→ POST /audio/transcribe
→ faster-Whisper
→ transkrypcja
→ dzielenie tekstu na fragmenty
→ embeddingi
→ ChromaDB
```

### Lista dostępnych plików

```bash
find sample_data -type f \
  \( -iname '*.wav' -o -iname '*.mp3' -o -iname '*.m4a' -o -iname '*.mp4' \) \
  -print | head -20
```

### Test jednego pliku

```bash
python scripts/upload_to_api.py \
  --input sample_data/ \
  --ext wav \
  --limit 1 \
  --api http://127.0.0.1:8000 \
  --results upload_results_test.json
```

Skrypt przesyła plik do `POST /audio/transcribe`, czeka na status zadania i zapisuje wyniki do JSON.

### Ręczny upload

```bash
curl -s -X POST http://127.0.0.1:8000/audio/transcribe \
  -F "file=@sample_data/NAZWA_PLIKU.wav" \
  | python -m json.tool
```

Przykładowa odpowiedź:

```json
{
  "job_id": "801f954a-aeab-4188-bf62-b0f744c6818d",
  "status": "queued",
  "message": "Zadanie transkrypcji zostało przyjęte."
}
```

Sprawdzanie statusu:

```bash
curl -s \
  http://127.0.0.1:8000/audio/jobs/TWOJ_JOB_ID \
  | python -m json.tool
```

Możesz również odpytywać status automatycznie:

```bash
JOB_ID="TU_WSTAW_JOB_ID"

while true; do
  curl -s "http://127.0.0.1:8000/audio/jobs/$JOB_ID" | python -m json.tool
  sleep 15
done
```

### Potwierdzenie indeksacji

Po statusie `completed` sprawdź ChromaDB:

```bash
curl -s http://127.0.0.1:8000/health | python -m json.tool
```

Liczba dokumentów w komponencie `chromadb` powinna być większa niż zero.

### Wyszukiwanie semantyczne

Endpoint `/rag/search` wymaga metody `POST`. Otworzenie ścieżki w przeglądarce wykonuje `GET` i zwróci `405 Method Not Allowed`.

```bash
curl -s -X POST http://127.0.0.1:8000/rag/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What was the ECB monetary policy decision in April 2025?",
    "top_k": 3
  }' | python -m json.tool
```

Przed pierwszą indeksacją poprawną odpowiedzią jest:

```json
{
  "query": "What was the ECB monetary policy decision in April 2025?",
  "results": [],
  "total_found": 0
}
```

To oznacza pustą kolekcję ChromaDB, nie awarię bazy.

### Odpowiedź RAG

Po zaindeksowaniu co najmniej jednego nagrania:

```bash
curl -s -X POST http://127.0.0.1:8000/rag/answer \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What was the ECB monetary policy decision in April 2025?",
    "top_k": 3
  }' | python -m json.tool
```

Endpoint wymaga poprawnie skonfigurowanego `LLM_PROVIDER` oraz właściwego klucza Gemini albo OpenAI.

### Usuwanie przetworzonych WAV

Po potwierdzeniu, że job ma status `completed`, ChromaDB zawiera dokumenty, a `/rag/search` zwraca wyniki, usuń źródłowy plik WAV, aby odzyskać miejsce:

```bash
rm "sample_data/NAZWA_PRZETWORZONEGO_PLIKU.wav"
```

Transkrypcja i embeddingi pozostają zapisane w ChromaDB.

## Zarządzanie miejscem na dysku

Modele ML, obrazy Docker, cache buildów, dane ChromaDB i WAV mogą szybko zapełnić dysk, szczególnie w Codespaces.

### Diagnoza

```bash
df -h
docker system df
docker system df --verbose

du -sh sample_data 2>/dev/null
du -sh ~/.cache/huggingface ~/.cache/ctranslate2 2>/dev/null || true
```

Największe pliki w `sample_data/`:

```bash
du -ah sample_data | sort -hr | head -30
```

### Bezpieczne czyszczenie Docker

Najpierw zatrzymaj usługi Docker:

```bash
docker compose down
```

Usuń nieużywane kontenery, sieci i cache buildów:

```bash
docker system prune -f
docker builder prune -af
```

Sprawdź odzyskane miejsce:

```bash
docker system df
df -h
```

### Tymczasowe przeniesienie WAV

Jeżeli `/tmp` ma więcej wolnego miejsca niż `/workspaces`, możesz tymczasowo przenieść pobrane pliki WAV:

```bash
mkdir -p /tmp/ecb_audio_backup
mv sample_data/*.wav /tmp/ecb_audio_backup/
```

Przywrócenie pojedynczego pliku do indeksacji:

```bash
cp "/tmp/ecb_audio_backup/NAZWA_PLIKU.wav" sample_data/
```

`/tmp` jest magazynem tymczasowym. Jego zawartość może zostać usunięta po restarcie lub przebudowie Codespace.

### Operacje destrukcyjne

Poniższe polecenia mogą skasować dane ChromaDB, obrazy Docker lub cache modeli:

```bash
docker compose down -v
docker volume prune
docker system prune -a --volumes
docker image prune -a -f
```

Używaj ich tylko wtedy, gdy świadomie chcesz usunąć indeks lub zacząć od zera.

## Testy

```bash
pip install -r requirements-test.txt

pytest
pytest tests/ -v
pytest tests/test_audio.py -v
pytest --cov=app --cov-report=html
```

## Kubernetes / Minikube

### Wymagania

- [Minikube](https://minikube.sigs.k8s.io/) >= 1.32
- [kubectl](https://kubernetes.io/docs/tasks/tools/) >= 1.28
- Docker

### Uruchomienie klastra

```bash
minikube start --memory=16384 --cpus=4 --driver=docker
```

Manifest API uruchamia dwie repliki. Każda ładuje model Whisper i model embeddingów, dlatego dla klastra z tymi ustawieniami przeznacz około 16 GB RAM. Przy mniejszej ilości pamięci ustaw `replicas`, `minReplicas` i `maxReplicas` na `1` odpowiednio w `k8s/api/deployment.yaml` i `k8s/api/hpa.yaml`.

### Zbuduj obraz w Minikube

```bash
minikube image build -t audio-rag-api:latest .
```

### Skonfiguruj sekret

Manifest API wymaga sekretu Kubernetes `audio-rag-secret`. Dla domyślnego `LLM_PROVIDER=gemini` utwórz go z kluczem Gemini. Polecenie poprosi o klucz bez wyświetlania go w terminalu i można je bezpiecznie uruchomić ponownie:

```bash
read -rsp "Klucz Gemini: " GEMINI_API_KEY
printf '\n'
kubectl create secret generic audio-rag-secret \
  --namespace audio-rag \
  --from-literal=GEMINI_API_KEY="$GEMINI_API_KEY" \
  --dry-run=client -o yaml | kubectl apply -f -
unset GEMINI_API_KEY
```

W środowisku produkcyjnym użyj zewnętrznego menedżera sekretów.

### Zastosuj manifesty

Najpierw utwórz namespace, a następnie włącz dodatki potrzebne przez HPA i Ingress:

```bash
kubectl apply -f k8s/namespace.yaml
minikube addons enable metrics-server
minikube addons enable ingress
```

Utwórz sekret zgodnie z poprzednią sekcją, a następnie zastosuj pozostałe manifesty:

```bash
kubectl apply -f k8s/chromadb/pvc.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/chromadb/deployment.yaml
kubectl apply -f k8s/chromadb/service.yaml
kubectl apply -f k8s/api/deployment.yaml
kubectl apply -f k8s/api/service.yaml
kubectl apply -f k8s/api/hpa.yaml
kubectl apply -f k8s/ingress.yaml
```

Jeśli nagrania przekraczają domyślny limit 25 MB, zwiększ `MAX_FILE_SIZE_MB` w `k8s/configmap.yaml` oraz `nginx.ingress.kubernetes.io/proxy-body-size` w `k8s/ingress.yaml`. Dla plików do 350 MB ustaw odpowiednio `350` i `350m`.

### Sprawdź wdrożenie

```bash
kubectl rollout status deployment/chromadb -n audio-rag --timeout=10m
kubectl rollout status deployment/audio-rag-api -n audio-rag --timeout=20m
kubectl get pods -n audio-rag
kubectl get svc -n audio-rag
kubectl get hpa -n audio-rag
```

Pierwsze uruchomienie API pobiera modele, więc może potrwać. W razie problemów sprawdź logi poda API:

```bash
kubectl logs -n audio-rag deployment/audio-rag-api
```

### Dostęp do API

Port forward:

```bash
kubectl port-forward -n audio-rag svc/audio-rag-api-service 8000:80
```

API będzie dostępne pod:

```text
http://127.0.0.1:8000/docs
```

NodePort:

```bash
minikube service audio-rag-api-service -n audio-rag --url
```

Do adresu zwróconego przez polecenie dopisz `/docs`.

Ingress (wymaga włączonego dodatku ingress):

```bash
echo "$(minikube ip) audio-rag.local" | sudo tee -a /etc/hosts
```

Otwórz Swagger UI pod adresem:

```text
http://audio-rag.local/docs
```

### Zatrzymanie i usunięcie klastra

Zatrzymanie Minikube zachowuje klaster i dane ChromaDB:

```bash
minikube stop
```

Poniższe polecenia usuwają namespace, a następnie cały klaster wraz z danymi ChromaDB:

```bash
kubectl delete namespace audio-rag
minikube delete
```

## Struktura projektu

```text
audio-rag-api/
├── app/
│   ├── main.py
│   ├── core/
│   │   └── config.py
│   ├── routers/
│   │   ├── audio.py
│   │   └── rag.py
│   ├── schemas/
│   │   └── models.py
│   └── services/
│       ├── transcription.py
│       ├── embeddings.py
│       ├── vector_store.py
│       └── llm.py
├── k8s/
│   ├── api/
│   ├── chromadb/
│   ├── configmap.yaml
│   ├── ingress.yaml
│   └── namespace.yaml
├── scripts/
│   ├── download_ecb_soundcloud.py
│   └── upload_to_api.py
├── sample_data/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-test.txt
├── .env.example
└── README.md
```
