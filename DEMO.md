# 5-Minute Demo Script

A guided tour of the AI Resume Analyzer covering the full user journey:
register → login → upload → analyze → recommendations → improvements → chat →
job search → logout.

**Before you start**

```bash
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8080
```

Open **http://127.0.0.1:8080/** in a browser.
Sample resume to upload: [`samples/jane_doe_resume.pdf`](samples/jane_doe_resume.pdf)
(fallback: [`samples/jane_doe_resume.txt`](samples/jane_doe_resume.txt)).

> Tip: set `GEMINI_API_KEY` in `.env` for real LLM answers. Leave it empty to
> demo the deterministic fallback — every screen still works, and the log shows
> `LLM provider gemini-2.5-flash: DISABLED (rule-based fallback active)`.

---

## 0:00 — First impression (30 s)

- Land on the home page: hero, value props, sticky navbar with **Log in /
  Register**, footer link to `/docs`.
- Show `http://127.0.0.1:8080/docs` — the live OpenAPI spec for all 19 endpoints.

## 0:30 — Register & login (30 s)

1. **Register** with any valid email + password ≥ 8 chars.
   - Demonstrate validation: submit an invalid email and a short password —
     inline field errors appear, no page reload.
   - Demonstrate the duplicate-account path: register the same email twice →
     `400 An account with this email address already exists.` surfaced as a toast.
2. **Login**. Wrong password → `401 Invalid email or password.` shown inline.
3. Navbar now shows your name in a dropdown menu (My Resumes / Jobs / Logout).

## 1:00 — Upload a resume (40 s)

1. **Upload Resume** → drop `samples/jane_doe_resume.pdf` onto the dropzone
   (or click the zone to open the file picker; it is keyboard-focusable).
2. Watch the parsing happen: extracted name, contact, skills.
3. Show the validation paths (optional):
   - `../../etc/passwd.pdf` → accepted but sanitized (directory stripped)
   - a `.txt` file → `400 Invalid file format…`
   - a file > 5 MB → `413 File size exceeds maximum limit of 5MB.`

## 1:40 — AI analysis (40 s)

1. On the dashboard, note the three stat cards — total resumes, analyzed, and
   **Average Match Score**.
2. Open the resume → **Analyze**. The Analyzer Agent returns:
   skills (technical + soft), experience summary, education, strengths/gaps.
3. `POST /api/resumes/{id}/analyze` in `/docs` returns the same payload.

## 2:20 — Job recommendations (60 s)

1. Open **Recommendations** for the resume.
2. The Job Matcher scores every job on **five weighted factors**:
   `0.40 technical skills · 0.10 soft skills · 0.25 experience ·
   0.10 education · 0.15 semantic similarity`.
3. Point out per-job: `match_score`, `match_grade`, matched/missing skills,
   `experience_fit`, `education_fit`, and the plain-language `explanation`.
4. Filter with `?min_score=85` — only high-confidence matches remain.
   `?explain=false` skips the LLM pass and returns instantly (used by the
   dashboard's average-score card).

## 3:20 — Improvements & skill gaps (40 s)

1. Open **Resume Improvements**: readiness score, key strengths, weaknesses.
2. **Missing High-Demand Skills** shows how many jobs require each gap.
3. Recommended certifications and learning resources come from the knowledge
   base; **Actionable Resume Edits** gives rewordable bullets.

## 4:00 — Career Advisor chat (50 s)

1. Ask: *"What Kubernetes projects should I build?"*
2. Highlight three things in the reply:
   - **Retrieval happened first** — 50 chunks are in `data/kb_data/*.json`,
     retrieved by TF-IDF before generation.
   - **Citations are appended**: `Sources: [RESOURCE: Kubernetes Deep Dive
     Course], [SKILL: Containerization with Docker & Kubernetes]` — present on
     every path, including the fallback.
   - **History is fed back** — send a follow-up ("And what certification do you
     recommend?") and it answers in context.
3. `GET /api/chat/history?limit=1` returns only the *most recent* message;
   `?resume_id=` scopes history to one resume.

## 4:50 — Jobs & logout (10 s)

1. **Jobs** page: 20 seeded postings, filters for title, skill, location, job
   type, and experience level, plus `limit`/`offset` pagination.
2. Create → edit → delete a job posting.
3. **Logout** → `POST /api/auth/logout` is called, session cleared, redirected
   to the home page.

---

## Quick API walkthrough (optional, 2 min)

```bash
# Register
TOKEN=$(curl -s -X POST localhost:8080/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@example.com","password":"Password123!","full_name":"Demo"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')

# Upload + analyze
curl -s -X POST localhost:8080/api/resumes/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F file=@samples/jane_doe_resume.pdf
# → note the "id", then:
#   POST /api/resumes/<id>/analyze
#   GET  /api/resumes/<id>/recommendations?min_score=80
#   GET  /api/resumes/<id>/improvements
#   POST /api/chat  {"resume_id": <id>, "message": "What am I missing?"}
```

## Talking points

- **Three agents**: Analyzer (parse + extract), Job Matcher (5-factor scoring +
  explanations), career Advisor (RAG + citations).
- **Graceful AI**: no key → no crash. Timeouts (15 s SDK / 20 s hard) and a
  retry guarantee the UI never hangs.
- **Security**: JWT bearer auth, ownership checks returning `404`, filename
  sanitization, file size limits, HTML escaping of every rendered value.
- **Offline by design**: no CDN, no npm, no framework — plain files served by
  FastAPI.
