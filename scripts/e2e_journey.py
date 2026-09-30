"""
End-to-end journey check against a LIVE server.

Run the server first, then:

    python3 scripts/e2e_journey.py [base_url]

Covers: register -> login -> upload (validation + happy path) -> analyze ->
recommendations -> improvements -> chat -> job CRUD/search/pagination ->
KB search -> ownership 404s -> unauthenticated 401s -> delete -> logout.

Exits 0 only when every step passes.
"""
import json
import sys
import urllib.error
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
STEPS = []

def log(ok, label, extra=""):
    STEPS.append((ok, label, extra))
    print(("  OK  " if ok else " FAIL ") + label + (" :: " + str(extra) if extra else ""))

def req(method, path, data=None, token=None, raw=None, ctype=None, timeout=180):
    headers = {}
    if token:
        headers["Authorization"] = "Bearer " + token
    body = None
    if raw is not None:
        body = raw
        headers["Content-Type"] = ctype
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    r = urllib.request.Request(BASE + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            payload = resp.read()
            try:
                return resp.status, json.loads(payload or b"null")
            except json.JSONDecodeError:
                return resp.status, payload
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None

def make_pdf(text):
    lines = text.split("\n")
    ops = ["BT", "/F1 11 Tf", "14 TL", "50 760 Td"]
    for line in lines:
        safe = line.replace("\\", "").replace("(", "").replace(")", "")
        ops.append(f"({safe}) Tj")
        ops.append("T*")
    ops.append("ET")
    stream = "\n".join(ops)
    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objs)+1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    out += f"trailer\n<< /Size {len(objs)+1} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    return out.encode("latin-1")

RESUME_TEXT = """Jane Doe
Senior Software Engineer
Email: jane.doe@example.com | Phone: +1-555-0199 | Location: San Francisco, CA

Summary
Results-oriented Senior Software Engineer with 6 years of experience building
microservices, REST APIs and scalable backend platforms with Python, FastAPI,
Docker, PostgreSQL and AWS.

Technical Skills
Python, FastAPI, Flask, Docker, Kubernetes, PostgreSQL, SQL, REST APIs,
Git, AWS, Linux, JavaScript, HTML, CSS

Soft Skills
Leadership, Communication, Problem Solving, Teamwork, Agile

Experience
TechStream Solutions - Senior Backend Developer (2022 - Present)
- Architected RESTful microservices processing 10M daily transactions.
- Optimized SQL query performance reducing endpoint latency by 45%.
- Mentored four junior developers through code review and pairing.

DataPulse Inc - Software Developer (2020 - 2022)
- Developed backend features using Python and Flask.
- Integrated third-party payment gateways and webhook services.

Education
University of California, Berkeley - B.S. in Computer Science - 2020
"""

def _headers(url):
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return {k.lower(): v for k, v in resp.headers.items()}


def main():
    # 0. Hardening headers present on static + API responses
    try:
        h = _headers(BASE + "/")
        log(h.get("x-content-type-options") == "nosniff"
            and h.get("x-frame-options") == "DENY"
            and h.get("referrer-policy") == "same-origin",
            "security headers on /", str({k: h.get(k) for k in
                ("x-content-type-options", "x-frame-options", "referrer-policy")}))
    except Exception as exc:  # noqa: BLE001
        log(False, "security headers on /", type(exc).__name__)

    tag = uuid.uuid4().hex[:6]
    email = f"journey_{tag}@example.com"

    # --- 1. Register ---
    s, b = req("POST", "/api/auth/register",
               {"email": email, "password": "Passw0rd!x", "full_name": "Journey Tester"})
    token = b.get("access_token") if isinstance(b, dict) else None
    log(s == 201 and token, "register", f"status={s}")
    if not token:
        return finish()

    # duplicate register
    s2, b2 = req("POST", "/api/auth/register",
                 {"email": email, "password": "Passw0rd!x", "full_name": "Dup"})
    log(s2 == 400 and "detail" in b2, "duplicate register rejected", f"status={s2} {b2}")

    # --- 2. Login ---
    s, b = req("POST", "/api/auth/login", {"email": email, "password": "Passw0rd!x"})
    log(s == 200 and b.get("access_token"), "login", f"status={s}")
    token = b.get("access_token") or token

    s, b = req("POST", "/api/auth/login", {"email": email, "password": "wrongpass"})
    log(s == 401 and "detail" in b, "bad login -> 401 detail", f"status={s} {b}")

    s, b = req("GET", "/api/auth/me", token=token)
    log(s == 200 and b.get("email") == email, "GET /api/auth/me", f"status={s}")

    # --- 3. Upload validation ---
    s, b = req("POST", "/api/resumes/upload", token=token,
               raw=b"plain text", ctype="text/plain")
    # wrong extension -> 400 (multipart filename test.txt)
    wrong = multipart("bad.txt", b"hello", "text/plain")
    s, b = req("POST", "/api/resumes/upload", token=token, raw=wrong, ctype="multipart/form-data; boundary=XYZ")
    log(s == 400 and "detail" in b, "upload .txt rejected", f"status={s}")

    corrupt = multipart("fake.pdf", b"NOTAPDF" * 20, "application/pdf")
    s, b = req("POST", "/api/resumes/upload", token=token, raw=corrupt, ctype="multipart/form-data; boundary=XYZ")
    log(s == 400 and "detail" in b, "corrupt pdf rejected", f"status={s} {b}")

    empty = multipart("empty.pdf", b"", "application/pdf")
    s, b = req("POST", "/api/resumes/upload", token=token, raw=empty, ctype="multipart/form-data; boundary=XYZ")
    log(s == 400 and "detail" in b, "empty file rejected", f"status={s} {b}")

    # --- 4. Valid upload ---
    pdf = make_pdf(RESUME_TEXT)
    up = multipart("Jane_Doe_Resume.pdf", pdf, "application/pdf")
    s, b = req("POST", "/api/resumes/upload", token=token, raw=up,
               ctype="multipart/form-data; boundary=XYZ")
    log(s == 201 and b.get("id"), "upload valid pdf", f"status={s} {b if s!=201 else ''}")
    if s != 201:
        return finish()
    rid = b["id"]
    log(b.get("file_type") == "pdf" and b.get("parsed_text_snippet"), "upload response fields", f"keys={sorted(b.keys())}")

    # --- 5. Analyze ---
    s, b = req("POST", f"/api/resumes/{rid}/analyze", token=token, timeout=180)
    ok = s == 200 and b.get("status") == "completed" and b.get("result", {}).get("technical_skills")
    log(ok, "analyze resume", f"status={s} skills={len(b.get('result',{}).get('technical_skills',[])) if isinstance(b,dict) else '?'}")
    if not ok:
        return finish()

    s, b2 = req("GET", f"/api/resumes/{rid}/analysis", token=token)
    log(s == 200 and b2.get("result", {}).get("full_name"), "get analysis", f"status={s}")

    # --- 6. Recommendations ---
    s, b = req("GET", f"/api/resumes/{rid}/recommendations?min_score=0&limit=5", token=token, timeout=180)
    recs = b.get("recommendations", []) if isinstance(b, dict) else []
    log(s == 200 and len(recs) > 0, "recommendations", f"count={len(recs)} total={b.get('total_matched') if isinstance(b,dict) else '?'}")
    if recs:
        top = recs[0]
        log(0 <= top.get("match_score", -1) <= 100 and top.get("explanation")
            and top.get("matched_technical_skills") is not None
            and top.get("missing_technical_skills") is not None
            and top.get("experience_fit") and top.get("education_fit"),
            "recommendation shape (score/explanation/skills/fits)",
            f"score={top.get('match_score')} grade={top.get('match_grade')}")
        log(all(isinstance(r.get("match_score"), int) for r in recs),
            "recommendations sorted high->low",
            f"scores={[r.get('match_score') for r in recs]}")

    # --- 7. Improvements ---
    s, b = req("GET", f"/api/resumes/{rid}/improvements", token=token, timeout=180)
    keys = sorted(b.keys()) if isinstance(b, dict) else []
    log(s == 200 and all(k in b for k in
        ["overall_score", "strengths", "weaknesses", "missing_critical_skills",
         "recommended_certifications", "learning_resources", "actionable_bullet_improvements"]),
        "improvements sections", f"keys={keys}")

    # --- 8. Chat ---
    s, b = req("POST", "/api/chat",
               {"resume_id": rid, "message": "What Kubernetes projects should I build?"}, token=token, timeout=180)
    log(s == 200 and b.get("reply") and b.get("suggested_followups") is not None,
        "chat message", f"status={s}")
    reply = b.get("reply", "") if isinstance(b, dict) else ""
    log("Source" in reply or "source" in reply, "chat reply cites retrieved sources",
        reply[-140:].replace("\n", " "))

    s, b = req("POST", "/api/chat", {"resume_id": rid, "message": "And what certification do you recommend?"}, token=token, timeout=180)
    log(s == 200, "second chat turn", f"status={s}")

    s, b = req("GET", f"/api/chat/history?limit=10", token=token)
    log(s == 200 and len(b) >= 4, "chat history (latest first window)",
        f"count={len(b) if isinstance(b,list) else '?'}")

    s, b = req("GET", "/api/chat/history?resume_id=999999", token=token)
    log(s == 200 and len(b) == 0, "history resume_id filter", f"count={len(b) if isinstance(b,list) else '?'}")

    # --- 9. Job CRUD + search ---
    s, b = req("GET", "/api/jobs?limit=100")
    total = b.get("total", 0) if isinstance(b, dict) else 0
    log(s == 200 and total >= 20, "seeded jobs >= 20", f"total={total}")

    s, b = req("GET", "/api/jobs?title=Python&limit=5")
    log(s == 200 and b.get("total", 0) > 0, "search by title", f"total={b.get('total')}")
    s, b = req("GET", "/api/jobs?experience_level=Senior&limit=5")
    log(s == 200 and b.get("total", 0) > 0, "search by experience_level", f"total={b.get('total')}")
    s, b = req("GET", "/api/jobs?job_type=Remote&limit=5")
    log(s == 200, "search by job_type", f"total={b.get('total')}")
    s, b = req("GET", "/api/jobs?limit=5&offset=0")
    log(s == 200 and len(b.get("jobs", [])) <= 5, "pagination limit", f"count={len(b.get('jobs',[]))}")

    job_payload = {
        "title": "Journey FastAPI Engineer", "company": "JourneyCo", "location": "Remote",
        "job_type": "Full-time", "experience_level": "Mid", "min_years_experience": 2,
        "required_degree": "Bachelor",
        "description": "Build FastAPI microservices with PostgreSQL and Docker.",
        "required_skills": ["Python", "FastAPI", "Docker"], "soft_skills": ["Communication"],
        "salary_range": "$120,000 - $150,000",
    }
    s, b = req("POST", "/api/jobs", job_payload, token=token)
    log(s == 201 and b.get("id"), "create job", f"status={s}")
    jid = b.get("id") if isinstance(b, dict) else None

    s, b = req("PUT", f"/api/jobs/{jid}", {"location": "Berlin, DE"}, token=token)
    log(s == 200 and b.get("location") == "Berlin, DE", "update job", f"status={s}")

    s, b = req("DELETE", f"/api/jobs/{jid}", token=token)
    log(s == 200 and "detail" in b, "delete job", f"status={s}")
    s, b = req("GET", f"/api/jobs/{jid}")
    log(s == 404, "deleted job -> 404", f"status={s}")

    s, b = req("POST", "/api/jobs", job_payload)
    log(s == 401 and "detail" in b, "job create without token -> 401", f"status={s}")

    # --- 10. KB search (auth required) ---
    s, b = req("GET", "/api/kb/search?q=FastAPI")
    log(s == 401, "kb search without token -> 401", f"status={s}")
    s, b = req("GET", "/api/kb/search?q=Kubernetes+learning&limit=3", token=token)
    log(s == 200 and b.get("total_results", 0) > 0, "kb search", f"results={b.get('total_results')}")

    # --- 11. Ownership: second user cannot touch first user's resume ---
    s, b = req("POST", "/api/auth/register",
               {"email": f"other_{tag}@example.com", "password": "Passw0rd!x", "full_name": "Other"})
    other = b.get("access_token")
    log(s == 201 and other, "second user register", f"status={s}")
    for label, method, path in [
        ("get", "GET", f"/api/resumes/{rid}"),
        ("analyze", "POST", f"/api/resumes/{rid}/analyze"),
        ("delete", "DELETE", f"/api/resumes/{rid}"),
        ("analysis", "GET", f"/api/resumes/{rid}/analysis"),
        ("recommendations", "GET", f"/api/resumes/{rid}/recommendations"),
        ("improvements", "GET", f"/api/resumes/{rid}/improvements"),
    ]:
        s, b = req(method, path, token=other, timeout=60)
        log(s == 404, f"ownership: foreign {label} -> 404", f"status={s}")

    s, b = req("POST", "/api/chat", {"resume_id": rid, "message": "hi"}, token=other, timeout=60)
    log(s == 404, "ownership: foreign resume in chat -> 404", f"status={s}")

    # --- 12. Unauthenticated access ---
    for path in ["/api/resumes", "/api/chat/history", "/api/kb/search?q=a"]:
        s, b = req("GET", path)
        log(s == 401, f"unauthenticated {path} -> 401", f"status={s}")

    # --- 13. Delete resume ---
    s, b = req("DELETE", f"/api/resumes/{rid}", token=token)
    log(s == 200, "delete own resume", f"status={s}")
    s, b = req("GET", f"/api/resumes/{rid}", token=token)
    log(s == 404, "deleted resume -> 404", f"status={s}")

    # --- 14. Clear chat + logout ---
    s, b = req("DELETE", "/api/chat/history", token=token)
    log(s == 200 and "detail" in b, "clear chat history", f"status={s}")
    s, b = req("POST", "/api/auth/logout", token=token)
    log(s == 200 and "detail" in b, "logout", f"status={s}")

    return finish()


def multipart(filename, content, content_type):
    boundary = "XYZ"
    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    parts.append(content)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    return b"".join(parts)


def finish():
    failed = [s for s in STEPS if not s[0]]
    print(f"\n=== {len(STEPS) - len(failed)}/{len(STEPS)} steps passed ===")
    if failed:
        print("FAILED:")
        for _, label, extra in failed:
            print("  -", label, extra)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
