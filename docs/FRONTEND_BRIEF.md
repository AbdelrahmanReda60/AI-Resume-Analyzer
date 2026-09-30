# AI Resume Analyzer — Frontend Architecture Brief

> **Frontend Implementation Specification**: Multi-page Vanilla HTML5, CSS3, and JavaScript Application Guide.

---

## 1. Architectural Strategy & Design System

### 1.1 Zero-Framework Philosophy
- **Constraints**: No React, Angular, Vue, Svelte, or any client-side JavaScript frameworks. No build step (Babel, Webpack, Vite, Tailwind CLI), no `node_modules`, and no `npm`.
- **Technologies**: Standard HTML5, CSS3 (CSS Variables, Flexbox, CSS Grid), Vanilla JavaScript (ES6+ async/await, Fetch API, DOM manipulation).
- **FastAPI Static Mount Strategy**:
  - FastAPI serves the `frontend/` directory at the root URL `/` using `StaticFiles(directory="frontend", html=True)`.
  - All REST API endpoints reside under `/api/...`.
  - **Result**: Zero CORS issues, straightforward relative API requests (`/api/auth/login`), and instant page loads.

---

## 2. Shared Assets Architecture

### 2.1 Stylesheet (`frontend/css/style.css`)
Centralized CSS file imported across all HTML pages.
- **Design System Tokens**:
  ```css
  :root {
    --primary-color: #2563eb;
    --primary-hover: #1d4ed8;
    --secondary-color: #475569;
    --bg-color: #f8fafc;
    --card-bg: #ffffff;
    --text-color: #0f172a;
    --text-muted: #64748b;
    --border-color: #e2e8f0;
    --success-color: #16a34a;
    --warning-color: #d97706;
    --danger-color: #dc2626;
    --radius-sm: 6px;
    --radius-md: 12px;
    --shadow-md: 0 4px 6px -1px rgb(0 0 0 / 0.1);
  }
  ```
- **Component Classes**:
  - `.btn`, `.btn-primary`, `.btn-secondary`, `.btn-danger`
  - `.card`, `.badge`, `.badge-success`, `.badge-warning`
  - `.pill-tag`, `.pill-tag-matched`, `.pill-tag-missing`
  - `.form-group`, `.form-input`, `.form-select`
  - `.toast-container`, `.toast-error`, `.toast-success`
  - `.chat-bubble`, `.chat-user`, `.chat-assistant`

---

### 2.2 Shared API Fetch Wrapper (`frontend/js/api.js`)
All HTTP requests to `/api` MUST use the global `apiFetch()` helper function exposed by `js/api.js`.

```javascript
/**
 * Global HTTP Fetch Wrapper with automatic JWT attachment and unified error handling.
 */
async function apiFetch(endpoint, options = {}) {
  const token = localStorage.getItem("token");
  const headers = {
    ...options.headers,
  };

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  try {
    const response = await fetch(endpoint, { ...options, headers });

    if (response.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      if (!window.location.pathname.includes("login.html") && !window.location.pathname.includes("register.html")) {
        showToast("Session expired. Please log in again.", "error");
        setTimeout(() => window.location.href = "login.html", 1500);
      }
      throw new Error("Unauthorized");
    }

    const data = await response.json();

    if (!response.ok) {
      const errorMessage = data.detail || "An unexpected error occurred.";
      showToast(errorMessage, "error");
      throw new Error(errorMessage);
    }

    return data;
  } catch (err) {
    if (err.message !== "Unauthorized") {
      console.error("API Error:", err);
    }
    throw err;
  }
}

/**
 * Toast Notification Utility
 */
function showToast(message, type = "info") {
  let toastContainer = document.getElementById("toast-container");
  if (!toastContainer) {
    toastContainer = document.createElement("div");
    toastContainer.id = "toast-container";
    toastContainer.className = "toast-container";
    document.body.appendChild(toastContainer);
  }

  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.innerText = message;
  toastContainer.appendChild(toast);

  setTimeout(() => {
    toast.remove();
  }, 4000);
}
```

---

## 3. Page Inventory & Wireframe Specifications

The frontend consists of **11 dedicated HTML pages**:

```
                                  +-------------------+
                                  |    index.html     |
                                  |   (Landing Page)  |
                                  +---------+---------+
                                            |
                         +------------------+------------------+
                         v                                     v
               +-------------------+                 +-------------------+
               |   register.html   |                 |    login.html     |
               +---------+---------+                 +---------+---------+
                         |                                     |
                         +------------------+------------------+
                                            v
                                  +-------------------+
                                  |  dashboard.html   |
                                  +---------+---------+
                                            |
        +------------------+----------------+----------------+------------------+
        v                  v                                 v                  v
+---------------+  +---------------+                 +---------------+  +---------------+
|upload-resume  |  |  jobs.html    |                 |career-advisor |  |  job-form     |
|    .html      |  | (Search/List) |                 |    .html      |  |    .html      |
+-------+-------+  +-------+-------+                 +---------------+  +---------------+
        |                  |
        v                  v
+---------------+  +---------------+
|resume-analysis|  |   job-rec-    |
|    .html      |  | mendations    |
+-------+-------+  +---------------+
        |
        v
+---------------+
|resume-improve-|
|  ments.html   |
+---------------+
```

---

### 3.1 `index.html` (Landing Page)
- **Purpose**: Public showcase of AI Resume Analyzer features.
- **Components**:
  - Navigation Header (Logo, Link to Jobs search, Login button, Get Started button).
  - Hero Banner with call-to-action buttons ("Upload Your Resume Now").
  - Feature highlights grid (AI Parsing, Match Scoring, Career Advice Chat).
  - Footer with project credits.

---

### 3.2 `register.html` (Registration View)
- **Purpose**: New user account creation.
- **Components**:
  - Centered auth card.
  - Inputs: Full Name, Email Address, Password, Confirm Password.
  - Submit Button ("Create Account").
  - Redirect link ("Already have an account? Log In").
- **JS Logic (`js/auth.js`)**: Validates input match, calls `POST /api/auth/register`, saves token in `localStorage`, redirects to `dashboard.html`.

---

### 3.3 `login.html` (Authentication View)
- **Purpose**: Existing user authentication.
- **Components**:
  - Centered auth card.
  - Inputs: Email Address, Password.
  - Submit Button ("Sign In").
  - Redirect link ("Don't have an account? Register").
- **JS Logic (`js/auth.js`)**: Calls `POST /api/auth/login`, saves JWT token + user metadata in `localStorage`, redirects to `dashboard.html`.

---

### 3.4 `dashboard.html` (User Control Center)
- **Purpose**: Central hub displaying active resumes, quick stats, and quick actions.
- **Components**:
  - Top Navigation Bar (Dashboard, Upload Resume, Browse Jobs, Career Advisor, User Profile, Logout button).
  - Welcome banner with user name.
  - Quick Action Cards ("Upload Resume", "Browse Jobs", "Talk to Career Advisor").
  - Recent Resumes Table (Title, File Type, Upload Date, Analysis Status, Action buttons: Analyze, View Analysis, Recommend Jobs, Delete).
- **JS Logic (`js/resumes.js`)**: Fetches `GET /api/resumes` and populates resumes table dynamically.

---

### 3.5 `upload-resume.html` (Resume Document Upload)
- **Purpose**: Form interface to upload PDF or DOCX documents.
- **Components**:
  - Drag-and-Drop file dropzone area with file browser fallback input.
  - Document Title input (optional).
  - File format badge indicator (`PDF` or `DOCX`, max 5MB).
  - Upload progress bar / loading spinner.
- **JS Logic (`js/resumes.js`)**: Handles drag events, validates file extension and size, submits `FormData` to `POST /api/resumes/upload`, and redirects user to `resume-analysis.html?id={resume_id}`.

---

### 3.6 `resume-analysis.html` (AI Resume Analysis View)
- **Purpose**: Displays the structured output of the Resume Analyzer Agent.
- **Components**:
  - Candidate Profile Header (Name, Email, Phone, Location, Total Experience badge).
  - Executive Summary block.
  - Technical Skills pill container (categorized).
  - Soft Skills pill container.
  - Work Experience Timeline Cards (Company, Role, Duration, Bullet points).
  - Education Cards (Institution, Degree, Year).
  - Domain Strengths list.
  - Quick action toolbar ("Get Job Recommendations", "View Resume Improvements", "Ask Career Advisor").
- **JS Logic (`js/resumes.js`)**: Reads `id` from URL query parameter, triggers `POST /api/resumes/{id}/analyze` (or fetches existing analysis via `GET /api/resumes/{id}/analysis`), renders JSON response into DOM cards.

---

### 3.7 `job-recommendations.html` (Job Match Score View)
- **Purpose**: Displays job recommendations ordered by calculated match score (0-100).
- **Components**:
  - Active Resume selector dropdown.
  - Filter bar (Min Score slider, Location filter).
  - Job Match Cards Grid:
    - Circular match score badge (Color coded: Green >=75, Yellow 60-74, Red <60).
    - Job Title, Company, Location, Salary.
    - Matched Skills tags (Green pills).
    - Missing Skills tags (Red/Orange pills).
    - Fit indicators (Experience fit, Education fit).
    - Qualitative AI Rationale expandable accordion.
- **JS Logic (`js/jobs.js`)**: Calls `GET /api/resumes/{id}/recommendations`, renders score badges and skill breakdown pills dynamically.

---

### 3.8 `jobs.html` (Job Search & Listings)
- **Purpose**: Public and user job discovery board.
- **Components**:
  - Search & Filter bar (Search input by Title/Keyword, Skill filter, Location filter, Job Type dropdown).
  - "Add New Job" button (for admins/recruiters).
  - Job Cards grid: Title, Company, Location, Job Type badge, Required Skills tags, Salary range.
  - Action buttons: "View Details", "Match Against My Resume".
- **JS Logic (`js/jobs.js`)**: Calls `GET /api/jobs?title=...&skill=...` on user input typing (debounced).

---

### 3.9 `job-form.html` (Job Add/Edit View)
- **Purpose**: Form interface to post or update job listings in the database.
- **Components**:
  - Inputs: Job Title, Company, Location, Job Type (`Full-time`, `Remote`), Experience Level (`Entry`, `Mid`, `Senior`), Min Years Experience, Required Degree.
  - Comma-separated Required Technical Skills input.
  - Comma-separated Soft Skills input.
  - Description textarea.
  - Salary Range input.
  - Save / Submit button.
- **JS Logic (`js/jobs.js`)**: Populates form if editing existing `job_id`, submits payload to `POST /api/jobs` or `PUT /api/jobs/{id}`.

---

### 3.10 `career-advisor.html` (AI Career Advisor Chat Interface)
- **Purpose**: Interactive chat application powered by the Career Advisor Agent and RAG knowledge base.
- **Components**:
  - Sidebar: Active Resume selector, Target Job selector, "Clear Chat" button.
  - Chat Window:
    - Scrollable message history pane (User bubbles on right, Assistant bubbles on left).
    - Typing indicator animation.
    - Actionable Recommendations Cards embedded in bot messages (Course links, Certification recommendations).
    - Clickable Suggested Follow-up chips.
  - Message Input Bar (Textarea + Send button).
- **JS Logic (`js/chat.js`)**: Maintains `session_id`, posts user queries to `POST /api/chat`, streams or appends responses, renders follow-up chips that populate the input when clicked.

---

### 3.11 `resume-improvements.html` (Weaknesses & Career Growth View)
- **Purpose**: Specialized career development dashboard generated from the candidate's resume analysis and RAG knowledge base.
- **Components**:
  - Overall Resume Health Score gauge.
  - Key Strengths checklist.
  - Weaknesses & Gaps breakdown.
  - Missing Critical Skills matrix.
  - Recommended Certifications cards (Title, Provider, direct URL link).
  - Recommended Courses & Learning Resources cards.
  - Actionable Bullet Point Improvements list.
- **JS Logic (`js/improvements.js`)**: Calls `GET /api/resumes/{id}/improvements`, populates health gauge and course resource cards.

---

## 4. Client State & Authentication Flow

1. **Authentication Persistence**:
   - `localStorage.setItem('token', access_token)`
   - `localStorage.setItem('user', JSON.stringify(user_data))`
2. **Session Checks**:
   - Protected pages (`dashboard.html`, `upload-resume.html`, `career-advisor.html`, etc.) execute a check on page load:
     ```javascript
     if (!localStorage.getItem('token')) {
       window.location.href = 'login.html';
     }
     ```
3. **Logout Flow**:
   - Calling `POST /api/auth/logout` clears `localStorage` items and redirects the browser to `index.html`.
