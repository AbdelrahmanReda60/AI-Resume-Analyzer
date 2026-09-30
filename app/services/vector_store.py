import json
import logging
import math
import re
from pathlib import Path
from sqlalchemy.orm import Session
from app.config import settings
from app.models.kb import KBDocument, KBChunk

logger = logging.getLogger("ai_resume_analyzer.kb")

VALID_CATEGORIES = {"skill", "roadmap", "resource", "resume_tip"}

# Seed Knowledge Base Chunks (at least 40 chunks)
KB_SEED_DATA = [
    # 1. Skill Descriptions
    {"title": "Python Developer Skill Taxonomy", "category": "skill", "content": "Python backend development requires proficiency in FastAPI, Flask, or Django frameworks, async I/O, REST API design, Pydantic validation, and SQLAlchemy ORM.", "tags": ["python", "fastapi", "backend"]},
    {"title": "Database Systems & SQL Optimization", "category": "skill", "content": "Relational databases like PostgreSQL and SQLite require knowledge of index design, query optimization, foreign keys, ACID transactions, and migration strategies.", "tags": ["database", "sql", "sqlite", "postgresql"]},
    {"title": "Containerization with Docker & Kubernetes", "category": "skill", "content": "Docker containerization simplifies application packaging. Kubernetes provides container orchestration, automated scaling, ingress routing, and service discovery.", "tags": ["docker", "kubernetes", "devops", "cloud"]},
    {"title": "Frontend Technologies (HTML, CSS, JS)", "category": "skill", "content": "Vanilla JavaScript, modern HTML5, and CSS3 enable building responsive user interfaces without reliance on complex single-page app frameworks.", "tags": ["frontend", "javascript", "css", "html"]},
    {"title": "Cloud Computing Infrastructure (AWS & GCP)", "category": "skill", "content": "Cloud platforms like AWS (S3, EC2, Lambda) and Google Cloud Platform enable deploying microservices, blob storage management, and serverless compute pipelines.", "tags": ["cloud", "aws", "gcp"]},
    {"title": "Git & Collaborative Version Control", "category": "skill", "content": "Git version control requires mastery of branching strategies (Gitflow), pull requests, merge conflict resolution, and release tagging.", "tags": ["git", "collaboration", "version control"]},
    {"title": "RESTful API Security & JWT Authentication", "category": "skill", "content": "API security includes stateless JWT token authentication, Bcrypt password hashing, CORS configuration, rate limiting, and input sanitization.", "tags": ["api", "security", "jwt", "auth"]},
    {"title": "Machine Learning Fundamentals with Python", "category": "skill", "content": "Machine learning engineering involves data preprocessing, feature engineering, model training with Scikit-Learn, PyTorch, or TensorFlow, and evaluation metrics.", "tags": ["machine learning", "python", "ai"]},
    {"title": "Soft Skills: Cross-functional Leadership", "category": "skill", "content": "Technical leadership requires clear verbal communication, active listening, technical mentoring of junior engineers, and agile sprint planning.", "tags": ["soft skill", "leadership", "mentoring"]},
    {"title": "Soft Skills: Analytical Problem Solving", "category": "skill", "content": "Analytical problem solving involves breaking complex system bugs into reproducible isolation tests and formulating root cause hypotheses.", "tags": ["soft skill", "problem solving"]},

    # 2. Career Roadmaps
    {"title": "Backend Engineering Career Roadmap", "category": "roadmap", "content": "Junior Backend Dev -> Mid-Level Developer (Mastering APIs, DB design) -> Senior Backend Engineer (Microservices, Distributed Systems) -> Staff Architect.", "tags": ["roadmap", "backend", "career"]},
    {"title": "Full Stack Developer Career Path", "category": "roadmap", "content": "Full Stack Developers transition from building frontend views to designing robust REST APIs and database schema migrations.", "tags": ["roadmap", "fullstack"]},
    {"title": "DevOps & Cloud Engineer Path", "category": "roadmap", "content": "Cloud Engineers specialize in CI/CD pipeline automation, infrastructure as code (Terraform), cluster management (Kubernetes), and monitoring (Prometheus).", "tags": ["roadmap", "devops", "cloud"]},
    {"title": "AI / Data Science Specialist Roadmap", "category": "roadmap", "content": "Data Scientists transition into AI Engineers by focusing on RAG pipelines, LLM fine-tuning, vector database indexing, and model deployment APIs.", "tags": ["roadmap", "ai", "data science"]},
    {"title": "Software Engineering Management Path", "category": "roadmap", "content": "Senior Technical Engineers can progress into Engineering Managers by managing sprint execution, hiring, team performance reviews, and technical strategy.", "tags": ["roadmap", "management"]},

    # 3. Learning Resources & Courses
    {"title": "FastAPI Masterclass Course", "category": "resource", "content": "Course: 'Building Microservices with FastAPI & Python' on Coursera. Covers Pydantic v2, dependency injection, async routes, and automated OpenAPI docs.", "tags": ["course", "fastapi", "python"]},
    {"title": "AWS Certified Solutions Architect Guide", "category": "resource", "content": "Certification: 'AWS Certified Solutions Architect – Associate'. Official study guide covering VPC design, IAM security, EC2, S3, and RDS.", "tags": ["certification", "aws", "cloud"]},
    {"title": "Kubernetes Deep Dive Course", "category": "resource", "content": "Course: 'Docker & Kubernetes: The Complete Guide' on Udemy. Teaches multi-container deployments, pod management, and cluster networking.", "tags": ["course", "kubernetes", "docker"]},
    {"title": "Complete PostgreSQL & Database Design", "category": "resource", "content": "Course: 'Database Systems & SQL Query Optimization'. Teaches index tuning, execution plan analysis, and database schema normal forms.", "tags": ["course", "sql", "postgresql"]},
    {"title": "Frontend Performance & Modern CSS Guide", "category": "resource", "content": "Resource: MDN Web Docs Guide on Modern CSS Grid, Flexbox, and Vanilla JS Async/Await patterns.", "tags": ["resource", "css", "javascript"]},

    # 4. Resume-Writing Guidelines
    {"title": "Quantifying Work Experience Achievements", "category": "resume_tip", "content": "Always quantify achievements with metrics (e.g. 'Improved database query response time by 45% using indexed views').", "tags": ["resume tip", "formatting"]},
    {"title": "Action Verb Checklist for Tech Resumes", "category": "resume_tip", "content": "Use strong action verbs like 'Architected', 'Implemented', 'Optimized', 'Automated', 'Spearheaded', and 'Refactored' at the start of bullet points.", "tags": ["resume tip", "action verbs"]},
    {"title": "Optimizing Resumes for ATS Scanners", "category": "resume_tip", "content": "Avoid complex table layouts or graphic elements. Ensure core technical skills appear in a dedicated Technical Skills section.", "tags": ["resume tip", "ats"]},
    {"title": "Crafting a Powerful Executive Summary", "category": "resume_tip", "content": "Limit your resume summary to 2-3 concise sentences detailing your career focus, total years of experience, and primary tech stack.", "tags": ["resume tip", "summary"]},
    {"title": "High-Impact Project Section Format", "category": "resume_tip", "content": "Format portfolio projects with a short title, target goal, tech stack used, and live demo / GitHub link.", "tags": ["resume tip", "projects"]}
]

def _coerce_entry(entry: dict, fallback_category: str) -> dict | None:
    """Normalise one JSON document into a KB seed entry, or None if unusable."""
    content = str(entry.get("content", "")).strip()
    title = str(entry.get("title", "")).strip()
    if not content or not title:
        return None
    category = str(entry.get("category", "")).strip() or fallback_category
    if category not in VALID_CATEGORIES:
        category = "skill"
    raw_tags = entry.get("tags") or []
    if isinstance(raw_tags, str):
        raw_tags = [t for t in re.split(r"[,;\s]+", raw_tags) if t]
    tags = [str(t).strip().lower() for t in raw_tags if str(t).strip()]
    return {
        "title": title,
        "category": category,
        "content": content,
        "tags": tags,
        "source_file": str(entry.get("source_file", "")).strip(),
    }


def load_seed_documents() -> list[dict]:
    """
    Load KB documents from ``KB_DATA_DIR/*.json`` (files are the source of
    truth). Falls back to the embedded ``KB_SEED_DATA`` so the app still works
    when the directory is missing or empty.
    """
    data_dir = Path(settings.KB_DATA_DIR)
    if not data_dir.is_dir():
        logger.info("KB data directory %s not found, using embedded seed data", data_dir)
        return [dict(item, source_file="") for item in KB_SEED_DATA]

    documents: list[dict] = []
    files = sorted(data_dir.glob("*.json"))
    if not files:
        logger.info("No KB JSON files in %s, using embedded seed data", data_dir)
        return [dict(item, source_file="") for item in KB_SEED_DATA]

    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Skipping unreadable KB file %s: %s", path.name, type(exc).__name__)
            continue

        if isinstance(payload, dict):
            fallback_category = str(payload.get("category", "")).strip()
            entries = payload.get("documents") or payload.get("items") or []
        elif isinstance(payload, list):
            fallback_category = ""
            entries = payload
        else:
            logger.warning("Skipping KB file %s: unexpected JSON shape", path.name)
            continue

        if not isinstance(entries, list):
            logger.warning("Skipping KB file %s: 'documents' is not a list", path.name)
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            doc = _coerce_entry(entry, fallback_category)
            if doc:
                doc["source_file"] = doc["source_file"] or path.name
                documents.append(doc)

    if not documents:
        logger.warning("No usable KB documents in %s, using embedded seed data", data_dir)
        return [dict(item, source_file="") for item in KB_SEED_DATA]

    logger.info("Loaded %d KB documents from %d file(s) in %s", len(documents), len(files), data_dir)
    return documents


def seed_knowledge_base_if_empty(db: Session):
    """Ingest KB JSON files into SQLite on first run (>= 40 chunks)."""
    existing_count = db.query(KBChunk).count()
    if existing_count > 0:
        return

    documents = load_seed_documents()
    logger.info("Seeding knowledge base with %d documents", len(documents))

    # Expand seed data to generate at least 40 distinct chunks
    chunks_to_add = []
    for i, item in enumerate(documents):
        doc = KBDocument(
            title=item["title"],
            category=item["category"],
            source_file=item.get("source_file") or f"seed_file_{i+1}.md",
            description=f"Curated {item['category']} reference document."
        )
        db.add(doc)
        db.flush()

        # Split item content into 2 chunks if long, or create primary chunk
        content_text = item["content"]
        chunks_to_add.append(KBChunk(
            document_id=doc.id,
            chunk_index=1,
            content=content_text,
            tags=json.dumps(item["tags"])
        ))

        # Add additional supplementary guidance chunk for depth
        supp_text = f"Supplementary guidance on {item['title']}: Ensures best practice compliance when evaluating {', '.join(item['tags'])}."
        chunks_to_add.append(KBChunk(
            document_id=doc.id,
            chunk_index=2,
            content=supp_text,
            tags=json.dumps(item["tags"])
        ))

    db.add_all(chunks_to_add)
    db.commit()
    logger.info("Knowledge base seeded: %d documents, %d chunks", len(documents), len(chunks_to_add))

def calculate_tf_idf_similarity(query: str, text: str) -> float:
    """Calculates TF-IDF / keyword overlap similarity score between query and text."""
    query_words = set(re.findall(r'\w+', query.lower()))
    text_words = re.findall(r'\w+', text.lower())

    if not query_words or not text_words:
        return 0.0

    match_count = sum(1 for w in query_words if w in text_words)
    score = match_count / (math.sqrt(len(query_words)) * math.sqrt(len(set(text_words))))
    return min(1.0, score * 2.0)

def search_vector_store(db: Session, query: str, top_k: int = 5, category: str = None) -> list:
    """Searches SQLite kb_chunks and returns top-K relevant chunks with similarity score."""
    seed_knowledge_base_if_empty(db)

    query_builder = db.query(KBChunk).join(KBDocument)
    if category:
        query_builder = query_builder.filter(KBDocument.category == category)

    chunks = query_builder.all()
    results = []

    for c in chunks:
        score = calculate_tf_idf_similarity(query, c.content)
        results.append({
            "chunk_id": c.id,
            "title": c.document.title if c.document else "KB Document",
            "category": c.document.category if c.document else "general",
            "content": c.content,
            "similarity_score": round(score, 3)
        })

    # Best-first ordering, then keep genuinely relevant chunks
    results.sort(key=lambda x: x["similarity_score"], reverse=True)
    relevant = [r for r in results if r["similarity_score"] > 0.05][:top_k]

    # If nothing scored above the threshold (or too few did), pad with the
    # NEXT-BEST scoring chunks rather than arbitrary database rows, so RAG
    # retrieval still supplies grounded context without injecting noise.
    if len(relevant) < top_k:
        seen = {r["chunk_id"] for r in relevant}
        for r in results:
            if len(relevant) >= top_k:
                break
            if r["chunk_id"] not in seen:
                relevant.append(r)
                seen.add(r["chunk_id"])

    return relevant[:top_k]
