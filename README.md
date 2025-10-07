# Codex Cards

Minimal Flask + Socket.IO app to run a shared card-drawing session for 6–10 players. All clients see the same deck and draws in real time.

## Prerequisites
- Python 3.10+
- Recommended: virtualenv

## Setup

```bash
cd /home/paul/codexCards
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Convert cards (one-off)
We now prefer JSON. Convert your TSV once:
```bash
python scripts/tsv_to_json.py
```
This writes `materials/cards.json`. The server will load JSON if present, otherwise it falls back to TSV.

## Run

```bash
python app.py
```
Then open `http://localhost:5000`.

- Health check: `http://localhost:5000/healthz`
- Download rules: `http://localhost:5000/instructions`

## How it works
- Backend: Flask + Flask-SocketIO (eventlet) serves a single shared game state in memory.
- Data: `materials/cards.json` (preferred) or `materials/cards.tsv` is loaded at startup. The deck is shuffled; each Draw reveals the next card.
- Frontend: `static/index.html` connects via Socket.IO and renders the drawn cards.

## Deploy notes
- For small groups (6–10), a single eventlet worker is fine. For more users, consider a message queue (Redis) + multiple workers.
- Use a reverse proxy (nginx/Caddy) if exposing to the internet.

## Customization
- Card fields: `Category1`, `Category2`, `Name`, `Text`, `ShortText`, `URL` (optional).
- Adjust styling/layout in `static/index.html`.

## Safety
- State is in-memory only. Restarting the server resets the deck.
