# Codex Cards (labcards)

Minimal Flask + Socket.IO app to run a shared card-drawing session.

## Local run
```bash
cd /home/paul/codexCards/labcards
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Open `http://localhost:5000`.

## Data
- Preferred: `materials/cards.json`
- Fallback: `materials/cards.tsv`
- Rules: `materials/instructions.docx`

## Render deployment
1) Commit and push this folder to GitHub (repo root can be `labcards/` or the repo itself).
2) On Render → New → Web Service → Connect your repo.
3) Set:
   - Environment: `Python 3`
   - Build Command: `pip install -r labcards/requirements.txt` (or `requirements.txt` if repo root is `labcards/`)
   - Start Command: `cd labcards && gunicorn -k eventlet -w 1 -b 0.0.0.0:$PORT app:app`
4) Ensure `materials/` is in the repo (JSON/TSV and instructions).
5) Deploy. The app should listen on the Render URL.

Notes:
- We use Gunicorn + eventlet for WebSocket support.
- One worker (`-w 1`) is fine for small groups. Scale up with a Redis message queue if needed.

## Features
- Draw exactly one random card from each suit in order: TOUCHSTONE → WORKSHOP → TOOL → PROTOCOL → PLATFORM.
- Reset to start a fresh 5-card sequence.
