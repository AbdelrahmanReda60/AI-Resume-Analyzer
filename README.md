# AI Resume Analyzer

Upload a resume, let three AI agents analyze it, match it against job postings,
and get grounded career advice from a RAG-powered advisor — all running locally
with Python + FastAPI, SQLite, and a vanilla-JS frontend.

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy, SQLite, JWT auth
- **AI**: Analyzer Agent, Job Matcher Agent (5-factor weighted scoring), Career
  Advisor Agent (RAG over a ≥40-chunk knowledge base with citations)
- **Frontend**: HTML / CSS / Vanilla JavaScript — no frameworks, no CDN, no build
  step, works fully offline
- **LLM**: Google Gemini (`gemini-2.5-flash`) with a **rule-based fallback**, so
  the app still works with no API key at all

---

## 1. Setup

```bash
# 1. Create and activate a virtualenv (recommended)
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
#    then edit .env — at minimum set GEMINI_API_KEY (optional) and SECRET_KEY
```

### Environment variables (`.env`)

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GEMINI_API_KEY` | No | `""` | Enables Gemini LLM agents. If missing/invalid the app falls back to deterministic rule-based AI. |
| `SECRET_KEY` | Yes (prod) | dev placeholder | JWT signing key. **Change it before deploying.** |
| `ALGORITHM` | No | `HS256` | JWT algorithm. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `1440` | Token lifetime. |
| `DATABASE_URL` | No | `sqlite:///./data/app.db` | SQLAlchemy URL (SQLite only for this project). |
| `UPLOAD_DIR` | No | `./data/uploads` | Where uploaded resumes are stored (UUID-named). |
| `KB_DATA_DIR` | No | `./data/kb_data` | JSON knowledge-base files ingested on first run. |

Never commit `.env` or `data/*.db`.

---

## 2. Run

```bash
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Then open:

| URL | What it is |
| --- | --- |
| http://127.0.0.1:8080/ | Frontend (register → login → dashboard) |
| http://127.0.0.1:8080/docs | Interactive OpenAPI docs |
| http://127.0.0.1:8080/redoc | Reference docs |

On first startup the app creates `data/app.db`, ingests `data/kb_data/*.json`
(25 documents → 50 chunks) and seeds 20 job postings. Subsequent runs are
idempotent.

---

## 3. Test

```bash
python3 -m pytest -q                        # unit / integration
python3 scripts/e2e_journey.py              # 49-step live journey (server must be running)
# optional UI audit — needs Chrome with --remote-debugging-port=9222 and the server up:
node scripts/browser/tableprobe.mjs         # responsive dashboard table (360-1280px)
node scripts/browser/hoverprobe2.mjs        # hover must not move/clip anything
```

`tests/conftest.py` clears `GEMINI_API_KEY` before the app is imported, so the
suite runs **offline and deterministically** — every agent exercises its
rule-based fallback path. Expect `21 passed`.

Coverage includes: auth flow, unauthorized access, upload validation (bad
extension / corrupt / empty / oversized / path-traversal filename), edge-case
resumes (scanned/no-text, password-protected, corrupt structure, non-standard
headings, missing fields), ownership 404s, job CRUD + search + pagination, chat
history ordering + `resume_id` filter, KB search auth, KB ≥ 40 chunks, KB JSON
ingestion, recommendation query parameters, and improvements personalization.

---

## 4. Project structure

```
app/
├── main.py               # App wiring, request logging, seeding, static mount
├── config.py             # Settings (pydantic-settings, .env)
├── database.py           # Engine + SessionLocal
├── models/               # SQLAlchemy models (User, Resume, Analysis, Job, ...)
├── schemas/              # Pydantic request/response models
├── core/                 # security (JWT/bcrypt), exceptions, deps
├── api/                  # auth, resumes, jobs, recommendations,
│                         # improvements, chat, kb
└── services/
    ├── resume_parser.py  # Validation, sanitization, PDF/DOCX extraction
    ├── llm_client.py     # Gemini transport: timeout, retry, JSON parsing
    ├── agent_analyzer.py # Agent 1 — resume analysis (LLM + rule fallback)
    ├── agent_matcher.py  # Agent 2 — 5-factor job matching + explanations
    ├── agent_advisor.py  # Agent 3 — RAG chat with citations
    └── vector_store.py   # KB ingestion from JSON + TF-IDF retrieval
frontend/                 # Static HTML/CSS/vanilla JS (served at /)
tests/                    # pytest suite + conftest (offline, no API key)
scripts/e2e_journey.py    # 49-step end-to-end check against a live server
scripts/browser/          # Chrome-CDP UI audits (responsive table, hover layout)
samples/                  # jane_doe_resume.{pdf,txt} for demos
data/                     # app.db, uploads/, kb_data/*.json  (gitignored)
docs/                     # PLAN, API_CONTRACT, ER_DIAGRAM, PROGRESS, ...
```

---

## 5. Key behaviours

**AI without a key.** `app/services/llm_client.py` exposes `generate_json()`.
Every agent calls it first and falls back to deterministic logic when it raises
`LLMError` (no key, timeout, malformed JSON). The fallback is a first-class path,
not an error state — the UI works identically either way.

**Timeouts.** Each Gemini call has a 15 s SDK timeout plus a 20 s wall-clock
guard enforced on a daemon thread, with 1 retry.

**Retrieval before generation.** The advisor queries the knowledge base (TF-IDF
over 50 chunks) and appends `[RESOURCE: …]` / `[SKILL: …]` citations to the
reply on *every* path, including the fallback path.

**Ownership.** Resume, analysis, recommendations, improvements, and chat
endpoints return `404` when the resource belongs to another user.

**Error shape.** Every error is `{"detail": "message"}` — see
[`docs/API_CONTRACT.md`](docs/API_CONTRACT.md).

**Hardening.** Every response carries `X-Content-Type-Options: nosniff`,
`X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, and
`Cross-Origin-Opener-Policy: same-origin`. CORS is intentionally off — the
frontend is served same-origin. Request logs record method/path/status/time
only; Authorization headers, bodies, and query strings are never written.

---

## 6. Troubleshooting

| Symptom | Fix |
| --- | --- |
| Answers look generic | Set a valid `GEMINI_API_KEY` in `.env` and restart. Check the log line `LLM provider gemini-2.5-flash: enabled`. |
| `401` on API calls | Token expired (default 24 h) or you called a protected route anonymously — log in again. |
| Upload fails with `413` | File exceeds the 5 MB limit. |
| "Unable to extract text…" | The PDF is scanned/image-only or password-protected. |
| Port already in use | `--port 8081` or stop the other process. |
| Want a clean slate | Stop the server, delete `data/app.db` and `data/uploads/*`, restart. |

---

## 7. Documentation

- [`docs/PLAN.md`](docs/PLAN.md) — architecture & implementation plan
- [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) — full REST contract
- [`docs/ER_DIAGRAM.md`](docs/ER_DIAGRAM.md) — data model
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — status, known issues, task log
- [`DEMO.md`](DEMO.md) — 5-minute demo script
