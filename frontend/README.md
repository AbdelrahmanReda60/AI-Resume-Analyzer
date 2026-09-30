# AI Resume Analyzer - Frontend

Vanilla HTML5, CSS3, and JavaScript frontend for the AI Resume Analyzer project.

## Quick Start

### Mock Mode (No Backend Required)

1. Open `frontend/js/config.js`
2. Set `USE_MOCK = true`
3. Open `frontend/index.html` in a browser

### Real Mode (With Backend)

1. Start the FastAPI backend (from project root):
   ```bash
   uvicorn app.main:app --reload
   ```
2. Open `http://localhost:8000`

### Static Server (Mock Mode)

From the `frontend/` directory:
```bash
python -m http.server 8080
```
Then open `http://localhost:8080`

## Pages

| Page | File | Description |
|------|------|-------------|
| Landing | `index.html` | Public showcase with features and CTA |
| Register | `register.html` | New user account creation |
| Login | `login.html` | Existing user authentication |
| Dashboard | `dashboard.html` | Resume list, quick actions, user greeting |
| Upload Resume | `upload-resume.html` | Drag & drop PDF/DOCX upload with auto-analysis |
| Resume Analysis | `resume-analysis.html` | AI-parsed resume breakdown (skills, experience, education) |
| Job Recommendations | `job-recommendations.html` | Match scores (0-100) with skill breakdown |
| Browse Jobs | `jobs.html` | Job search with filters and pagination |
| Job Form | `job-form.html` | Add/edit job postings |
| Career Advisor | `career-advisor.html` | AI chat interface with suggestions |
| Resume Improvements | `resume-improvements.html` | Weaknesses, gaps, certifications, and learning resources |

## Architecture

```
frontend/
├── css/style.css              # Design system with CSS variables
├── js/
│   ├── config.js              # USE_MOCK flag and API_BASE_URL
│   ├── mock.js                # Sample JSON responses for all endpoints
│   ├── api.js                 # apiFetch() wrapper with JWT, errors, toasts
│   ├── auth.js                # Route guard and session management
│   ├── ui.js                  # Navbar, footer, toasts, spinners, escapeHtml
│   ├── resumes.js             # Resume management handlers (placeholder)
│   ├── jobs.js                # Job management handlers (placeholder)
│   ├── chat.js                # Chat interface handlers (placeholder)
│   └── improvements.js        # Improvements handlers (placeholder)
├── index.html
├── register.html
├── login.html
├── dashboard.html
├── upload-resume.html
├── resume-analysis.html
├── job-recommendations.html
├── jobs.html
├── job-form.html
├── career-advisor.html
├── resume-improvements.html
└── README.md
```

## API Endpoints Consumed

| Endpoint | Method | Page |
|----------|--------|------|
| `/api/auth/register` | POST | register.html |
| `/api/auth/login` | POST | login.html |
| `/api/auth/logout` | POST | All (logout button) |
| `/api/auth/me` | GET | Dashboard greeting |
| `/api/resumes` | GET | dashboard.html |
| `/api/resumes/upload` | POST | upload-resume.html |
| `/api/resumes/{id}` | GET | resume-analysis.html |
| `/api/resumes/{id}` | DELETE | dashboard.html |
| `/api/resumes/{id}/analyze` | POST | upload-resume.html |
| `/api/resumes/{id}/analysis` | GET | resume-analysis.html |
| `/api/resumes/{id}/recommendations` | GET | job-recommendations.html |
| `/api/resumes/{id}/improvements` | GET | resume-improvements.html |
| `/api/jobs` | GET | jobs.html |
| `/api/jobs` | POST | job-form.html |
| `/api/jobs/{id}` | GET | job-form.html |
| `/api/jobs/{id}` | PUT | job-form.html |
| `/api/jobs/{id}` | DELETE | job-form.html |
| `/api/chat` | POST | career-advisor.html |
| `/api/chat/history` | GET | career-advisor.html |
| `/api/chat/history` | DELETE | career-advisor.html |

## Contract Questions

### Assumptions Made

1. **Pagination**: Jobs list uses `limit`/`offset` query params. UI provides Previous/Next buttons.

2. **Job deletion permission**: Contract requires auth but no role check. UI shows Delete button only when authenticated.

3. **Chat history format**: Contract returns `{id, sender, message, timestamp}`. UI renders based on `sender` field.

4. **Mock mode**: When `USE_MOCK = true`, all API calls return sample JSON from `mock.js` without hitting the server. This allows full UI demo without the backend.

5. **File upload progress**: Contract doesn't specify progress events. UI shows spinner during upload and analysis.

6. **URL validation**: Only `http://` and `https://` URLs are rendered as clickable links (XSS prevention).