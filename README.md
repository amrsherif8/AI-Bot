# Funke Project

FastAPI app: math solver, translator, document Q&A, text-to-speech, YouTube audio.
AI features use the Google Gemini API.

## Run locally
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env        # then put your GEMINI_API_KEY inside
uvicorn main:app --reload
```
Get a key at https://aistudio.google.com (never commit it; `.env` is git-ignored).

## Push to GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

## Deploy on Render
1. New > Web Service > connect the GitHub repo.
2. Runtime: Python 3. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Environment variables: `GEMINI_API_KEY` = your key (optional: `GEMINI_MODEL`).

## Notes
- The local voice robot (`botAI.py`, microphone + speakers) only works on your own machine. On Render it is disabled automatically.
- YouTube download may be blocked from cloud IPs.
