import json
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.job import Job
from app.schemas.job import JobCreate, JobUpdate, JobResponse, JobListResponse
from app.api.deps import get_current_user_optional, get_current_user
from app.models.user import User

router = APIRouter(prefix="/jobs", tags=["Jobs"])

SEED_JOBS_DATA = [
    {"title": "Senior Python Backend Engineer", "company": "CloudScale Systems", "location": "Remote / San Francisco, CA", "job_type": "Full-time", "experience_level": "Senior", "min_years_experience": 4, "required_degree": "Bachelor", "description": "Build high-throughput RESTful microservices and asynchronous data pipelines using Python, FastAPI, Docker, and PostgreSQL.", "required_skills": ["Python", "FastAPI", "Docker", "PostgreSQL", "REST APIs"], "soft_skills": ["Problem Solving", "Teamwork"], "salary_range": "$130,000 - $160,000"},
    {"title": "Full Stack Software Developer", "company": "TechStream Solutions", "location": "Austin, TX", "job_type": "Full-time", "experience_level": "Mid", "min_years_experience": 3, "required_degree": "Bachelor", "description": "Develop full-stack web applications with Python FastAPI backend and modern vanilla JS/CSS frontend interface.", "required_skills": ["Python", "JavaScript", "HTML", "CSS", "SQL"], "soft_skills": ["Communication", "Agile"], "salary_range": "$100,000 - $130,000"},
    {"title": "DevOps & Cloud Systems Engineer", "company": "Nexus Cloud Labs", "location": "Remote / Seattle, WA", "job_type": "Remote", "experience_level": "Senior", "min_years_experience": 5, "required_degree": "Bachelor", "description": "Automate cloud infrastructure deployments using Terraform, Docker, Kubernetes clusters, and AWS/GCP pipelines.", "required_skills": ["Docker", "Kubernetes", "AWS", "Linux", "Git"], "soft_skills": ["Leadership", "Troubleshooting"], "salary_range": "$140,000 - $175,000"},
    {"title": "Data Scientist & AI Specialist", "company": "Apex Analytics Inc.", "location": "New York, NY", "job_type": "Full-time", "experience_level": "Mid", "min_years_experience": 3, "required_degree": "Master", "description": "Build predictive models and natural language processing RAG pipelines using Python, PyTorch, Scikit-Learn, and vector databases.", "required_skills": ["Python", "Machine Learning", "SQL", "PyTorch", "RAG"], "soft_skills": ["Analytical Thinking", "Research"], "salary_range": "$125,000 - $155,000"},
    {"title": "Frontend UI Developer", "company": "PixelCraft Media", "location": "Chicago, IL", "job_type": "Full-time", "experience_level": "Mid", "min_years_experience": 2, "required_degree": "Bachelor", "description": "Craft responsive, accessible web interfaces using semantic HTML5, modern CSS Grid/Flexbox, and performance-optimized Vanilla JavaScript.", "required_skills": ["JavaScript", "HTML", "CSS", "REST APIs"], "soft_skills": ["Design Sense", "Attention to Detail"], "salary_range": "$90,000 - $115,000"},
    {"title": "Junior Backend Developer", "company": "StartUp Catalyst", "location": "Remote / Denver, CO", "job_type": "Full-time", "experience_level": "Entry", "min_years_experience": 1, "required_degree": "Bachelor", "description": "Great entry-level role for developers proficient in Python, SQL, and REST API development. Mentorship provided.", "required_skills": ["Python", "SQL", "Git"], "soft_skills": ["Curiosity", "Fast Learner"], "salary_range": "$75,000 - $90,000"},
    {"title": "Cybersecurity Analyst & Engineer", "company": "ShieldGuard Security", "location": "Washington, DC", "job_type": "Full-time", "experience_level": "Mid", "min_years_experience": 3, "required_degree": "Bachelor", "description": "Audit network security posture, implement JWT authentication standards, and prevent web vulnerability vectors (XSS, SQLi).", "required_skills": ["Security", "Linux", "Python", "JWT"], "soft_skills": ["Vigilance", "Ethics"], "salary_range": "$110,000 - $140,000"},
    {"title": "Database Administrator (DBA)", "company": "DataFortress Enterprise", "location": "Boston, MA", "job_type": "Full-time", "experience_level": "Senior", "min_years_experience": 5, "required_degree": "Bachelor", "description": "Manage enterprise relational database clusters (PostgreSQL, SQLite), optimize query performance, and ensure ACID reliability.", "required_skills": ["PostgreSQL", "SQL", "SQLite", "Linux"], "soft_skills": ["Reliability", "Optimization"], "salary_range": "$135,000 - $165,000"},
    {"title": "Machine Learning Operations (MLOps) Engineer", "company": "Cognitive AI Systems", "location": "Remote / San Jose, CA", "job_type": "Remote", "experience_level": "Senior", "min_years_experience": 4, "required_degree": "Master", "description": "Deploy and monitor production LLM applications, manage vector databases, and scale AI inference microservices.", "required_skills": ["Python", "Docker", "Kubernetes", "Machine Learning", "AWS"], "soft_skills": ["Cross-functional Leadership"], "salary_range": "$150,000 - $185,000"},
    {"title": "Software Quality Assurance (QA) Automation Engineer", "company": "QualityFirst Tech", "location": "Atlanta, GA", "job_type": "Full-time", "experience_level": "Mid", "min_years_experience": 2, "required_degree": "Bachelor", "description": "Develop automated end-to-end integration tests for Python FastAPI REST APIs using pytest and HTTP client frameworks.", "required_skills": ["Python", "pytest", "REST APIs", "Git"], "soft_skills": ["Precision", "Communication"], "salary_range": "$85,000 - $110,000"},
    {"title": "Cloud Solutions Architect", "company": "Skyline Enterprise Cloud", "location": "Dallas, TX", "job_type": "Full-time", "experience_level": "Senior", "min_years_experience": 6, "required_degree": "Bachelor", "description": "Design high-availability cloud architecture for Fortune 500 enterprise clients utilizing AWS, Docker microservices, and Kubernetes.", "required_skills": ["AWS", "Docker", "Kubernetes", "Architecture"], "soft_skills": ["Executive Presentation", "Strategy"], "salary_range": "$165,000 - $200,000"},
    {"title": "Site Reliability Engineer (SRE)", "company": "Uptime Velocity", "location": "Remote / Portland, OR", "job_type": "Remote", "experience_level": "Senior", "min_years_experience": 4, "required_degree": "Bachelor", "description": "Maintain 99.99% service availability, build automated incident recovery tools in Python, and monitor system metrics.", "required_skills": ["Python", "Linux", "Docker", "Kubernetes"], "soft_skills": ["Calm Under Pressure"], "salary_range": "$140,000 - $170,000"},
    {"title": "Technical Product Manager", "company": "Innovate Labs", "location": "San Francisco, CA", "job_type": "Full-time", "experience_level": "Mid", "min_years_experience": 3, "required_degree": "Bachelor", "description": "Bridge technical software development teams and business goals. Define REST API specs and agile feature roadmaps.", "required_skills": ["Agile", "REST APIs", "Product Roadmap"], "soft_skills": ["Stakeholder Management", "Leadership"], "salary_range": "$130,000 - $160,000"},
    {"title": "Python Developer (Contract)", "company": "FlexiCode Services", "location": "Remote", "job_type": "Contract", "experience_level": "Mid", "min_years_experience": 3, "required_degree": "Bachelor", "description": "6-month contract building custom web scrapers, REST API integrations, and SQLite data ingestion scripts.", "required_skills": ["Python", "FastAPI", "SQLite", "REST APIs"], "soft_skills": ["Autonomy", "Speed"], "salary_range": "$60 - $80 / hr"},
    {"title": "AI Research Scientist", "company": "DeepMind Frontiers", "location": "Remote / Palo Alto, CA", "job_type": "Full-time", "experience_level": "Senior", "min_years_experience": 5, "required_degree": "Doctorate", "description": "Conduct frontier AI research in retrieval-augmented generation, multi-agent frameworks, and vector search embeddings.", "required_skills": ["Python", "Machine Learning", "PyTorch", "AI"], "soft_skills": ["Innovation", "Writing"], "salary_range": "$180,000 - $240,000"},
    {"title": "Systems Software Engineer (C++ / Python)", "company": "CoreEngine Dynamics", "location": "San Diego, CA", "job_type": "Full-time", "experience_level": "Mid", "min_years_experience": 3, "required_degree": "Bachelor", "description": "Develop high-performance systems software, low-latency streaming modules, and Python binding wrappers.", "required_skills": ["Python", "C++", "Linux"], "soft_skills": ["Problem Solving"], "salary_range": "$120,000 - $150,000"},
    {"title": "Junior Web Developer", "company": "Digital Reach Agency", "location": "Miami, FL", "job_type": "Full-time", "experience_level": "Entry", "min_years_experience": 1, "required_degree": "Bachelor", "description": "Build client marketing landing pages and form integration handlers using HTML, CSS, JavaScript, and basic Python.", "required_skills": ["HTML", "CSS", "JavaScript"], "soft_skills": ["Teamwork", "Enthusiasm"], "salary_range": "$65,000 - $80,000"},
    {"title": "Lead API Architect", "company": "ConnectSphere", "location": "Remote / Phoenix, AZ", "job_type": "Remote", "experience_level": "Senior", "min_years_experience": 6, "required_degree": "Bachelor", "description": "Architect public RESTful and GraphQL APIs handling millions of daily external requests with strict rate-limiting.", "required_skills": ["Python", "FastAPI", "PostgreSQL", "REST APIs", "Security"], "soft_skills": ["Architecture Design"], "salary_range": "$160,000 - $195,000"},
    {"title": "Data Pipeline Engineer", "company": "StreamData Inc.", "location": "Raleigh, NC", "job_type": "Full-time", "experience_level": "Mid", "min_years_experience": 3, "required_degree": "Bachelor", "description": "Build scalable ETL data pipelines, JSON payload parsers, and database transformation scripts using Python and SQL.", "required_skills": ["Python", "SQL", "PostgreSQL", "Docker"], "soft_skills": ["Data Accuracy"], "salary_range": "$110,000 - $135,000"},
    {"title": "Application Security Engineer", "company": "CyberArmor", "location": "Remote / Salt Lake City, UT", "job_type": "Remote", "experience_level": "Mid", "min_years_experience": 3, "required_degree": "Bachelor", "description": "Conduct automated code security scans, enforce JWT token security policies, and secure SQLite database file permissions.", "required_skills": ["Security", "Python", "JWT", "Linux"], "soft_skills": ["Communication"], "salary_range": "$120,000 - $150,000"}
]

def seed_jobs_if_empty(db: Session):
    if db.query(Job).count() > 0:
        return
    for item in SEED_JOBS_DATA:
        job = Job(
            title=item["title"],
            company=item["company"],
            location=item["location"],
            job_type=item["job_type"],
            experience_level=item["experience_level"],
            min_years_experience=item["min_years_experience"],
            required_degree=item["required_degree"],
            description=item["description"],
            required_skills=json.dumps(item["required_skills"]),
            soft_skills=json.dumps(item["soft_skills"]),
            salary_range=item["salary_range"]
        )
        db.add(job)
    db.commit()

@router.get("", response_model=JobListResponse)
def list_jobs(
    title: str = Query(None),
    skill: str = Query(None),
    location: str = Query(None),
    job_type: str = Query(None),
    experience_level: str = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    seed_jobs_if_empty(db)
    q = db.query(Job).filter(Job.is_active == True)

    if title:
        q = q.filter(Job.title.ilike(f"%{title}%") | Job.description.ilike(f"%{title}%"))
    if skill:
        q = q.filter(Job.required_skills.ilike(f"%{skill}%"))
    if location:
        q = q.filter(Job.location.ilike(f"%{location}%"))
    if job_type:
        q = q.filter(Job.job_type.ilike(f"%{job_type}%"))
    if experience_level:
        q = q.filter(Job.experience_level.ilike(f"%{experience_level}%"))

    total = q.count()
    jobs = q.order_by(Job.created_at.desc()).offset(offset).limit(limit).all()

    formatted_jobs = []
    for j in jobs:
        req_skills = json.loads(j.required_skills) if j.required_skills else []
        soft_skills = json.loads(j.soft_skills) if j.soft_skills else []
        formatted_jobs.append(JobResponse(
            id=j.id,
            title=j.title,
            company=j.company,
            location=j.location,
            job_type=j.job_type,
            experience_level=j.experience_level,
            min_years_experience=j.min_years_experience,
            required_degree=j.required_degree,
            description=j.description,
            required_skills=req_skills,
            soft_skills=soft_skills,
            salary_range=j.salary_range,
            is_active=j.is_active,
            created_at=j.created_at
        ))

    return JobListResponse(total=total, jobs=formatted_jobs)

@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    seed_jobs_if_empty(db)
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting with ID {job_id} not found."
        )

    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        job_type=job.job_type,
        experience_level=job.experience_level,
        min_years_experience=job.min_years_experience,
        required_degree=job.required_degree,
        description=job.description,
        required_skills=json.loads(job.required_skills) if job.required_skills else [],
        soft_skills=json.loads(job.soft_skills) if job.soft_skills else [],
        salary_range=job.salary_range,
        is_active=job.is_active,
        created_at=job.created_at
    )

@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
def create_job(
    job_data: JobCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_job = Job(
        title=job_data.title,
        company=job_data.company,
        location=job_data.location,
        job_type=job_data.job_type,
        experience_level=job_data.experience_level,
        min_years_experience=job_data.min_years_experience,
        required_degree=job_data.required_degree,
        description=job_data.description,
        required_skills=json.dumps(job_data.required_skills),
        soft_skills=json.dumps(job_data.soft_skills or []),
        salary_range=job_data.salary_range
    )
    db.add(new_job)
    db.commit()
    db.refresh(new_job)

    return JobResponse(
        id=new_job.id,
        title=new_job.title,
        company=new_job.company,
        location=new_job.location,
        job_type=new_job.job_type,
        experience_level=new_job.experience_level,
        min_years_experience=new_job.min_years_experience,
        required_degree=new_job.required_degree,
        description=new_job.description,
        required_skills=job_data.required_skills,
        soft_skills=job_data.soft_skills or [],
        salary_range=new_job.salary_range,
        is_active=new_job.is_active,
        created_at=new_job.created_at
    )

@router.put("/{job_id}", response_model=JobResponse)
def update_job(
    job_id: int,
    job_data: JobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job posting with ID {job_id} not found."
        )

    if job_data.title is not None: job.title = job_data.title
    if job_data.company is not None: job.company = job_data.company
    if job_data.location is not None: job.location = job_data.location
    if job_data.job_type is not None: job.job_type = job_data.job_type
    if job_data.experience_level is not None: job.experience_level = job_data.experience_level
    if job_data.min_years_experience is not None: job.min_years_experience = job_data.min_years_experience
    if job_data.required_degree is not None: job.required_degree = job_data.required_degree
    if job_data.description is not None: job.description = job_data.description
    if job_data.required_skills is not None: job.required_skills = json.dumps(job_data.required_skills)
    if job_data.soft_skills is not None: job.soft_skills = json.dumps(job_data.soft_skills)
    if job_data.salary_range is not None: job.salary_range = job_data.salary_range

    db.commit()
    db.refresh(job)

    return JobResponse(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        job_type=job.job_type,
        experience_level=job.experience_level,
        min_years_experience=job.min_years_experience,
        required_degree=job.required_degree,
        description=job.description,
        required_skills=json.loads(job.required_skills) if job.required_skills else [],
        soft_skills=json.loads(job.soft_skills) if job.soft_skills else [],
        salary_range=job.salary_range,
        is_active=job.is_active,
        created_at=job.created_at
    )

@router.delete("/{job_id}")
def delete_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job posting not found."
        )

    db.delete(job)
    db.commit()
    return {"detail": "Job posting deleted successfully."}
