# AI Resume Analyzer — Implementation Progress

> Updated: 2026-09-30 (completion session)
> Source of Truth: `docs/PLAN.md`, `docs/API_CONTRACT.md`, `docs/ER_DIAGRAM.md`, `docs/FRONTEND_BRIEF.md`

---

## 0. How to resume this project

```bash
pip install -r requirements.txt
cp .env.example .env                      # GEMINI_API_KEY optional
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8080   # http://127.0.0.1:8080/
python3 -m pytest -q                      # expect 21 passed
```

**Last verified:** server boots (`/` 200, `/docs` 200), **21/21 pytest pass**,
**49/49 end-to-end journey steps pass** (register → … → logout against the live
server), 20 jobs seeded, 50 KB chunks ingested from `data/kb_data/*.json`,
13 frontend pages + all JS/CSS return 200.

> ⚠️ Shell trap: **never** run `pkill -f "uvicorn app.main:app"` — the pattern
> matches the calling shell's own command line and kills it (this cost two
> stuck sessions). Kill by port instead:
> `kill $(ss -ltnp 'sport = :8080' | grep -oP 'pid=\K[0-9]+')`

---

## 1. Status Table

### Backend

| Component | File(s) | Status | Notes |
|---|---|---|---|
| App wiring / static mount | `app/main.py` | Complete | 19 API routes, 3 exception handlers, **hardening headers** (`nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`, COOP), **API request logging (method/path/status/ms only — no headers, bodies, query strings)**, startup log + `SECRET_KEY` default warning, static `/` |
| Config | `app/config.py` | Complete | pydantic-settings + `.env`; `GEMINI_API_KEY` optional |
| DB session | `app/database.py` | Complete | |
| bcrypt + JWT | `app/core/security.py` | Complete | |
| Error handlers `{"detail"}` | `app/core/exceptions.py` | Complete | uniform shape, logged |
| ORM models (7 + KB) | `app/models/*` | Complete | |
| Pydantic schemas | `app/schemas/*` | Complete | |
| Auth API | `app/api/auth.py` | Complete | register/login/logout/me, duplicate-email 400, bad login 401 |
| Ownership deps | `app/api/deps.py` | Complete | |
| Resume API | `app/api/resumes.py` | Complete | ownership 404 on all 5 routes |
| Resume parser | `app/services/resume_parser.py` | Complete | ext + magic bytes + 5 MB (413) + **sanitized filename** + **cleanup on failure** + correct 5-tuple annotation + **password-protected detection** + friendly pdfminer error mapping |
| LLM transport | `app/services/llm_client.py` | Complete | **NEW** — 15 s SDK timeout, 20 s wall-clock on a daemon thread, 2 attempts, `generate_json()`/`extract_json()`, `llm_available()` |
| Analyzer agent | `app/services/agent_analyzer.py` | Complete | LLM JSON with retry → rule-based fallback |
| Matcher agent | `app/services/agent_matcher.py` | Complete | 5-factor weights, **real education fit** (`degree_rank`), **batched LLM explanation** with deterministic fallback |
| Recommendations API | `app/api/recommendations.py` | Complete | score → filter → sort desc → enrich visible → persist; `min_score=0`, `limit`, `explain` |
| Improvements API | `app/api/improvements.py` | Complete | **rewritten** — every field derives from the analysis + real job-posting demand; deterministic 0–100 score |
| Advisor agent | `app/services/agent_advisor.py` | Complete | RAG **before** generation, `history` + `job_context` in prompt, **citations on every path**, LLM JSON + fallback |
| Chat API | `app/api/chat.py` | Complete | stable `_session_key()`, history loaded before save, 404 on foreign `resume_id`, `GET` takes `limit` (most recent) + `resume_id` filter |
| RAG service | `app/services/rag_service.py` | Complete | top-K + context + citations |
| Vector store | `app/services/vector_store.py` | Complete | **ingests `data/kb_data/*.json` on first run** (embedded fallback), sorted by score, threshold `> 0.05`, pads with next-best |
| Job CRUD + search | `app/api/jobs.py` | Complete | CRUD + 7 query params + 20 seeds + pagination bounds. *PUT/DELETE are auth-only by design (see §2.5)* |
| KB search API | `app/api/kb.py` | Complete | **auth required** (matches contract) |

### Frontend

| Page / Module | Status | Notes |
|---|---|---|
| `css/style.css` | Complete | `--primary-50` hex fixed, sticky moved to `#navbar-container`, `.sr-only` added, contrast fixes (badge/step/score/toast), `.nav-user-*`, `.nav-mobile-auth`, `.btn-block`, **responsive resumes table (`#resumes-table-container` stacks to labelled cards ≤700px)** |
| `js/ui.js` | Complete | navbar user menu (`aria-expanded`, Esc/outside click), **modal focus trap**, `safeExternalUrl()`, `parseIdParam()`, dead `privacy.html` link → `/docs` |
| `js/api.js` | Complete | network-error toast, safe JSON parse, surfaces `detail` on 401, single `showToast` owner |
| `js/auth.js` | Complete | inline validation + `aria-live`, submit spinners, `logoutUser()` → `POST /api/auth/logout` |
| `js/config.js`, `js/mock.js` | Placeholder | dead code, unused (harmless) |
| `js/resumes.js` | Complete | XSS via `?id=` fixed (`parseIdParam`), numeric ids in href/onclick, 3rd stat = avg match score, `resumes-error` vs empty state, dropzone keyboard/click, row cells carry `class="resume-cell"` + `data-label` for the ≤700px stacked layout |
| `js/jobs.js` | Complete | `escapeHtml(Number(score))`, `parseIdParam`, `jobs-error`, experience-level filter, numeric ids, `job_id` deep-link → advisor |
| `js/chat.js` | Complete | `data-query` chips (no inline handlers), `currentJobId` + `job_id` sent, history `?resume_id=` only when deep-linked, follow-ups via `dataset` |
| `js/improvements.js` | Complete | `safeExternalUrl()` + `escapeHtml` on hrefs, numeric id, **renders `actionable_bullet_improvements`** |
| `index.html` | Complete | |
| `login.html` / `register.html` | Complete | inline validation + `aria-live` |
| `dashboard.html` | Complete | Average Match Score stat, `resumes-error` |
| `upload-resume.html` | Complete | dropzone `tabindex/role/aria-label`, click-to-select |
| `resume-analysis.html` | Complete | duplicate `style` merged |
| `job-recommendations.html` | Complete | |
| `jobs.html`, `job-form.html` | Complete | `experience_level` filter, `add-job-btn` gated on auth, `jobs-error` |
| `career-advisor.html` | Complete | input label/`aria-label`, `data-query` chips |
| `resume-improvements.html` | Complete | duplicate `style` merged, **Actionable Resume Edits** card added |

### Tests / Docs

| Item | Status | Notes |
|---|---|---|
| `tests/test_app.py` | Complete | **21 tests, all passing** |
| `tests/conftest.py` | Complete | clears `GEMINI_API_KEY` → offline, deterministic |
| `scripts/e2e_journey.py` | Complete | 49-step live-server journey (`python3 scripts/e2e_journey.py [base_url]`) |
| `scripts/browser/*.mjs` | Complete | Chrome-CDP responsive + hover audit (`tableprobe.mjs`, `hoverprobe2.mjs`); opens its own tab so runs are parallel-safe |
| `requirements.txt`, `pytest.ini` | Complete | |
| `docs/PLAN.md` | Complete | **44/44 checkboxes done** (all 7 phases); §3.1/§3.3 "as built" note |
| `docs/API_CONTRACT.md` | Complete | §2.1 upload response/errors, §4.1 `min_score`/`limit`/`explain`/ordering reconciled |
| `docs/ER_DIAGRAM.md` | Complete | `embedding_blob` now NULLABLE + documented as unused |
| `README.md` | Complete | setup, env table, run, test, structure, troubleshooting |
| `DEMO.md` | Complete | 5-min script + API walkthrough + talking points |
| `samples/jane_doe_resume.{pdf,txt}` | Complete | demo upload file (extractable text) |

---

## 2. What was fixed (mapped to the original bug list)

### 2.1 Security / correctness — all resolved

1. ✅ DOM XSS `?id=` → `parseIdParam()` (digits only) in `resumes.js`, `jobs.js`, `chat.js`, `improvements.js`.
2. ✅ Attribute XSS `href` → `safeExternalUrl()` + `escapeHtml()` in `improvements.js`.
3. ✅ Inline `onclick` string → `data-query` chip listeners in `chat.js`; remaining `on*` handlers only interpolate `Number(id)`.
4. ✅ Path traversal → `sanitize_filename()` strips directories/danger chars.
5. ⚠️ Jobs PUT/DELETE have **no ownership check** — deliberate: requirements only mandate ownership on resume/analysis/chat. Contract documents auth-only. Change if required.
6. ✅ `/api/kb/search` now requires auth.

### 2.2 Broken UX — all resolved

7–8. ✅ `detail` surfaced on 401 + inline validation + `aria-live`.
9. ✅ Sticky navbar moved to `#navbar-container` (`.header-nav` is `position: relative`).
10. ✅ `--primary-50: #eep2ff` → `#eef2ff`.
11. ✅ Dashboard 3rd stat = average match score (`?min_score=0&limit=1&explain=false`).
12. ✅ Dropzone click/keyboard → file picker.
13. ✅ `resumes-error` / `jobs-error` distinct from empty state.
14. ✅ `privacy.html` → `/docs` (`rel="noopener"`).
15. ✅ Duplicate `style` attributes merged.
16. ✅ `logoutUser()` → `POST /api/auth/logout`.
17. ✅ Contrast fixes (`.badge-warning #92400e`, `.step` neutral-500, `.score-green/amber/red`, `.toast-success`).
+ ✅ Modal focus trap / Esc / backdrop, mobile auth menu, `.sr-only`.
+ ✅ Dashboard resumes table no longer scrolls sideways on phones: below 700px each row
  stacks into a card and `td::before` prints the column label (`TITLE` / `FORMAT` /
  `UPLOAD DATE` / `STATUS` / `ACTIONS`). Verified `document.scrollWidth === clientWidth`
  at 360/375/414/600/700/768/1280 (was `spillX = 252` at 375px).
+ ✅ Hover audit (reported "hover clips bottom content"): **no defect found** — all 11
  `:hover` rules only change color/background/border-color/box-shadow, no mouse-hover JS
  handlers exist, and CDP `CSS.forcePseudoState` on `.card`/`.card-title`/`.card-header`/
  `.btn` over dashboard, jobs, job-recommendations, resume-analysis × 375/768/1280
  produced **zero** geometry/computed-style diffs (screenshots byte-identical).

### 2.3 Backend logic — all resolved

18. ✅ History returns the **most recent** `limit` messages, chronological within the window.
19. ✅ Stable `_session_key(user, resume, job)`; history loaded before saving and passed as `history=`.
20. ✅ Foreign `resume_id` → **404** (chat + every resume sub-resource).
21. ✅ Files removed on any extraction/validation failure (`_remove_quietly`).
22. ✅ Retrieval sorted by score desc, threshold `> 0.05`, padded with next-best (never arbitrary rows).
23. ✅ Real education fit via `degree_rank()` / `candidate_degree_rank()`.
24. ✅ `llm_client.generate_text()` — 15 s SDK + 20 s wall-clock (daemon thread) + 1 retry; used by all three agents.
25. ✅ Return annotation corrected to a 5-tuple.
26. ✅ `data/kb_data/*.json` created (4 files, 25 docs → 50 chunks) and ingested on first run; embedded `KB_SEED_DATA` kept as fallback.
27. ✅ Logging configured; API middleware logs method/path/status/duration only.

### 2.4 Missing features — delivered

28. ✅ LLM match explanations (single batched call per request).
29. ✅ Citations on the Gemini path **and** every fallback.
30. ⚠️ `sentence-transformers` intentionally **not** added (heavyweight, breaks offline/lightweight goals). TF-IDF keyword-overlap fallback is explicitly permitted by `PLAN.md §3.3` and is now documented in §3.1/§3.3 notes.
31. ✅ Improvements personalization — weaknesses, strengths, skill gaps (real `appears_in_job_matches`), certifications, resources, bullets, and score all derived from the analysis + jobs table.
32. ✅ `README.md`, `DEMO.md`, `samples/`.

### 2.5 API contract mismatches — all reconciled in `docs/API_CONTRACT.md`

| Was | Now |
|---|---|
| upload response had `filename` | removed; added `has_analysis`, `user_id`; full error list documented |
| `min_score` default 50 | default **0**, documented, plus `limit` and `explain` |
| `chat/history?resume_id=` missing | documented (`limit`, `resume_id`, field names, ordering) |
| `/api/kb/search` auth | documented as required |
| jobs PUT/DELETE ownership | documented as **auth-only, any authenticated user** |

---

## 3. Test coverage (21 tests)

`tests/conftest.py` clears `GEMINI_API_KEY` before import → the whole suite runs
**offline and deterministically**, exercising every agent's fallback path.

| Test | Covers |
|---|---|
| `test_auth_flow` | register, duplicate 400, short password 422, login, bad login 401, `/me`, logout |
| `test_unauthorized_access` | 401 on 5 protected routes |
| `test_resume_upload_and_validation` | bad ext / corrupt / empty / pdf / docx / list / get / analyze / recommendations / improvements / delete |
| `test_resume_ownership_protection` | 404 for foreign get/analyze/delete |
| `test_job_crud_and_search` | search, filters, create/get/update/delete |
| `test_career_advisor_chat` | reply, follow-ups, history, clear |
| `test_kb_search` | 401 without token, results with token |
| `test_oversized_file_rejected` | **413 > 5 MB** |
| `test_upload_filename_sanitized_and_text_returned` | **traversal filename stripped**, `parsed_text_snippet`, `file_type` |
| `test_foreign_resources_return_404` | **7 foreign endpoints** → 404; owner still 200 |
| `test_jobs_pagination` | non-overlapping pages, totals, `limit`/`offset` bounds → 422 |
| `test_chat_history_order_and_resume_filter` | `limit=1` = most recent, chronological, `resume_id` filter incl. empty |
| `test_knowledge_base_has_at_least_40_chunks` | ≥ 40 |
| `test_knowledge_base_ingested_from_json_files` | `data/kb_data/*.json` is the source of truth |
| `test_recommendations_min_score_and_explain_params` | filtering, ordering, `explain=false`, 422 bounds |
| `test_improvements_are_personalized_from_analysis` | derived gaps/counts, https links, deterministic score |
| `test_scanned_pdf_without_extractable_text` | image-only PDF → 400 + no orphan file |
| `test_password_protected_pdf_rejected_with_clear_message` | `/Encrypt` → 400 with actionable message |
| `test_corrupt_pdf_structure_rejected` | passes magic bytes, fails parsing → 400 |
| `test_non_standard_headings_still_parse` | unconventional headings still analyzed |
| `test_sparse_resume_with_missing_fields_is_graceful` | missing skills/education/metrics → every downstream agent still 200 |

---

## 4. Final audit (Phase 7) — results

| Check | Result |
|---|---|
| SQL injection (raw `text()` / `execute` / f-string SQL) | none |
| `eval` / `exec` / `pickle` / `os.system` / `subprocess` | none |
| Hardcoded API keys or passwords in source | none |
| `GEMINI_API_KEY` printed or logged | never (only "configured/not configured") |
| DOM XSS: URL params → `innerHTML` | all routed through `parseIdParam()` (digits only) |
| DOM XSS: server data → `innerHTML` | `escapeHtml()` / `renderMarkdown()` (escapes first) / `innerText` |
| Attribute injection: `href` / `onclick` values | `safeExternalUrl()` + `Number(id)` coercion |
| Path traversal on upload | `sanitize_filename()` strips directories |
| Password hashing | bcrypt, 72-byte truncation |
| JWT | `exp` enforced, `algorithms=[...]` pinned, 401 on any failure |
| Security headers | `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: same-origin`, COOP |
| Secrets in git | `.env` never committed; `README.md` + `PROGRESS.md` warn |
| CORS | not enabled — frontend is served same-origin by FastAPI (correct) |

## 5. Remaining / deliberate open items

1. **Jobs PUT/DELETE ownership** — auth-only by decision (§2.5). Add
   `job.user_id` + a dependency if the spec changes.
2. **`sentence-transformers`** — not installed; TF-IDF fallback documented as
   the chosen option (`PLAN.md §3.3`).
3. **Rate limiting** — not implemented; not required by the spec and would risk
   breaking the automated tests. Worth adding (`slowapi`) for a real deploy.
4. **`js/config.js` / `js/mock.js`** — dead placeholders, unused by any page.
5. **Improvements scores are deterministic** — no LLM pass. Intentional: keeps
   the page instant and testable; an `explain=true`-style LLM enrichment could
   be added later following `recommendations.py`.
6. **No git repo initialized.** If version control is wanted: `git init`,
   add a `.gitignore` covering `.env`, `data/*.db`, `data/uploads/`,
   `__pycache__/`, `.pytest_cache/`, `.venv/`, then commit.
7. **Job-card descriptions are truncated on purpose** — `jobs.js` uses
   `-webkit-line-clamp: 2` (2 lines + ellipsis). Element scans report this as
   `overflow: hidden`; it is a preview, not a bug. Do not "fix" it.
8. **Hover audit closed as no-defect** — see §2.2. `.card` is `height: auto;
   overflow: visible` (neither property is set at all), `.card-hover:hover`
   changes only `box-shadow` + `border-color`, so no hover rule can shift or
   clip layout.

---

## 6. Verification checklist (run before submitting)

```bash
python3 -m pytest -q                 # 21 passed
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8080
#   /            -> 200  + nosniff / X-Frame-Options: DENY / Referrer-Policy
#   /docs        -> 200
#   13 HTML pages -> 200 (privacy.html intentionally 404)
python3 scripts/e2e_journey.py       # 49/49 steps
for f in frontend/js/*.js; do node --check "$f"; done   # all parse
grep -rn "GEMINI_API_KEY" app/ frontend/ tests/         # never logged/printed
# Responsive + hover audit (needs Chrome --remote-debugging-port=9222, server on :8080)
node scripts/browser/tableprobe.mjs   # dashboard rows stack <=700px, table spillX=0
                                      # at 360-1280, doc scrollWidth==clientWidth,
                                      # hover diffs NONE  -> "ALL CHECKS PASSED"
node scripts/browser/hoverprobe2.mjs  # dashboard/jobs/recommendations/analysis
                                      # x 375/768/1280 -> hover diffs NONE on all 12
```
