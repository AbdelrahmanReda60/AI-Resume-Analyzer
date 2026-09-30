/* Mock data for demoing the AI Resume Analyzer without a backend.
   Set USE_MOCK=true in config.js to use these stub responses.
*/

var mock = {
  auth: {
    register: function(userData) {
      var token = "mock-jwt-token-" + Math.random().toString(36).substring(2, 15);
      var user = {
        id: 1,
        email: userData.email,
        full_name: userData.full_name,
        created_at: new Date().toISOString()
      };
      return { user: user, access_token: token, token_type: "bearer" };
    },
    login: function(credentials) {
      var token = "mock-jwt-token-" + Math.random().toString(36).substring(2, 15);
      var user = {
        id: 1,
        email: credentials.email,
        full_name: "Test User",
        created_at: new Date().toISOString()
      };
      return { user: user, access_token: token, token_type: "bearer" };
    },
    logout: function() { return { detail: "Successfully logged out." }; },
    me: function() {
      return {
        id: 1,
        email: "user@example.com",
        full_name: "Test User",
        created_at: new Date().toISOString()
      };
    }
  },
  resumes: {
    upload: function(file, title) {
      return {
        id: 1,
        user_id: 1,
        title: title || "My Resume",
        filename: "resumes/uuid-test-resume.pdf",
        original_filename: "Test_Resume.pdf",
        file_type: "pdf",
        file_size: 245800,
        parsed_text_snippet: "Jane Doe | Senior Software Engineer | jane.doe@example.com | 555-0199...",
        created_at: new Date().toISOString()
      };
    },
    list: [
      {
        id: 1,
        title: "Software Engineer Resume 2026",
        original_filename: "Software_Engineer_Resume.pdf",
        file_type: "pdf",
        created_at: new Date().toISOString(),
        has_analysis: true
      }
    ],
    get: function(resumeId) {
      return {
        id: resumeId,
        user_id: 1,
        title: "Software Engineer Resume 2026",
        original_filename: "Software_Engineer_Resume.pdf",
        file_type: "pdf",
        parsed_text: "Jane Doe\nSenior Software Engineer\nEmail: jane.doe@example.com...",
        created_at: new Date().toISOString()
      };
    },
    delete: function() { return { detail: "Resume and associated analyses deleted successfully." }; },
    analyze: function(resumeId) {
      return {
        id: 5,
        resume_id: resumeId,
        status: "completed",
        created_at: new Date().toISOString(),
        result: {
          full_name: "Jane Doe",
          email: "jane.doe@example.com",
          phone: "+1-555-0199",
          location: "San Francisco, CA",
          summary: "Results-oriented Senior Software Engineer with 6 years of experience building high-concurrency microservices, REST APIs, and scalable backend platforms using Python and Cloud services.",
          technical_skills: ["Python", "FastAPI", "PostgreSQL", "Docker", "REST APIs", "Git", "AWS (S3, EC2)"],
          soft_skills: ["Leadership", "Cross-functional Collaboration", "Problem Solving", "Agile Methodology"],
          education: [
            { degree: "B.S. in Computer Science", institution: "University of California, Berkeley", year: "2020" }
          ],
          experience: [
            {
              company: "TechStream Solutions",
              role: "Senior Backend Developer",
              duration: "2022 - Present",
              responsibilities: [
                "Architected RESTful microservices processing 10M daily transactions.",
                "Optimized SQL query performance reducing endpoint latency by 45%."
              ]
            },
            {
              company: "DataPulse Inc.",
              role: "Software Developer",
              duration: "2020 - 2022",
              responsibilities: [
                "Developed backend features using Python and Flask.",
                "Integrated third-party payment gateways and webhook services."
              ]
            }
          ],
          years_of_experience: 6,
          domain_strengths: ["Backend Architecture", "API Design", "Database Optimization"]
        }
      };
    },
    analysis: function(resumeId) {
      return mock.resumes.analyze(resumeId);
    }
  },
  jobs: {
    list: function() {
      return [
        {
          id: 101,
          title: "Senior Python Backend Engineer",
          company: "CloudScale Systems",
          location: "Remote / San Francisco",
          job_type: "Full-time",
          experience_level: "Senior",
          min_years_experience: 4,
          required_skills: ["Python", "FastAPI", "Docker", "PostgreSQL", "Kubernetes"],
          soft_skills: ["Problem Solving", "Teamwork"],
          salary_range: "$130,000 - $160,000",
          created_at: new Date().toISOString()
        },
        {
          id: 102,
          title: "Frontend React Developer",
          company: "TechInnovate",
          location: "New York / Remote",
          job_type: "Full-time",
          experience_level: "Mid",
          min_years_experience: 3,
          required_skills: ["React", "TypeScript", "CSS", "HTML", "JavaScript"],
          soft_skills: ["Communication", "Teamwork"],
          salary_range: "$90,000 - $130,000",
          created_at: new Date().toISOString()
        }
      ];
    },
    get: function(jobId) {
      var jobs = mock.jobs.list();
      return jobs.find(function(j) { return j.id == jobId; }) || jobs[0];
    }
  },
  recommendations: {
    get: function(resumeId, params) {
      params = params || {};
      var minScore = params.min_score || 50;
      return {
        resume_id: resumeId,
        total_matched: 1,
        recommendations: [
          {
            job: {
              id: 101,
              title: "Senior Python Backend Engineer",
              company: "CloudScale Systems",
              location: "Remote / San Francisco",
              job_type: "Full-time",
              salary_range: "$130,000 - $160,000"
            },
            match_score: 88,
            match_grade: "High Match",
            matched_technical_skills: ["Python", "FastAPI", "Docker", "PostgreSQL"],
            missing_technical_skills: ["Kubernetes"],
            matched_soft_skills: ["Problem Solving"],
            missing_soft_skills: [],
            experience_fit: "Candidate has 6 years vs 4 years required.",
            education_fit: "Candidate holds B.S. in CS matching degree requirement.",
            explanation: "Jane is an exceptional fit for this role. She brings 6 years of core Python experience and expertise in FastAPI and microservices. Acquiring basic Kubernetes deployment knowledge will complete her qualification."
          }
        ]
      };
    }
  },
  improvements: {
    get: function(resumeId) {
      return {
        resume_id: resumeId,
        overall_score: 82,
        strengths: [
          "Strong technical base in Python and FastAPI microservices.",
          "Clear metric-driven achievement statements in past experience."
        ],
        weaknesses: [
          "Lack of demonstrated cloud orchestration experience (e.g. Kubernetes, Terraform).",
          "Resume summary lacks specific career targeting goals."
        ],
        missing_critical_skills: [
          { skill: "Kubernetes", importance: "High", appears_in_job_matches: 4 },
          { skill: "Redis", importance: "Medium", appears_in_job_matches: 2 }
        ],
        recommended_certifications: [
          {
            title: "AWS Certified Developer - Associate",
            provider: "Amazon Web Services",
            link: "https://aws.amazon.com/certification/certified-developer-associate/"
          }
        ],
        learning_resources: [
          {
            skill: "Kubernetes",
            resource_name: "Kubernetes Mastery: Hands-On Docker & K8s",
            type: "Course",
            url: "https://www.coursera.org/learn/kubernetes"
          }
        ],
        actionable_bullet_improvements: [
          "Rewrite summary to specify target senior cloud/backend architecture roles.",
          "Add a 'Key Projects' section demonstrating Docker container deployments."
        ]
      };
    }
  },
  chat: {
    send: function(message, resumeId, jobId) {
      var session_id = "session-uuid-" + Math.random().toString(36).substring(2, 10);
      return {
        session_id: session_id,
        user_message: message,
        reply: "To showcase Kubernetes skills for " + (jobId ? "a Backend Engineer role" : "this role") + ", I recommend building a multi-container FastAPI application with PostgreSQL and Redis deployed to Kubernetes. This demonstrates practical experience with container orchestration, persistent storage, and service networking.",
        actionable_recommendations: [
          {
            category: "Project Idea",
            title: "FastAPI + PostgreSQL + Redis K8s Deployment",
            provider: "Self-Guided Portfolio",
            reason: "Demonstrates ingress routing, persistent volumes, and secret management."
          }
        ],
        suggested_followups: [
          "How do I set up local Kubernetes using Minikube?",
          "Can you review my resume bullet points for cloud projects?"
        ]
      };
    },
    history: function() {
      return [
        {
          id: 1,
          sender: "user",
          message: "What specific projects should I build to learn Kubernetes?",
          timestamp: new Date().toISOString()
        },
        {
          id: 2,
          sender: "assistant",
          message: "To showcase Kubernetes skills, build a multi-container FastAPI app...",
          timestamp: new Date().toISOString()
        }
      ];
    },
    clear: function() { return { detail: "Chat history cleared successfully." }; }
  }
};