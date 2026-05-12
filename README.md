# Automated AI Video Cutter

Produktionsreifes End-to-End System fuer automatischen Videoschnitt auf Basis von Sprache:

- Frontend (React + Vite): Upload, Sprachwahl, Prompt, Fortschritt, Download
- Backend (FastAPI): Upload API, Job-Tracking, Whisper-Transkription, LLM-Bewertung, ffmpeg-Schnitt
- GPU-Beschleunigung: faster-whisper (CUDA), LM Studio (qwen3.5:9b auf GPU), ffmpeg NVENC

## Projektstruktur

```text
ai-video-cutter/
├── backend/
│   └── app/
│       ├── config.py
│       ├── job_store.py
│       ├── logging_config.py
│       ├── main.py
│       ├── schemas.py
│       └── services/
│           ├── ffmpeg_service.py
│           ├── llm_service.py
│           ├── pipeline_service.py
│           └── whisper_service.py
├── frontend/                  # Platzhalter fuer separates Frontend-Deployment
├── logs/
├── models/
├── outputs/
├── uploads/
├── venv/
├── src/                       # Aktives React-Frontend in diesem Repository
├── .env.example
├── requirements.txt
├── run.sh
└── README.md
```

## Systemanforderungen

- Debian 12 (Bookworm)
- Root-Zugriff
- NVIDIA RTX 3060 12GB
- Python 3.11
- Node.js 20+
- ffmpeg mit `h264_nvenc`
- LM Studio mit `qwen/qwen3.5-9b`

## 1) NVIDIA Treiber Installation (Debian 12)

Als root:

```bash
apt update
apt install -y linux-headers-$(uname -r) build-essential dkms
apt install -y nvidia-driver firmware-misc-nonfree
reboot
```

Nach Reboot pruefen:

```bash
nvidia-smi
```

## 2) CUDA Toolkit Installation

NVIDIA CUDA Repository (Debian 12) einrichten:

```bash
apt install -y wget gnupg ca-certificates
wget https://developer.download.nvidia.com/compute/cuda/repos/debian12/x86_64/cuda-keyring_1.1-1_all.deb
dpkg -i cuda-keyring_1.1-1_all.deb
apt update
apt install -y cuda-toolkit-12-6
```

Environment global setzen (`/etc/profile.d/cuda.sh`):

```bash
cat >/etc/profile.d/cuda.sh <<'EOF'
export PATH=/usr/local/cuda/bin:$PATH
export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
EOF
chmod +x /etc/profile.d/cuda.sh
source /etc/profile.d/cuda.sh
```

## 3) cuDNN Installation

cuDNN ueber NVIDIA Repo installieren:

```bash
apt update
apt install -y libcudnn9 libcudnn9-dev
```

## 4) CUDA Verifikation

```bash
nvidia-smi
python3 -c "import torch; print('cuda:', torch.cuda.is_available()); print('device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')"
```

Erwartet: `cuda: True`.

## 5) ffmpeg mit NVENC

Installieren:

```bash
apt install -y ffmpeg
```

Pruefen:

```bash
ffmpeg -hide_banner -encoders | grep nvenc
```

Erwartet: `h264_nvenc` sichtbar.

## 6) Python 3.11 + venv Setup

```bash
apt install -y python3.11 python3.11-venv python3-pip
cd /opt
git clone <DEIN-REPO-URL> ai-video-cutter
cd ai-video-cutter
python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

## 7) Node.js + Frontend Setup

```bash
apt install -y curl
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
npm install
```

## 8) Environment konfigurieren

```bash
cp .env.example .env
```

Wichtige Variablen in `.env`:

- `LMSTUDIO_BASE_URL=http://127.0.0.1:1234/v1`
- `LMSTUDIO_MODEL=qwen/qwen3.5-9b`
- `WHISPER_MODEL=large-v3`
- `WHISPER_DEVICE=auto`
- `VITE_API_BASE_URL=http://SERVER-IP:8000`

## 9) LM Studio Setup (GPU)

1. LM Studio fuer Linux herunterladen und starten.
2. Modell `qwen/qwen3.5-9b` laden.
3. In LM Studio:
   - Local Server aktivieren
   - OpenAI-kompatiblen Endpoint aktivieren (Standard `http://127.0.0.1:1234/v1`)
   - GPU Offload aktivieren
4. Test:

```bash
curl http://127.0.0.1:1234/v1/models
```

## 10) Starten

Entwicklung (Backend + Frontend gleichzeitig):

```bash
chmod +x run.sh
./run.sh
```

Direkter Einzelstart:

```bash
source venv/bin/activate
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

In zweiter Shell:

```bash
npm run dev -- --host 0.0.0.0 --port 5173
```

Zugriff:

- Frontend: `http://SERVER-IP:5173`
- API: `http://SERVER-IP:8000/api/health`

## API Ablauf

1. `POST /api/jobs`
   - Multipart: `file`, `language` (`de`/`en`), `user_prompt` (optional)
2. `GET /api/jobs/{job_id}`
   - Status, Fortschritt, Download-Link
3. `GET /api/jobs/{job_id}/download`
   - Finales Video

## Verarbeitungspipeline

1. Upload in `uploads/`
2. Falls kein MP4: Konvertierung zu MP4 via ffmpeg
3. Transkription mit faster-whisper (`large-v3`, CUDA wenn verfuegbar)
4. LM Studio Bewertung der Segmente mit robustem JSON-Prompt
5. ffmpeg Schnitt anhand Zeitstempel
   - Erst `-c copy`
   - Fallback Re-Encode (`h264_nvenc`, sonst `libx264`)
6. Ausgabe in `outputs/`
7. Logs in `logs/backend.log`

Wichtig fuer den ersten Lauf:

- `large-v3` wird beim ersten Job erst von Hugging Face geladen (mehrere GB).
- In dieser Zeit bleibt der Job laenger in "Preparing Whisper model".
- Das ist normal und kein Deadlock.

## Prompting Logik

- Wenn leer: `Cut only the highlights.`
- Wenn gesetzt: Nutzerprompt wird direkt als Task verwendet
- LLM muss gueltiges JSON liefern:

```json
[
  {"start": 12.34, "end": 18.92, "text": "..."}
]
```

## Testanleitung

1. `GET /api/health` aufrufen
2. Testvideo im Frontend hochladen
3. Sprache waehlen (`Deutsch` oder `English`)
4. Optional Prompt setzen
5. Fortschritt beobachten
6. Ergebnis herunterladen

Zusatztest via curl:

```bash
curl -X POST "http://127.0.0.1:8000/api/jobs" \
  -F "file=@/path/to/video.mp4" \
  -F "language=de" \
  -F "user_prompt=Cut all pauses and keep key insights."
```

## Troubleshooting GPU

- Job bleibt lange bei Whisper-Start
  - Beim ersten Lauf wird das Modell heruntergeladen.
  - Download-Fortschritt pruefen:
  - `watch -n 2 'du -sh models || true'`
  - `tail -f logs/backend.log`
  - Optional HF Token setzen fuer bessere Rate Limits:
  - `export HF_TOKEN=<dein_token>`
  - Danach Backend neu starten.
- LM Studio Modellname passt nicht
  - Verfuegbare IDs pruefen: `curl http://127.0.0.1:1234/v1/models`
  - Exakte ID in `.env` bei `LMSTUDIO_MODEL` setzen (z.B. `qwen/qwen3.5-9b`).

- `torch.cuda.is_available() == False`
  - Treiber/CUDA/cuDNN nicht korrekt installiert
  - `LD_LIBRARY_PATH` nicht gesetzt
- `ffmpeg` ohne `h264_nvenc`
  - ffmpeg Build ohne NVENC, anderes Build verwenden
- LM Studio langsam/CPU
  - GPU Offload in LM Studio aktivieren
  - kleineres Kontextfenster oder Quantisierung pruefen
- Whisper laeuft auf CPU
  - `WHISPER_DEVICE=auto` oder `cuda`
  - `nvidia-smi` pruefen

## Produktionshinweise

- Reverse Proxy (Nginx) vor FastAPI/Uvicorn setzen
- HTTPS terminieren
- Upload-Groessenlimits auf Proxy und App setzen
- Logrotation ist aktiviert (`RotatingFileHandler`)
- Outputs/Uploads regelmaessig bereinigen (Retention-Job)
- Fuer hohe Last: Job Queue (Celery/RQ) + Redis ergaenzen
