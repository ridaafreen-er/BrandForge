# BrandForge
One brand idea in. Publish-ready content for every platform out.

## Run locally
Backend (Python 3.11+):
    cd backend && python -m venv .venv && source .venv/bin/activate
    pip install -r requirements.txt
    cp .env.example .env   # optional, then export the vars or use `set -a; source .env; set +a`
    uvicorn main:app --reload --port 8000 --env-file .env

Frontend (Node 18+):
    cd frontend && npm install
    cp .env.example .env.local
    npm run dev            # http://localhost:3000

Click "Try live demo" on the landing page.

## Environment variables
Backend: GROQ_API_KEY / GROQ_MODEL, GEMINI_API_KEY / GEMINI_MODEL, OPENROUTER_API_KEY / OPENROUTER_MODEL, or OPENAI_API_KEY / OPENAI_MODEL; GEMINI_API_KEY enables Gemini text-to-speech and can refine image prompts (GEMINI_IMAGE_PROMPT_MODEL); carousel images use Pollinations (optional POLLINATIONS_API_KEY / POLLINATIONS_IMAGE_MODEL); DATA_DIR (SQLite + media), CORS_ORIGINS (your frontend URL).
Frontend: NEXT_PUBLIC_API_URL (backend URL).

## Deploy
- Backend: Render/Railway/Fly using backend/Dockerfile. Mount a persistent disk at DATA_DIR. Set CORS_ORIGINS to the frontend URL.
- Frontend: Vercel, root directory `frontend`, set NEXT_PUBLIC_API_URL.

## What is real vs fallback
| Feature | With API key | Without |
|---|---|---|
| Brand kit, plan, 6 assets, critic, regenerate, rewrite buttons | LLM (Groq, Gemini, OpenRouter, or OpenAI) | Labelled demo engine: templates filled from the brand context + rule-based critic |
| Voiceover | Gemini TTS WAV, included in export | Script shown, clear "not configured" message |
| Images | Gemini-refined prompts + Pollinations-generated Instagram carousel images, included in the UI and export | Text prompts and branded placeholders |
| Video | Not implemented: storyboards are shown on branded cards | same |
| Storage | SQLite (brands double as reusable brand memory via GET /api/brands) | same |
| Export | ZIP: campaign.json, report.md, copy/*.txt, visual prompts, audio | same |

Not built: Postgres/pgvector, Redis, auth, social publishing.
