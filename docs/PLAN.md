# AI Resume Analyzer — System Architecture & Implementation Plan

> **Phase 1 Deliverable**: System Architecture, Agent Design, RAG Engine, Scoring Algorithm, Error Strategy, and Implementation Roadmap.

---

## 1. Architecture Overview

### 1.1 High-Level Architecture
The **AI Resume Analyzer** is designed as a monolithic lightweight web application leveraging **FastAPI** for backend API services and **Vanilla HTML5/CSS3/JavaScript** for the client application. To simplify deployment and eliminate CORS issues, FastAPI directly serves the static frontend assets at `/` via `StaticFiles`, while exposing all REST API endpoints under `/api/...`.

```
+-----------------------------------------------------------------------+
|                            BROWSER CLIENT                             |
|    HTML5 Multi-Page App + Vanilla JS (Fetch API + LocalStorage JWT)   |
+-----------------------------------------------------------------------+
                                   |
                          HTTP / REST API requests
                                   v
+-----------------------------------------------------------------------+
|                            FASTAPI BACKEND                            |
|                                                                       |
|  +-----------------------------+   +-------------------------------+  |
|  |     StaticFiles Router      |   |        /api Router            |  |
|  |     (Serves frontend/)      |   | (Auth, Resumes, Jobs, Chat)   |  |
|  +-----------------------------+   +---------------+---------------+  |
|                                                    |                  |
|  +-------------------------------------------------+---------------+  |
|  |                          SERVICES LAYER                         |  |
|  |  +-------------------+  +------------------+  +--------------+  |  |
|  |  | Resume Parser     |  | AI Agents Engine |  | RAG Engine   |  |  |
|  |  | (pdfplumber,      |  | (Analyzer,       |  | (Embedding & |  |  |
|  |  |  python-docx)     |  |  Matcher, Chat)  |  |  Vector DB)  |  |  |
|  |  +-------------------+  +------------------+  +--------------+  |  |
|  +-----------------------------------------------------------------+  |
|                                   |                                   |
|  +--------------------------------+--------------------------------+  |
|  |                       DATA STORAGE LAYER                        |  |
|  |   +--------------------------+     +------------------------+   |  |
|  |   | SQLite DB (app.db)       |     | Local File Storage     |   |  |
|  |   | (Users, Resumes, Jobs,   |     | (uploads/, kb_data/)   |   |  |
|  |   |  Embeddings, Chat)       |     |                        |   |  |
|  |   +--------------------------+     +------------------------+   |  |
+-----------------------------------------------------------------------+
```

### 1.2 Component Responsibilities

1. **Frontend (`frontend/`)**:
   - Pure HTML, CSS (`style.css`), and Vanilla JS scripts (`js/api.js`, etc.).
   - No build step, framework dependencies, or node modules.
   - Interacts with `/api` via standard `fetch()` using standard Bearer token authorization stored in `localStorage`.

2. **API Layer (`app/api/`)**:
   - Handles REST request validation, route handling, dependency injection (`deps.py`), and response formatting.
   - Guarantees uniform error shapes (`{"detail": "..."}`) and standard HTTP status codes.

3. **Services & AI Agents Layer (`app/services/`)**:
   - `resume_parser.py`: Parses text content from uploaded PDF and DOCX files securely.
   - `agent_analyzer.py`: Invokes LLM with structured prompts to parse resumes into formatted JSON.
   - `agent_matcher.py`: Evaluates candidate resumes against job descriptions using hybrid deterministic + LLM scoring.
   - `agent_advisor.py`: Powers interactive chat providing tailored career guidance.
   - `rag_service.py` & `vector_store.py`: Performs chunking, vector embedding, and SQLite cosine vector similarity search.

4. **Persistence Layer (`app/models/` & `data/`)**:
   - **SQLite (`data/app.db`)**: Holds relational tables and BLOB/JSON vector embeddings.
   - **File System (`data/uploads/`)**: Holds original resume documents with unique UUID filenames.

---

## 2. Agent Design

The system implements three specialized AI agents. Each agent operates with specific inputs, structured output constraints, system prompts, and fallback mechanisms.

```
                  +--------------------------+
                  |  Uploaded PDF / DOCX     |
                  +------------+-------------+
                               |
                               v
                  +--------------------------+
                  |   Resume Parser Service  |
                  +------------+-------------+
                               | (Raw Text)
                               v
                  +--------------------------+
                  |  Resume Analyzer Agent   |
                  +------------+-------------+
                               | (Structured Analysis JSON)
              +----------------+----------------+
              |                                 |
              v                                 v
+--------------------------+       +--------------------------+
|   Job Matching Agent     |       |   Career Advisor Agent   |
| (Resume JSON + Jobs DB + |       | (Resume JSON + User Chat |
|       RAG Context)       |       |      + RAG Context)      |
+-------------+------------+       +------------+-------------+
              |                                 |
              v                                 v
   Job Recommendations &               Interactive Chat &
    Matching Scores (0-100)           Improvement Guidance
```

### 2.1 Agent 1: Resume Analyzer Agent
- **Purpose**: Parses unstructured resume text and transforms it into a standardized, validated JSON schema.
- **Inputs**: Raw text extracted from PDF/DOCX resume file.
- **Outputs**:
  ```json
  {
    "full_name": "Jane Doe",
    "email": "jane.doe@example.com",
    "phone": "+1-555-0199",
    "location": "San Francisco, CA",
    "summary": "Senior Software Engineer with 6+ years experience building distributed web services.",
    "technical_skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs", "AWS"],
    "soft_skills": ["Leadership", "Problem Solving", "Agile Communication"],
    "experience": [
      {
        "company": "Tech Corp",
        "role": "Senior Backend Developer",
        "duration": "2021 - Present",
        "responsibilities": ["Architected microservices handling 10M daily requests.", "Mentored junior developers."]
      }
    ],
    "education": [
      {
        "institution": "University of California",
        "degree": "B.S. Computer Science",
        "year": "2019"
      }
    ],
    "years_of_experience": 6,
    "domain_strengths": ["Backend Engineering", "Cloud Architecture"]
  }
  ```
- **System Prompt**:
  ```
  You are an expert HR Analyst and Technical Resume Parser. Your job is to extract candidate details from unstructured resume text into exact JSON format.
  Rules:
  1. Extract contact details, summary, technical skills, soft skills, work experience, education, total years of experience, and primary domain strengths.
  2. Categorize technical skills explicitly (programming languages, frameworks, tools, databases).
  3. Ensure experience entries contain company, role, duration, and bullet points of key responsibilities/achievements.
  4. Output MUST be strictly valid JSON matching the required structure without markdown wrapping or conversational commentary.
  ```

---

### 2.2 Agent 2: Job Matching Agent
- **Purpose**: Evaluates candidate profile against job postings in the database, producing a score from 0-100, matched/missing skills, and qualitative fit analysis.
- **Inputs**:
  - Resume Analysis JSON
  - Target Job Posting JSON (title, description, required skills, min experience, location)
  - RAG Context (Skill synonym mappings and domain requirements)
- **Outputs**:
  ```json
  {
    "match_score": 88,
    "match_grade": "High",
    "matched_technical_skills": ["Python", "FastAPI", "Docker", "REST APIs"],
    "missing_technical_skills": ["Kubernetes", "Redis"],
    "matched_soft_skills": ["Problem Solving"],
    "missing_soft_skills": ["Cross-functional Teamwork"],
    "experience_fit": "Fully meets requirement (6 years vs 4 years required)",
    "education_fit": "Matches required degree level",
    "explanation": "Jane's strong background in Python and FastAPI aligns exceptionally well with the Senior Backend role. She meets all core backend requirements, though gaining experience in Kubernetes would make her an ideal candidate."
  }
  ```
- **System Prompt**:
  ```
  You are an AI Job Matching Specialist. Compare the candidate's resume analysis JSON with the provided job specification and relevant RAG skill knowledge.
  Tasks:
  1. Identify exact and synonym matches between candidate skills and required job skills.
  2. Identify critical missing technical skills and soft skills.
  3. Evaluate experience level and educational qualification fit.
  4. Provide a fair, objective narrative explanation highlighting key strengths and areas of divergence.
  5. Structure your output strictly as valid JSON matching the exact schema specified.
  ```

---

### 2.3 Agent 3: Career Advisor Agent
- **Purpose**: Provides interactive, conversational career coaching, skill development advice, learning resource recommendations, and interview preparation guidance based on candidate resume and knowledge base context.
- **Inputs**:
  - Candidate Resume Analysis JSON
  - Optional Target Job or Target Role Context
  - Current User Query / Message
  - Conversation History (last N messages)
  - RAG Context (Retrieved career roadmaps, skill descriptions, recommended courses, and certifications)
- **Outputs**:
  ```json
  {
    "reply": "Based on your background in Python and FastAPI, transitioning into a Cloud Solutions Architect role requires deepening your expertise in AWS and Kubernetes. Here is a recommended path...",
    "actionable_recommendations": [
      {
        "category": "Certification",
        "title": "AWS Certified Solutions Architect – Associate",
        "provider": "Amazon Web Services",
        "reason": "Validates cloud architecture knowledge required for Senior roles."
      },
      {
        "category": "Learning Resource",
        "title": "Kubernetes Deep Dive",
        "provider": "Coursera / Udemy",
        "reason": "Fills the container orchestration gap identified in your recent job matches."
      }
    ],
    "suggested_followups": [
      "What projects can I build to demonstrate Kubernetes experience?",
      "How should I update my resume summary for a Cloud Architect role?"
    ]
  }
  ```
- **System Prompt**:
  ```
  You are an empathetic, expert AI Career Advisor and Tech Mentor. You help job seekers advance their careers by giving actionable advice, recommending tailored courses/certifications, and guiding resume improvements.
  Always inspect the provided candidate resume profile and retrieved knowledge base context before answering.
  Guidelines:
  - Be encouraging, precise, and practical.
  - Tailor course and certification suggestions directly to the candidate's missing skills.
  - Answer career queries directly and concisely.
  - Structure response as JSON containing `reply`, `actionable_recommendations`, and `suggested_followups`.
  ```

---

## 3. RAG (Retrieval-Augmented Generation) Design

The RAG engine enhances AI agent accuracy by grounding recommendations in curated domain knowledge (job market trends, skill taxonomies, learning resources, and career roadmaps) before generating responses.

```
+--------------------------+
|  Knowledge Base Corpus   |
| (JSON / Markdown / Text) |
+------------+-------------+
             |
             v
+--------------------------+
| Recursive Chunking Engine|  (Chunk Size: 500 chars, Overlap: 50 chars)
+------------+-------------+
             |
             v
+--------------------------+
|  Embedding Generator     |  (Model: sentence-transformers / all-MiniLM-L6-v2)
+------------+-------------+
             |
             v
+--------------------------+
|  SQLite Vector Database  |  (Table: kb_chunks with BLOB/JSON vector storage)
+------------+-------------+
             |
   --- QUERY EXECUTION ---
             |
User Query / Missing Skills
             |
             v
+--------------------------+
| SQLite Cosine Similarity |  (Calculates dot product / vector norm top-K=5)
+------------+-------------+
             |
             v
+--------------------------+
| Augmented LLM Prompt     |  (Injected into Agent Context)
+--------------------------+
```

### 3.1 Knowledge Base Structure (`data/kb_data/`)
The knowledge base consists of structured files divided into categories:
1. `skills_taxonomy.json`: Skill relationships (e.g., "FastAPI" -> "Python Framework", "React" -> "Frontend").
2. `learning_resources.json`: Curated list of courses, certifications, documentation links, and books indexed by skill tag.
3. `career_roadmaps.json`: Standard career progression paths (e.g., Junior Backend -> Senior Backend -> Cloud Architect).
4. `resume_guidelines.json`: Best practices for resume formatting, action verbs, and impact measurement.

### 3.2 Chunking Strategy
- **Strategy**: Recursive Character / Heading Chunking.
- **Chunk Size**: ~500 characters.
- **Overlap**: 50 characters (preserves sentence boundary context).
- **Metadata Tagging**: Each chunk is indexed with `doc_id`, `category` (`skill`, `resource`, `roadmap`, `resume_tip`), `title`, and `tags`.

### 3.3 Embeddings & Vector Storage Choice
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional dense vectors, lightweight, fast CPU inference in Python).
- **Storage Strategy in SQLite**:
  - SQLite table `kb_chunks` stores the text chunk, metadata JSON, and the 384-float vector stored as a binary `BLOB` (or float JSON array).
  - **Vector Query Mechanism**: Python handles similarity calculation using NumPy vector dot-product / cosine similarity over SQLite query results, OR SQLite custom function `cosine_similarity(v1, v2)` registered on connection start.
  - **Fallback / TF-IDF Option**: If `sentence-transformers` is unavailable or lightweight execution is required, SQLite built-in `FTS5` full-text search combined with TF-IDF keyword overlap serves as a zero-dependency fallback.

> **Implementation note (as built).**
> - Knowledge-base files in `data/kb_data/`: `skills.json`, `career_roadmaps.json`,
>   `learning_resources.json`, `resume_guidelines.json` (25 documents → **50 chunks**).
>   The JSON files are the source of truth and are read on first run; if the
>   directory is missing/empty the embedded `KB_SEED_DATA` is used as a fallback.
> - **Retrieval uses the documented TF-IDF / keyword-overlap option** from §3.3.
>   `sentence-transformers` (~90 MB model download) was deliberately left out of
>   `requirements.txt` to keep the project dependency-light and fully offline.
>   Scoring: `match_count / (sqrt(|query|) * sqrt(|unique text terms|)) * 2`,
>   clipped to 1.0; top-K kept above 0.05 and padded with the next-best matches
>   (never arbitrary rows).
> - Every advisor call retrieves **before** generation and appends
>   `[RESOURCE: …]` / `[SKILL: …]` citations on all paths.

### 3.4 Retrieval Flow
1. **Query Construction**: Extract candidate missing skills, user query, or target job requirements.
2. **Embedding**: Compute vector embedding for the search query.
3. **Similarity Search**: Perform vector cosine similarity comparison across all `kb_chunks` in SQLite; select top-K (K=3 to 5) most relevant chunks (threshold score >= 0.65).
4. **Context Formatting**: Format retrieved chunks into a standard markdown context block.
5. **Prompt Injection**: Prepend retrieved context to the system prompt before invoking LLM generation.

---

## 4. Job Matching-Score Algorithm

To ensure transparency, reliability, and speed, job recommendations use a **hybrid deterministic algorithm** combined with semantic vector similarity scoring.

### 4.1 Scoring Formula

$$\text{Final Score} = (W_{\text{tech}} \cdot S_{\text{tech}}) + (W_{\text{soft}} \cdot S_{\text{soft}}) + (W_{\text{exp}} \cdot S_{\text{exp}}) + (W_{\text{edu}} \cdot S_{\text{edu}}) + (W_{\text{sem}} \cdot S_{\text{sem}})$$

Where weights sum up to $1.0$ (100%):
- $W_{\text{tech}} = 0.40$ (Technical Skill Coverage)
- $W_{\text{soft}} = 0.10$ (Soft Skill Coverage)
- $W_{\text{exp}} = 0.25$ (Experience Duration & Title Fit)
- $W_{\text{edu}} = 0.10$ (Education Level Fit)
- $W_{\text{sem}} = 0.15$ (Semantic Resume vs Job Description Similarity)

---

### 4.2 Sub-Score Calculations

#### A. Technical Skill Score ($S_{\text{tech}}$) — 40%
- Let $R_{\text{tech}}$ be candidate technical skills set (including synonyms from knowledge base).
- Let $J_{\text{tech}}$ be required job technical skills set.
- $S_{\text{tech}} = \frac{|R_{\text{tech}} \cap J_{\text{tech}}|}{|J_{\text{tech}}|} \times 100$

#### B. Soft Skill Score ($S_{\text{soft}}$) — 10%
- $S_{\text{soft}} = \frac{|R_{\text{soft}} \cap J_{\text{soft}}|}{|J_{\text{soft}}|} \times 100$ (Defaults to 100% if job lists no soft skills).

#### C. Experience Score ($S_{\text{exp}}$) — 25%
- Let $Y_{\text{cand}}$ = Candidate years of experience.
- Let $Y_{\text{req}}$ = Job required years of experience.
- If $Y_{\text{req}} == 0$: $S_{\text{exp}} = 100$.
- If $Y_{\text{cand}} \ge Y_{\text{req}}$: $S_{\text{exp}} = 100$.
- If $Y_{\text{cand}} < Y_{\text{req}}$: $S_{\text{exp}} = \max(0, \frac{Y_{\text{cand}}}{Y_{\text{req}}} \times 100)$.

#### D. Education Score ($S_{\text{edu}}$) — 10%
- Degree rank hierarchy: `None` (0) < `High School` (1) < `Associate` (2) < `Bachelor` (3) < `Master` (4) < `Doctorate` (5).
- If candidate degree level $\ge$ required degree level: $S_{\text{edu}} = 100$.
- Else: $S_{\text{edu}} = 60$ (Partial credit if candidate has relevant degree tier below requirement).

#### E. Semantic Similarity Score ($S_{\text{sem}}$) — 15%
- Cosine similarity between embedding vector of candidate summary & experience text and job description vector:
  $$S_{\text{sem}} = \max(0, \text{cosine\_similarity}(\vec{V}_{\text{resume}}, \vec{V}_{\text{job}})) \times 100$$

---

### 4.3 Final Rating Tiers
- **90 – 100**: Exceptional Match (Strong candidate, direct interview candidate)
- **75 – 89**: High Match (Meets primary requirements, minor skill gaps)
- **60 – 74**: Moderate Match (Transferable skills present, upskilling recommended)
- **Below 60**: Low Match (Significant skill or experience gap)

---

## 5. Error-Handling & Resilience Strategy

### 5.1 Standardized Error Format
All backend API routes, middleware, and exception handlers enforce a unified JSON response payload structure:
```json
{
  "detail": "Human-readable explanation of the error."
}
```

### 5.2 HTTP Status Code Mapping
| Status Code | Situation | Trigger Example |
|---|---|---|
| `400 Bad Request` | Client request validation error | Unsupported file extension, missing payload fields |
| `401 Unauthorized` | Invalid or expired token | Missing `Authorization: Bearer` header, corrupt token |
| `403 Forbidden` | Access control violation | User attempting to access another user's resume |
| `404 Not Found` | Requested entity missing | Non-existent resume ID or job ID |
| `413 Payload Too Large` | File upload exceeds maximum size | Uploaded file size > 5 MB |
| `422 Unprocessable Entity` | Pydantic validation failure | Invalid email format, negative experience years |
| `500 Internal Server Error` | Unexpected server crash | File system write failure, unhandled DB error |
| `502 Bad Gateway` | External AI service failure | LLM provider timeout, rate limit, or invalid response |

### 5.3 Resilience & Fallback Mechanisms
1. **File Parsing Resilience**:
   - If PDF extraction via `pdfplumber` fails (e.g. image-only PDF), fall back to `pypdf` text extraction.
   - If document text is completely unextractable, return `400 Bad Request` with helpful error: `"Unable to extract text from document. Please ensure PDF contains selectable text."`
2. **AI Provider Fallbacks**:
   - Wrap all external LLM network calls in timeouts (15s limit) and retry loop (up to 2 retries with exponential backoff).
   - If LLM response fails to parse as valid JSON, trigger a secondary cleaning prompt or fallback to rule-based parser output.
3. **Database Integrity**:
   - SQLite active transactions wrapped in context managers with automatic rollback on error.

---

## 6. Phased Implementation Task List

- [x] **Phase 1: Planning & Architecture (Current Phase)**
  - [x] Create project repository structure and skeleton files.
  - [x] Write `docs/PLAN.md` (System Architecture, Agent Specs, RAG, Scoring, Error strategy).
  - [x] Write `docs/API_CONTRACT.md` (Complete REST API source of truth).
  - [x] Write `docs/ER_DIAGRAM.md` (Mermaid ER diagram and SQLite schema specifications).
  - [x] Write `docs/FRONTEND_BRIEF.md` (Multi-page vanilla frontend architecture & design).

- [x] **Phase 2: Backend Core Infrastructure & Database**
  - [x] Configure `app/config.py` (Pydantic settings, secrets, paths).
  - [x] Set up SQLAlchemy ORM engine & SQLite connection in `app/database.py`.
  - [x] Implement database models in `app/models/` (`user`, `resume`, `analysis`, `job`, `recommendation`, `chat`, `kb`).
  - [x] Implement Security helper functions in `app/core/security.py` (Bcrypt hashing, PyJWT token creation/verification).
  - [x] Implement authentication endpoints in `app/api/auth.py` (`/register`, `/login`, `/logout`, `/me`).
  - [x] Create initial SQLite database migration / table creation scripts.

- [x] **Phase 3: Resume Parser & Storage Engine**
  - [x] Implement document parser in `app/services/resume_parser.py` (PDF & DOCX text extraction).
  - [x] Implement file upload endpoint `/api/resumes/upload` with extension and size checks.
  - [x] Implement resume management endpoints (`GET /api/resumes`, `GET /api/resumes/{id}`, `DELETE /api/resumes/{id}`).

- [x] **Phase 4: AI Agents Development**
  - [x] Implement `app/services/agent_analyzer.py` (Structured JSON resume extraction via LLM).
  - [x] Implement analysis trigger route `POST /api/resumes/{id}/analyze`.
  - [x] Implement Job management endpoints in `app/api/jobs.py` (CRUD + search).
  - [x] Implement `app/services/agent_matcher.py` (Hybrid scoring algorithm + LLM qualitative rationale).
  - [x] Implement recommendation endpoint `GET /api/resumes/{id}/recommendations`.
  - [x] Implement improvement advisor endpoint `GET /api/resumes/{id}/improvements`.

- [x] **Phase 5: Knowledge Base & RAG Pipeline**
  - [x] Create initial knowledge base dataset files under `data/kb_data/`.
  - [x] Implement chunking & vector store logic in `app/services/vector_store.py`.
  - [x] Implement retrieval service in `app/services/rag_service.py`.
  - [x] Implement `app/services/agent_advisor.py` (RAG-infused career advice agent).
  - [x] Implement chat endpoint `/api/chat` and debug KB search endpoint `/api/kb/search`.

- [x] **Phase 6: Frontend Development (Vanilla JS + HTML/CSS)**
  - [x] Create layout stylesheet `frontend/css/style.css`.
  - [x] Implement HTTP client wrapper `frontend/js/api.js` (JWT headers, error toasts, request wrappers).
  - [x] Implement authentication scripts `frontend/js/auth.js` and pages (`register.html`, `login.html`).
  - [x] Implement dashboard `frontend/dashboard.html` and resume management (`upload-resume.html`, `resume-analysis.html`).
  - [x] Implement job management & recommendation UI (`jobs.html`, `job-form.html`, `job-recommendations.html`).
  - [x] Implement Career Advisor chat UI (`career-advisor.html`, `frontend/js/chat.js`).
  - [x] Implement Resume Improvements page (`resume-improvements.html`, `frontend/js/improvements.js`).
  - [x] Mount frontend static directory in `app/main.py`.

- [x] **Phase 7: System Verification & Polish**
  - [x] Run end-to-end user workflows (Registration -> Resume Upload -> Analysis -> Recommendations -> Advisor Chat).
  - [x] Conduct validation on edge case resumes (scanned text, non-standard headings, missing fields).
  - [x] Review security (JWT expiry, path traversal protection on file uploads, password complexity).
  - [x] Perform final code audit and complete project documentation. *(security headers, secret-leak scan, XSS sweep, README/DEMO/contract/ER updated — see `docs/PROGRESS.md`)*
