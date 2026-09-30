# AI Resume Analyzer — REST API Contract

> **Frontend Team Source of Truth**: Standardized API documentation for all endpoints, schemas, authentication, and error responses.

---

## General API Conventions

### Base URL & Protocol
- Base Path: `/api`
- All communications are encoded using `application/json` unless handling multipart form data (file uploads).

### Authentication Standard
- Authentication is handled via **JWT (JSON Web Tokens)**.
- Protected endpoints require the header:
  ```http
  Authorization: Bearer <your_jwt_access_token>
  ```

### Standard Error Response Schema
All error responses across all endpoints strictly follow this JSON shape:
```json
{
  "detail": "Human-readable explanation of the error."
}
```

### Status Codes Used
| Code | Meaning |
|---|---|
| `200` | Success |
| `201` | Created (register, upload, job create) |
| `400` | Bad request (business validation: duplicate email, unanalyzed resume, unusable file) |
| `401` | Missing / invalid / expired bearer token, or wrong password |
| `404` | Resource not found **or** owned by another user (never distinguish the two) |
| `413` | Uploaded file exceeds 5 MB |
| `422` | Request body / query parameter failed schema validation |

### Security Response Headers
Every response (API and static) includes:
```http
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: same-origin
Cross-Origin-Opener-Policy: same-origin
```
CORS is intentionally **not** enabled — the frontend is served from the same
origin as the API.

---

## 1. Authentication Endpoints (`/api/auth`)

### 1.1 Register User
- **Method**: `POST`
- **Path**: `/api/auth/register`
- **Auth Required**: No
- **Request Body** (`application/json`):
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123!",
    "full_name": "Jane Doe"
  }
  ```
- **Success Response** (`201 Created`):
  ```json
  {
    "user": {
      "id": 1,
      "email": "user@example.com",
      "full_name": "Jane Doe",
      "created_at": "2026-09-29T19:50:00Z"
    },
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
  }
  ```
- **Error Responses**:
  - `400 Bad Request`:
    ```json
    {
      "detail": "An account with this email address already exists."
    }
    ```
  - `422 Unprocessable Entity`:
    ```json
    {
      "detail": "Password must be at least 8 characters long."
    }
    ```

---

### 1.2 Login User
- **Method**: `POST`
- **Path**: `/api/auth/login`
- **Auth Required**: No
- **Request Body** (`application/json`):
  ```json
  {
    "email": "user@example.com",
    "password": "SecurePassword123!"
  }
  ```
- **Success Response** (`200 OK`):
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "email": "user@example.com",
      "full_name": "Jane Doe",
      "created_at": "2026-09-29T19:50:00Z"
    }
  }
  ```
- **Error Response** (`401 Unauthorized`):
  ```json
  {
    "detail": "Invalid email or password."
  }
  ```

---

### 1.3 Logout User
- **Method**: `POST`
- **Path**: `/api/auth/logout`
- **Auth Required**: Yes
- **Request Body**: None
- **Success Response** (`200 OK`):
  ```json
  {
    "detail": "Successfully logged out."
  }
  ```
- **Error Response** (`401 Unauthorized`):
  ```json
  {
    "detail": "Not authenticated."
  }
  ```

---

### 1.4 Get Current User Profile
- **Method**: `GET`
- **Path**: `/api/auth/me`
- **Auth Required**: Yes
- **Success Response** (`200 OK`):
  ```json
  {
    "id": 1,
    "email": "user@example.com",
    "full_name": "Jane Doe",
    "created_at": "2026-09-29T19:50:00Z"
  }
  ```
- **Error Response** (`401 Unauthorized`):
  ```json
  {
    "detail": "Could not validate credentials."
  }
  ```

---

## 2. Resume Management Endpoints (`/api/resumes`)

### 2.1 Upload Resume
- **Method**: `POST`
- **Path**: `/api/resumes/upload`
- **Auth Required**: Yes
- **Request Format**: `multipart/form-data`
- **Form Fields**:
  - `file`: Binary File (PDF or DOCX, max 5 MB).
  - `title` (optional): String (e.g. "Software Engineer Resume 2026").
- **Success Response** (`201 Created`):
  ```json
  {
    "id": 12,
    "user_id": 1,
    "title": "Software Engineer Resume 2026",
    "original_filename": "Jane_Doe_Resume.pdf",
    "file_type": "pdf",
    "file_size": 245800,
    "parsed_text_snippet": "Jane Doe | Senior Software Engineer | jane.doe@example.com | 555-0199...",
    "has_analysis": false,
    "created_at": "2026-09-29T19:52:00Z"
  }
  ```
  > Notes: `title` falls back to `original_filename` when not supplied. The file
  > is stored server-side under a UUID-prefixed name; the path is never returned.
  > `original_filename` is sanitized (directory components stripped).
- **Error Responses** (all errors use the `{"detail": "..."}` schema):
  - `400 Bad Request` — wrong extension:
    ```json
    {
      "detail": "Invalid file format. Only PDF (.pdf) and DOCX (.docx) files are supported."
    }
    ```
  - `400 Bad Request` — empty file: `"Uploaded file is empty (0 bytes)."`
  - `400 Bad Request` — magic-byte mismatch: `"File content header does not match valid PDF format."`
  - `400 Bad Request` — no extractable text (scanned/protected PDF):
    `"Unable to extract text from document. Please ensure the file is not scanned, empty, or password-protected."`
  - `400 Bad Request` — extraction failure: `"Unable to process the uploaded document."`
  - `413 Content Too Large`:
    ```json
    {
      "detail": "File size exceeds maximum limit of 5MB."
    }
    ```
  - `401 Unauthorized` — missing/invalid bearer token.

---

### 2.2 List User Resumes
- **Method**: `GET`
- **Path**: `/api/resumes`
- **Auth Required**: Yes
- **Success Response** (`200 OK`):
  ```json
  [
    {
      "id": 12,
      "title": "Software Engineer Resume 2026",
      "original_filename": "Jane_Doe_Resume.pdf",
      "file_type": "pdf",
      "created_at": "2026-09-29T19:52:00Z",
      "has_analysis": true
    }
  ]
  ```

---

### 2.3 Get Resume Details
- **Method**: `GET`
- **Path**: `/api/resumes/{resume_id}`
- **Auth Required**: Yes
- **Success Response** (`200 OK`):
  ```json
  {
    "id": 12,
    "user_id": 1,
    "title": "Software Engineer Resume 2026",
    "original_filename": "Jane_Doe_Resume.pdf",
    "file_type": "pdf",
    "parsed_text": "Jane Doe\nSenior Software Engineer\nEmail: jane.doe@example.com...",
    "created_at": "2026-09-29T19:52:00Z"
  }
  ```
- **Error Response** (`404 Not Found`):
  ```json
  {
    "detail": "Resume with ID 12 not found."
  }
  ```

---

### 2.4 Delete Resume
- **Method**: `DELETE`
- **Path**: `/api/resumes/{resume_id}`
- **Auth Required**: Yes
- **Success Response** (`200 OK`):
  ```json
  {
    "detail": "Resume and associated analyses deleted successfully."
  }
  ```
- **Error Response** (`404 Not Found`):
  ```json
  {
    "detail": "Resume not found."
  }
  ```

---

### 2.5 Trigger AI Resume Analysis
- **Method**: `POST`
- **Path**: `/api/resumes/{resume_id}/analyze`
- **Auth Required**: Yes
- **Success Response** (`200 OK`):
  ```json
  {
    "id": 5,
    "resume_id": 12,
    "status": "completed",
    "created_at": "2026-09-29T19:55:00Z",
    "result": {
      "full_name": "Jane Doe",
      "email": "jane.doe@example.com",
      "phone": "+1-555-0199",
      "location": "San Francisco, CA",
      "summary": "Results-oriented Senior Software Engineer with 6 years of experience building high-concurrency microservices, REST APIs, and scalable backend platforms using Python and Cloud services.",
      "technical_skills": [
        "Python",
        "FastAPI",
        "PostgreSQL",
        "Docker",
        "REST APIs",
        "Git",
        "AWS (S3, EC2)"
      ],
      "soft_skills": [
        "Leadership",
        "Cross-functional Collaboration",
        "Problem Solving",
        "Agile Methodology"
      ],
      "education": [
        {
          "degree": "B.S. in Computer Science",
          "institution": "University of California, Berkeley",
          "year": "2020"
        }
      ],
      "experience": [
        {
          "company": "TechStream Solutions",
          "role": "Senior Backend Developer",
          "duration": "2022 - Present",
          "responsibilities": [
            "Architected RESTful microservices processing 10M daily transactions.",
            "Optimized SQL query performance reducing endpoint latency by 45%."
          ]
        },
        {
          "company": "DataPulse Inc.",
          "role": "Software Developer",
          "duration": "2020 - 2022",
          "responsibilities": [
            "Developed backend features using Python and Flask.",
            "Integrated third-party payment gateways and webhook services."
          ]
        }
      ],
      "years_of_experience": 6,
      "domain_strengths": [
        "Backend Architecture",
        "API Design",
        "Database Optimization"
      ]
    }
  }
  ```
- **Error Response** (`502 Bad Gateway`):
  ```json
  {
    "detail": "AI Analysis service is currently unavailable. Please try again later."
  }
  ```

---

### 2.6 Get Resume Analysis Result
- **Method**: `GET`
- **Path**: `/api/resumes/{resume_id}/analysis`
- **Auth Required**: Yes
- **Success Response** (`200 OK`): Matches the structure of `2.5` above.
- **Error Response** (`404 Not Found`):
  ```json
  {
    "detail": "No analysis found for this resume. Please trigger analysis first."
  }
  ```

---

## 3. Job Management Endpoints (`/api/jobs`)

### 3.1 List and Search Jobs
- **Method**: `GET`
- **Path**: `/api/jobs`
- **Auth Required**: Optional
- **Query Parameters**:
  - `title` (optional): Filter by job title keyword (e.g. `title=Backend`).
  - `skill` (optional): Filter by required skill (e.g. `skill=Python`).
  - `location` (optional): Filter by location (e.g. `location=Remote`).
  - `job_type` (optional): Filter by type (`Full-time`, `Part-time`, `Contract`, `Remote`).
  - `experience_level` (optional): Filter level (`Entry`, `Mid`, `Senior`).
  - `limit` (optional): Integer (default 20).
  - `offset` (optional): Integer (default 0).
- **Success Response** (`200 OK`):
  ```json
  {
    "total": 1,
    "jobs": [
      {
        "id": 101,
        "title": "Senior Python Backend Engineer",
        "company": "CloudScale Systems",
        "location": "Remote / San Francisco",
        "job_type": "Full-time",
        "experience_level": "Senior",
        "min_years_experience": 4,
        "required_skills": ["Python", "FastAPI", "Docker", "PostgreSQL", "Kubernetes"],
        "soft_skills": ["Problem Solving", "Teamwork"],
        "salary_range": "$130,000 - $160,000",
        "created_at": "2026-09-25T10:00:00Z"
      }
    ]
  }
  ```

---

### 3.2 Get Job Details
- **Method**: `GET`
- **Path**: `/api/jobs/{job_id}`
- **Auth Required**: No
- **Success Response** (`200 OK`):
  ```json
  {
    "id": 101,
    "title": "Senior Python Backend Engineer",
    "company": "CloudScale Systems",
    "location": "Remote / San Francisco",
    "job_type": "Full-time",
    "experience_level": "Senior",
    "min_years_experience": 4,
    "required_degree": "Bachelor",
    "description": "We are seeking a Senior Python Engineer to build scalable microservices...",
    "required_skills": ["Python", "FastAPI", "Docker", "PostgreSQL", "Kubernetes"],
    "soft_skills": ["Problem Solving", "Teamwork"],
    "salary_range": "$130,000 - $160,000",
    "created_at": "2026-09-25T10:00:00Z"
  }
  ```
- **Error Response** (`404 Not Found`):
  ```json
  {
    "detail": "Job posting with ID 101 not found."
  }
  ```

---

### 3.3 Create Job Posting
- **Method**: `POST`
- **Path**: `/api/jobs`
- **Auth Required**: Yes
- **Request Body** (`application/json`):
  ```json
  {
    "title": "Senior Python Backend Engineer",
    "company": "CloudScale Systems",
    "location": "Remote / San Francisco",
    "job_type": "Full-time",
    "experience_level": "Senior",
    "min_years_experience": 4,
    "required_degree": "Bachelor",
    "description": "We are seeking a Senior Python Engineer to build scalable microservices using FastAPI and SQLite vector capabilities.",
    "required_skills": ["Python", "FastAPI", "Docker", "PostgreSQL", "Kubernetes"],
    "soft_skills": ["Problem Solving", "Teamwork"],
    "salary_range": "$130,000 - $160,000"
  }
  ```
- **Success Response** (`201 Created`): Returns created job object with assigned `id`.

---

### 3.4 Update Job Posting
- **Method**: `PUT`
- **Path**: `/api/jobs/{job_id}`
- **Auth Required**: Yes
- **Request Body**: Partial or complete job object JSON fields.
- **Success Response** (`200 OK`): Returns updated job object JSON.

---

### 3.5 Delete Job Posting
- **Method**: `DELETE`
- **Path**: `/api/jobs/{job_id}`
- **Auth Required**: Yes
- **Success Response** (`200 OK`):
  ```json
  {
    "detail": "Job posting deleted successfully."
  }
  ```

---

## 4. Job Recommendations Endpoints (`/api/resumes/{resume_id}/recommendations`)

### 4.1 Get Job Recommendations for Resume
- **Method**: `GET`
- **Path**: `/api/resumes/{resume_id}/recommendations`
- **Auth Required**: Yes
- **Query Parameters**:
  - `min_score` (optional): Integer threshold 0-100 (default `0`, i.e. no filtering).
  - `limit` (optional): Integer 1-100, max jobs returned (default `10`).
  - `explain` (optional): Boolean (default `true`). When `false`, the LLM
    explanation pass is skipped and a deterministic explanation is returned —
    useful for fast/dashboard calls.
- **Ordering**: `recommendations` are sorted by `match_score` descending.
- **Precondition**: `400 Bad Request` with
  `{"detail": "Resume must be analyzed before requesting job recommendations."}`
  if the resume has no completed analysis.
- **Success Response** (`200 OK`):
  ```json
  {
    "resume_id": 12,
    "total_matched": 1,
    "recommendations": [
      {
        "job": {
          "id": 101,
          "title": "Senior Python Backend Engineer",
          "company": "CloudScale Systems",
          "location": "Remote / San Francisco",
          "job_type": "Full-time",
          "salary_range": "$130,000 - $160,000"
        },
        "match_score": 88,
        "match_grade": "High Match",
        "matched_technical_skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
        "missing_technical_skills": ["Kubernetes"],
        "matched_soft_skills": ["Problem Solving"],
        "missing_soft_skills": [],
        "experience_fit": "Candidate has 6 years vs 4 years required.",
        "education_fit": "Candidate holds B.S. in CS matching degree requirement.",
        "explanation": "Jane is an exceptional fit for this role. She brings 6 years of core Python experience and expertise in FastAPI and microservices. Acquiring basic Kubernetes deployment knowledge will complete her qualification."
      }
    ]
  }
  ```
- **Error Response** (`400 Bad Request`):
  ```json
  {
    "detail": "Resume must be analyzed before requesting job recommendations."
  }
  ```

---

## 5. Resume Improvement Endpoints (`/api/resumes/{resume_id}/improvements`)

### 5.1 Get Resume Improvement Advice
- **Method**: `GET`
- **Path**: `/api/resumes/{resume_id}/improvements`
- **Auth Required**: Yes
- **Success Response** (`200 OK`):
  ```json
  {
    "resume_id": 12,
    "overall_score": 82,
    "strengths": [
      "Strong technical base in Python and FastAPI microservices.",
      "Clear metric-driven achievement statements in past experience."
    ],
    "weaknesses": [
      "Lack of demonstrated cloud orchestration experience (e.g. Kubernetes, Terraform).",
      "Resume summary lacks specific career targeting goals."
    ],
    "missing_critical_skills": [
      {
        "skill": "Kubernetes",
        "importance": "High",
        "appears_in_job_matches": 4
      },
      {
        "skill": "Redis",
        "importance": "Medium",
        "appears_in_job_matches": 2
      }
    ],
    "recommended_certifications": [
      {
        "title": "AWS Certified Developer – Associate",
        "provider": "Amazon Web Services",
        "link": "https://aws.amazon.com/certification/certified-developer-associate/"
      }
    ],
    "learning_resources": [
      {
        "skill": "Kubernetes",
        "resource_name": "Kubernetes Mastery: Hands-On Docker & K8s",
        "type": "Course",
        "url": "https://www.coursera.org/learn/kubernetes"
      }
    ],
    "actionable_bullet_improvements": [
      "Rewrite summary to specify target senior cloud/backend architecture roles.",
      "Add a 'Key Projects' section demonstrating Docker container deployments."
    ]
  }
  ```

---

## 6. AI Career Advisor Chat Endpoints (`/api/chat`)

### 6.1 Send Chat Message
- **Method**: `POST`
- **Path**: `/api/chat`
- **Auth Required**: Yes
- **Request Body** (`application/json`):
  ```json
  {
    "resume_id": 12,
    "job_id": 101,
    "message": "What specific projects should I build to learn Kubernetes for this Backend Engineer role?"
  }
  ```
- **Success Response** (`200 OK`):
  ```json
  {
    "session_id": "session-uuid-9876",
    "user_message": "What specific projects should I build to learn Kubernetes for this Backend Engineer role?",
    "reply": "To showcase Kubernetes skills for CloudScale Systems' Senior Backend Engineer role, I recommend building a multi-container FastAPI application...",
    "actionable_recommendations": [
      {
        "category": "Project Idea",
        "title": "FastAPI + PostgreSQL + Redis K8s Deployment",
        "provider": "Self-Guided Portfolio",
        "reason": "Demonstrates ingress routing, persistent volumes, and secret management."
      }
    ],
    "suggested_followups": [
      "How do I set up local Kubernetes using Minikube?",
      "Can you review my resume bullet points for cloud projects?"
    ]
  }
  ```

---

### 6.2 Get Chat History
- **Method**: `GET`
- **Path**: `/api/chat/history`
- **Auth Required**: Yes
- **Query Parameters**:
  - `resume_id` (optional): Filter history by resume ID context.
  - `limit` (optional): Integer (default 50).
- **Success Response** (`200 OK`):
  ```json
  [
    {
      "id": 1,
      "sender": "user",
      "message": "What specific projects should I build to learn Kubernetes?",
      "timestamp": "2026-09-29T20:00:00Z"
    },
    {
      "id": 2,
      "sender": "assistant",
      "message": "To showcase Kubernetes skills, build a multi-container FastAPI app...",
      "timestamp": "2026-09-29T20:00:02Z"
    }
  ]
  ```

---

### 6.3 Clear Chat History
- **Method**: `DELETE`
- **Path**: `/api/chat/history`
- **Auth Required**: Yes
- **Success Response** (`200 OK`):
  ```json
  {
    "detail": "Chat history cleared successfully."
  }
  ```

---

## 7. Knowledge Base Search Endpoints (`/api/kb`) [Debug / Optional]

### 7.1 Search Knowledge Base Chunks
- **Method**: `GET`
- **Path**: `/api/kb/search`
- **Auth Required**: Yes
- **Query Parameters**:
  - `q`: Search query string (e.g. `q=Kubernetes+learning`).
  - `category` (optional): Filter category (`skill`, `resource`, `roadmap`, `resume_tip`).
  - `limit` (optional): Integer (default 5).
- **Success Response** (`200 OK`):
  ```json
  {
    "query": "Kubernetes learning",
    "total_results": 2,
    "results": [
      {
        "chunk_id": 42,
        "title": "Kubernetes Learning Roadmap",
        "category": "roadmap",
        "content_snippet": "Kubernetes fundamentals include Pods, Services, Deployments, and Ingress controllers...",
        "similarity_score": 0.89
      }
    ]
  }
  ```
