import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import docx

import app.models
from app.database import Base, get_db
from app.main import app
from app.services.vector_store import seed_knowledge_base_if_empty
from app.api.jobs import seed_jobs_if_empty

# Setup in-memory SQLite database with StaticPool for concurrency & persistence across requests
TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        seed_knowledge_base_if_empty(db)
        seed_jobs_if_empty(db)
    finally:
        db.close()
    yield
    Base.metadata.drop_all(bind=engine)

def make_test_pdf(text: str) -> bytes:
    """Generates a valid minimal single-page PDF containing extractable text."""
    stream_content = f"BT\n/F1 12 Tf\n72 712 Td\n({text}) Tj\nET"
    stream_len = len(stream_content)
    pdf = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length {stream_len} >>
stream
{stream_content}
endstream
endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000244 00000 n 
0000000318 00000 n 
trailer
<< /Size 6 /Root 1 0 R >>
startxref
420
%%EOF"""
    return pdf.encode("latin1")

def make_test_docx(text: str) -> bytes:
    """Generates a valid DOCX file containing extractable text."""
    doc = docx.Document()
    doc.add_paragraph(text)
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

def test_auth_flow():
    # 1. Register User
    reg_payload = {
        "email": "testuser@example.com",
        "password": "SecurePassword123!",
        "full_name": "Test Candidate"
    }
    res = client.post("/api/auth/register", json=reg_payload)
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["user"]["email"] == "testuser@example.com"
    token = data["access_token"]

    # 2. Duplicate Registration Error
    res_dup = client.post("/api/auth/register", json=reg_payload)
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"]

    # 3. Short Password Validation Error
    res_short = client.post("/api/auth/register", json={
        "email": "short@example.com", "password": "123", "full_name": "Short Pass"
    })
    assert res_short.status_code == 422

    # 4. Login User
    login_payload = {
        "email": "testuser@example.com",
        "password": "SecurePassword123!"
    }
    res_login = client.post("/api/auth/login", json=login_payload)
    assert res_login.status_code == 200
    assert "access_token" in res_login.json()

    # 5. Invalid Login Error
    res_bad_login = client.post("/api/auth/login", json={"email": "testuser@example.com", "password": "WrongPassword"})
    assert res_bad_login.status_code == 401

    # 6. Get User Profile (/api/auth/me)
    headers = {"Authorization": f"Bearer {token}"}
    res_me = client.get("/api/auth/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["full_name"] == "Test Candidate"

    # 7. Logout User
    res_logout = client.post("/api/auth/logout", headers=headers)
    assert res_logout.status_code == 200
    assert "detail" in res_logout.json()

def test_unauthorized_access():
    # Attempting protected routes without token
    assert client.get("/api/resumes").status_code == 401
    assert client.post("/api/chat", json={"message": "hello"}).status_code == 401
    assert client.get("/api/chat/history").status_code == 401
    assert client.delete("/api/chat/history").status_code == 401
    assert client.post("/api/jobs", json={}).status_code == 401

def test_resume_upload_and_validation():
    # Register & Login
    reg_res = client.post("/api/auth/register", json={
        "email": "uploader@example.com", "password": "Password123!", "full_name": "Uploader User"
    })
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Invalid File Extension (.txt)
    files_txt = {"file": ("test.txt", b"Plain text content", "text/plain")}
    res_txt = client.post("/api/resumes/upload", files=files_txt, headers=headers)
    assert res_txt.status_code == 400
    assert "Only PDF" in res_txt.json()["detail"]

    # 2. Corrupt Magic Bytes for PDF
    files_corrupt = {"file": ("corrupt.pdf", b"NOT_A_REAL_PDF_HEADER_12345678", "application/pdf")}
    res_corrupt = client.post("/api/resumes/upload", files=files_corrupt, headers=headers)
    assert res_corrupt.status_code == 400

    # 3. Empty File
    files_empty = {"file": ("empty.pdf", b"", "application/pdf")}
    res_empty = client.post("/api/resumes/upload", files=files_empty, headers=headers)
    assert res_empty.status_code == 400

    # 4. Valid PDF Upload
    pdf_bytes = make_test_pdf("Jane Doe Senior Software Engineer Python FastAPI Docker PostgreSQL AWS Git")
    files_pdf = {"file": ("resume.pdf", pdf_bytes, "application/pdf")}
    res_upload_pdf = client.post("/api/resumes/upload", files=files_pdf, data={"title": "Jane Doe Resume"}, headers=headers)
    assert res_upload_pdf.status_code == 201
    resume_pdf_data = res_upload_pdf.json()
    assert resume_pdf_data["title"] == "Jane Doe Resume"
    resume_id = resume_pdf_data["id"]

    # 5. Valid DOCX Upload
    docx_bytes = make_test_docx("John Smith Full Stack Developer Python JavaScript HTML CSS React SQL")
    files_docx = {"file": ("resume.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    res_upload_docx = client.post("/api/resumes/upload", files=files_docx, data={"title": "John Smith Resume"}, headers=headers)
    assert res_upload_docx.status_code == 201

    # 6. List Resumes
    res_list = client.get("/api/resumes", headers=headers)
    assert res_list.status_code == 200
    assert len(res_list.json()) == 2

    # 7. Get Resume Details
    res_get = client.get(f"/api/resumes/{resume_id}", headers=headers)
    assert res_get.status_code == 200
    assert res_get.json()["id"] == resume_id

    # 8. Analyze Resume
    res_an = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert res_an.status_code == 200
    an_data = res_an.json()
    assert an_data["status"] == "completed"
    assert "result" in an_data
    assert len(an_data["result"]["technical_skills"]) > 0

    # 9. Get Resume Analysis
    res_get_an = client.get(f"/api/resumes/{resume_id}/analysis", headers=headers)
    assert res_get_an.status_code == 200

    # 10. Get Recommendations
    res_rec = client.get(f"/api/resumes/{resume_id}/recommendations", headers=headers)
    assert res_rec.status_code == 200
    rec_data = res_rec.json()
    assert "recommendations" in rec_data
    assert len(rec_data["recommendations"]) > 0
    top_rec = rec_data["recommendations"][0]
    assert 0 <= top_rec["match_score"] <= 100
    assert "matched_technical_skills" in top_rec

    # 11. Get Improvements
    res_imp = client.get(f"/api/resumes/{resume_id}/improvements", headers=headers)
    assert res_imp.status_code == 200
    imp_data = res_imp.json()
    assert "overall_score" in imp_data
    assert len(imp_data["strengths"]) > 0
    assert len(imp_data["learning_resources"]) > 0

    # 12. Delete Resume
    res_del = client.delete(f"/api/resumes/{resume_id}", headers=headers)
    assert res_del.status_code == 200
    assert client.get(f"/api/resumes/{resume_id}", headers=headers).status_code == 404

def test_resume_ownership_protection():
    # User 1 registers and uploads a resume
    reg_u1 = client.post("/api/auth/register", json={
        "email": "user1@example.com", "password": "Password123!", "full_name": "User One"
    })
    token_u1 = reg_u1.json()["access_token"]
    pdf_bytes = make_test_pdf("User One Senior Developer Python")
    upload_res = client.post("/api/resumes/upload", files={"file": ("u1.pdf", pdf_bytes, "application/pdf")}, headers={"Authorization": f"Bearer {token_u1}"})
    u1_resume_id = upload_res.json()["id"]

    # User 2 registers
    reg_u2 = client.post("/api/auth/register", json={
        "email": "user2@example.com", "password": "Password123!", "full_name": "User Two"
    })
    token_u2 = reg_u2.json()["access_token"]
    headers_u2 = {"Authorization": f"Bearer {token_u2}"}

    # User 2 tries to get User 1's resume
    assert client.get(f"/api/resumes/{u1_resume_id}", headers=headers_u2).status_code == 404

    # User 2 tries to analyze User 1's resume
    assert client.post(f"/api/resumes/{u1_resume_id}/analyze", headers=headers_u2).status_code == 404

    # User 2 tries to delete User 1's resume
    assert client.delete(f"/api/resumes/{u1_resume_id}", headers=headers_u2).status_code == 404

def test_job_crud_and_search():
    # 1. Search Jobs (Seeded)
    res_search = client.get("/api/jobs?title=Python")
    assert res_search.status_code == 200
    data = res_search.json()
    assert data["total"] > 0
    assert len(data["jobs"]) > 0

    # Filter by location and job type
    res_remote = client.get("/api/jobs?job_type=Remote")
    assert res_remote.status_code == 200

    # Register Admin User for Job Creation
    reg_res = client.post("/api/auth/register", json={
        "email": "admin@example.com", "password": "Password123!", "full_name": "Admin User"
    })
    headers = {"Authorization": f"Bearer {reg_res.json()['access_token']}"}

    # 2. Create Job
    job_payload = {
        "title": "Lead FastAPI Architect",
        "company": "Innovation Labs",
        "location": "Remote",
        "job_type": "Full-time",
        "experience_level": "Senior",
        "min_years_experience": 5,
        "required_degree": "Bachelor",
        "description": "Architect cloud-native FastAPI microservices with high performance.",
        "required_skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
        "soft_skills": ["Leadership", "Communication"],
        "salary_range": "$150,000 - $180,000"
    }
    res_create = client.post("/api/jobs", json=job_payload, headers=headers)
    assert res_create.status_code == 201
    job_id = res_create.json()["id"]

    # 3. Get Job Details
    res_get = client.get(f"/api/jobs/{job_id}")
    assert res_get.status_code == 200
    assert res_get.json()["title"] == "Lead FastAPI Architect"

    # 4. Update Job
    res_update = client.put(f"/api/jobs/{job_id}", json={"location": "Austin, TX"}, headers=headers)
    assert res_update.status_code == 200
    assert res_update.json()["location"] == "Austin, TX"

    # 5. Delete Job
    res_del = client.delete(f"/api/jobs/{job_id}", headers=headers)
    assert res_del.status_code == 200
    assert client.get(f"/api/jobs/{job_id}").status_code == 404

def test_career_advisor_chat():
    reg_res = client.post("/api/auth/register", json={
        "email": "chatuser@example.com", "password": "Password123!", "full_name": "Chat User"
    })
    token = reg_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Send Chat Message
    chat_payload = {"message": "What courses should I take to learn Kubernetes?"}
    res_chat = client.post("/api/chat", json=chat_payload, headers=headers)
    assert res_chat.status_code == 200
    chat_data = res_chat.json()
    assert "reply" in chat_data
    assert len(chat_data["actionable_recommendations"]) > 0

    # 2. Get Chat History
    res_hist = client.get("/api/chat/history", headers=headers)
    assert res_hist.status_code == 200
    messages = res_hist.json()
    assert len(messages) >= 2  # user and assistant messages

    # 3. Clear History
    res_clear = client.delete("/api/chat/history", headers=headers)
    assert res_clear.status_code == 200
    res_empty_hist = client.get("/api/chat/history", headers=headers)
    assert len(res_empty_hist.json()) == 0

def test_kb_search():
    # Auth is required (matches docs/API_CONTRACT.md section 7.1)
    assert client.get("/api/kb/search?q=FastAPI").status_code == 401

    reg_res = client.post("/api/auth/register", json={
        "email": "kbuser@example.com", "password": "Password123!", "full_name": "KB User"
    })
    headers = {"Authorization": f"Bearer {reg_res.json()['access_token']}"}

    res = client.get("/api/kb/search?q=FastAPI", headers=headers)
    assert res.status_code == 200
    assert res.json()["total_results"] > 0
    first = res.json()["results"][0]
    assert "title" in first
    assert "similarity_score" in first

def _register_and_upload(email: str) -> tuple[str, int]:
    """Helper: register a user, upload a small PDF, return (token, resume_id)."""
    res = client.post("/api/auth/register", json={
        "email": email, "password": "Password123!", "full_name": "Helper User"
    })
    assert res.status_code == 201
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    pdf = make_test_pdf("Helper User Software Engineer Python FastAPI Docker SQL")
    up = client.post(
        "/api/resumes/upload",
        files={"file": ("helper.pdf", pdf, "application/pdf")},
        headers=headers,
    )
    assert up.status_code == 201
    return token, up.json()["id"]


def test_oversized_file_rejected():
    token = _register_and_upload("bigfile@example.com")[0]
    headers = {"Authorization": f"Bearer {token}"}

    oversized = b"%PDF-1.4\n" + (b"0" * (5 * 1024 * 1024 + 1))
    res = client.post(
        "/api/resumes/upload",
        files={"file": ("huge.pdf", oversized, "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 413
    assert "detail" in res.json()
    assert "5MB" in res.json()["detail"]


def test_upload_filename_sanitized_and_text_returned():
    token = _register_and_upload("sane@example.com")[0]
    headers = {"Authorization": f"Bearer {token}"}

    pdf = make_test_pdf("Path Traversal Attempt Resume Python Developer")
    res = client.post(
        "/api/resumes/upload",
        files={"file": ("../../../etc/passwd.pdf", pdf, "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 201
    data = res.json()
    # The stored original filename must never contain directory components
    assert "/" not in data["original_filename"]
    assert ".." not in data["original_filename"]
    assert data["parsed_text_snippet"]
    assert data["file_type"] == "pdf"


def test_foreign_resources_return_404():
    """Every resume-owned endpoint must 404 (not 403/200) for another user."""
    token_a, resume_id = _register_and_upload("owner@example.com")
    res_b = client.post("/api/auth/register", json={
        "email": "intruder@example.com", "password": "Password123!", "full_name": "Intruder"
    })
    headers_b = {"Authorization": f"Bearer {res_b.json()['access_token']}"}

    checks = [
        ("GET", f"/api/resumes/{resume_id}", None),
        ("GET", f"/api/resumes/{resume_id}/analysis", None),
        ("GET", f"/api/resumes/{resume_id}/recommendations", None),
        ("GET", f"/api/resumes/{resume_id}/improvements", None),
        ("POST", f"/api/resumes/{resume_id}/analyze", {}),
        ("DELETE", f"/api/resumes/{resume_id}", None),
        ("POST", "/api/chat", {"resume_id": resume_id, "message": "hi"}),
    ]
    for method, path, body in checks:
        res = client.request(method, path, json=body, headers=headers_b)
        assert res.status_code == 404, f"{method} {path} -> {res.status_code}"

    # The owner still has full access
    assert client.get(f"/api/resumes/{resume_id}", headers={"Authorization": f"Bearer {token_a}"}).status_code == 200


def test_jobs_pagination():
    page1 = client.get("/api/jobs?limit=5&offset=0")
    page2 = client.get("/api/jobs?limit=5&offset=5")
    assert page1.status_code == 200 and page2.status_code == 200
    assert len(page1.json()["jobs"]) == 5
    assert page1.json()["total"] == page2.json()["total"] >= 20
    ids1 = [j["id"] for j in page1.json()["jobs"]]
    ids2 = [j["id"] for j in page2.json()["jobs"]]
    assert not set(ids1) & set(ids2), "pages must not overlap"

    # Bounds are enforced
    assert client.get("/api/jobs?limit=0").status_code == 422
    assert client.get("/api/jobs?offset=-1").status_code == 422


def test_chat_history_order_and_resume_filter():
    token, resume_id = _register_and_upload("history@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    for msg in ["First question about Python", "Second question about Docker"]:
        res = client.post("/api/chat", json={"resume_id": resume_id, "message": msg}, headers=headers)
        assert res.status_code == 200

    res = client.get("/api/chat/history?limit=1", headers=headers)
    assert res.status_code == 200
    single = res.json()
    assert len(single) == 1
    # limit=1 must return the MOST RECENT message in the window
    assert single[0]["sender"] == "assistant"
    # The most recent reply must answer the SECOND question, not the first
    assert "Second question about Docker" in single[0]["message"]

    # Full window is chronological (oldest first) within the recent slice
    res = client.get("/api/chat/history?limit=10", headers=headers)
    messages = res.json()
    assert len(messages) >= 4
    timestamps = [m["timestamp"] for m in messages]
    assert timestamps == sorted(timestamps), "history must be chronological"
    # Latest turn is last chronologically, and the two user turns are present
    user_turns = [m for m in messages if m["sender"] == "user"]
    assert len(user_turns) == 2
    assert user_turns[0]["message"] == "First question about Python"
    assert user_turns[1]["message"] == "Second question about Docker"

    # resume_id filter: this resume has messages, an unrelated one has none
    res = client.get(f"/api/chat/history?resume_id={resume_id}", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) >= 4
    res = client.get("/api/chat/history?resume_id=999999", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


def test_knowledge_base_has_at_least_40_chunks():
    from app.models.kb import KBChunk

    db = TestingSessionLocal()
    try:
        assert db.query(KBChunk).count() >= 40
    finally:
        db.close()


def test_knowledge_base_ingested_from_json_files():
    """data/kb_data/*.json is the source of truth for first-run ingestion."""
    from app.services.vector_store import load_seed_documents

    docs = load_seed_documents()
    assert len(docs) >= 20
    assert all(d["content"] and d["title"] for d in docs)
    assert {d["source_file"] for d in docs} <= {
        "skills.json", "career_roadmaps.json", "learning_resources.json", "resume_guidelines.json"
    }
    # 2 documents per entry in seed_knowledge_base_if_empty -> well over 40 chunks
    assert len(docs) * 2 >= 40


def test_recommendations_min_score_and_explain_params():
    token, resume_id = _register_and_upload("params@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post(f"/api/resumes/{resume_id}/analyze", headers=headers).status_code == 200

    # min_score filters, explain=false skips the LLM enrichment pass
    res = client.get(
        f"/api/resumes/{resume_id}/recommendations?min_score=85&limit=3&explain=false",
        headers=headers,
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["recommendations"]) <= 3
    assert all(r["match_score"] >= 85 for r in data["recommendations"])

    scores = [r["match_score"] for r in data["recommendations"]]
    assert scores == sorted(scores, reverse=True)
    assert all(isinstance(r["explanation"], str) and r["explanation"] for r in data["recommendations"])

    # Out-of-range parameters are rejected by validation
    assert client.get(f"/api/resumes/{resume_id}/recommendations?min_score=-5", headers=headers).status_code == 422
    assert client.get(f"/api/resumes/{resume_id}/recommendations?limit=0", headers=headers).status_code == 422

def test_improvements_are_personalized_from_analysis():
    """Weaknesses / skill gaps / score must derive from the analysis, not be static."""
    token, resume_id = _register_and_upload("improve@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    assert client.post(f"/api/resumes/{resume_id}/analyze", headers=headers).status_code == 200

    res = client.get(f"/api/resumes/{resume_id}/improvements", headers=headers)
    assert res.status_code == 200
    data = res.json()

    # every required section present
    for key in ("overall_score", "strengths", "weaknesses", "missing_critical_skills",
                "recommended_certifications", "learning_resources",
                "actionable_bullet_improvements"):
        assert key in data
    assert 0 <= data["overall_score"] <= 100

    # skill gaps reflect REAL job-posting demand (count >= 1, descending order)
    gaps = data["missing_critical_skills"]
    assert gaps, "expected missing skills derived from seeded jobs"
    counts = [g["appears_in_job_matches"] for g in gaps]
    assert all(c >= 1 for c in counts)
    assert counts == sorted(counts, reverse=True)
    # the sample resume lists Python/SQL, so those must not be reported as missing
    assert not any(g["skill"].lower() in {"python", "sql"} for g in gaps)

    # certifications and resources are linked to the gaps and use https URLs
    assert data["recommended_certifications"]
    for cert in data["recommended_certifications"]:
        assert cert["link"].startswith("https://")
    for res_item in data["learning_resources"]:
        assert res_item["url"].startswith("https://")

    # bullet suggestions mention a concrete skill from the gap list
    assert any(g["skill"].lower() in " ".join(data["actionable_bullet_improvements"]).lower()
               for g in gaps[:3])

    # scoring is deterministic: same resume -> same score
    res2 = client.get(f"/api/resumes/{resume_id}/improvements", headers=headers)
    assert res2.json()["overall_score"] == data["overall_score"]


# ---------------------------------------------------------------------------
# Phase 7: edge-case resume validation
# ---------------------------------------------------------------------------

def _build_pdf(text: str, trailer_extra: str = "") -> bytes:
    """Minimal one-page PDF with one text-showing operator per line.

    pdfminer only extracts text that a positioning operator (`T*`) separates;
    a raw newline inside a PDF string is invisible to it.
    """
    safe_lines = [ln.replace("\\", "").replace("(", "").replace(")", "")
                  for ln in text.split("\n")]
    stream = "BT\n/F1 11 Tf\n14 TL\n50 760 Td\n"
    stream += "\n".join(f"({ln}) Tj T*" for ln in safe_lines)
    stream += "\nET"
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    out += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R{trailer_extra} >>\n"
    out += f"startxref\n{xref}\n%%EOF"
    return out.encode("latin-1")


def _upload(token: str, filename: str, data: bytes, content_type="application/pdf"):
    return client.post(
        "/api/resumes/upload",
        files={"file": (filename, data, content_type)},
        headers={"Authorization": f"Bearer {token}"},
    )


def test_scanned_pdf_without_extractable_text():
    """Image-only / scanned PDF: valid container, zero extractable characters."""
    token = _register_and_upload("scanned@example.com")[0]
    scanned = _build_pdf("")  # content stream with no text-showing operators
    res = _upload(token, "scanned.pdf", scanned)
    assert res.status_code == 400
    assert "Unable to extract text" in res.json()["detail"]
    # No orphan file is left behind
    assert client.get("/api/resumes", headers={"Authorization": f"Bearer {token}"}).json() == [
        r for r in client.get("/api/resumes", headers={"Authorization": f"Bearer {token}"}).json()
        if r["original_filename"] != "scanned.pdf"
    ]


def test_password_protected_pdf_rejected_with_clear_message():
    token = _register_and_upload("locked@example.com")[0]
    encrypt = (" /Encrypt 6 0 R")
    locked = _build_pdf("Secret locked resume", trailer_extra=encrypt) + (
        b"\n6 0 obj\n<< /Filter /Standard /V 1 /R 2 /P -44 "
        b"/O <0102030405060708090a0b0c0d0e0f10> "
        b"/U <1112131415161718191a1b1c1d1e1f20> >>\nendobj\n"
    )
    res = _upload(token, "protected.pdf", locked)
    assert res.status_code == 400
    assert "password-protected" in res.json()["detail"].lower()


def test_corrupt_pdf_structure_rejected():
    """Passes the %PDF magic-byte check, then fails to parse."""
    token = _register_and_upload("broken@example.com")[0]
    broken = b"%PDF-1.4\n" + b"garbage bytes and no xref table at all\n" + b"%%EOF"
    res = _upload(token, "broken.pdf", broken)
    assert res.status_code == 400
    assert "detail" in res.json()


def test_non_standard_headings_still_parse():
    """Resume using unconventional section headings must still be analyzed."""
    token = _register_and_upload("nonstandard@example.com")[0]
    text = (
        "Alex Rivera\nWhat I've Done\n"
        "Built FastAPI services with Docker and PostgreSQL for four years.\n"
        "Tech Stack: Python, FastAPI, Docker, PostgreSQL, Kubernetes, Git\n"
        "How I Work: Leadership, Communication\n"
        "Schooling: B.S. Computer Science, MIT, 2019\n"
    )
    res = _upload(token, "nonstandard.pdf", _build_pdf(text))
    assert res.status_code == 201
    resume_id = res.json()["id"]
    assert res.json()["parsed_text_snippet"]

    an = client.post(f"/api/resumes/{resume_id}/analyze",
                     headers={"Authorization": f"Bearer {token}"})
    assert an.status_code == 200
    assert an.json()["status"] == "completed"
    skills = an.json()["result"]["technical_skills"]
    assert any(s.lower() == "python" for s in skills)


def test_sparse_resume_with_missing_fields_is_graceful():
    """A resume with almost nothing in it must not crash any downstream agent."""
    token = _register_and_upload("sparse@example.com")[0]
    # Name + one sentence only: no skills section, no education, no metrics.
    text = (
        "Sam Lee\n"
        "Backend Developer\n"
        "I write server-side code and talk to people about requirements."
    )
    res = _upload(token, "sparse.pdf", _build_pdf(text))
    assert res.status_code == 201
    resume_id = res.json()["id"]
    headers = {"Authorization": f"Bearer {token}"}

    an = client.post(f"/api/resumes/{resume_id}/analyze", headers=headers)
    assert an.status_code == 200
    assert an.json()["status"] == "completed"

    rec = client.get(f"/api/resumes/{resume_id}/recommendations?explain=false", headers=headers)
    assert rec.status_code == 200
    assert isinstance(rec.json()["recommendations"], list)

    imp = client.get(f"/api/resumes/{resume_id}/improvements", headers=headers)
    assert imp.status_code == 200
    data = imp.json()
    assert 0 <= data["overall_score"] <= 100
    assert data["strengths"] and data["weaknesses"]

    chat = client.post("/api/chat", json={"resume_id": resume_id, "message": "What should I add?"},
                       headers=headers)
    assert chat.status_code == 200
    assert "Sources:" in chat.json()["reply"]
