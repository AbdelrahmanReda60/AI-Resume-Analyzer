/* Client-side job browsing, searching, recommendations, and admin CRUD handlers */

var currentRecommendations = [];

document.addEventListener("DOMContentLoaded", function() {
  var path = window.location.pathname;

  if (path.includes("jobs.html")) {
    initJobsPage();
  } else if (path.includes("job-form.html")) {
    initJobFormPage();
  } else if (path.includes("job-recommendations.html")) {
    initRecommendationsPage();
  }
});

// --- JOBS SEARCH & LIST PAGE ---
var currentPage = 1;
var limit = 10;

async function initJobsPage() {
  // "Post New Job" is only meaningful for signed-in users
  var addJobBtn = document.getElementById("add-job-btn");
  if (addJobBtn && localStorage.getItem("token")) addJobBtn.hidden = false;

  var filterForm = document.getElementById("jobs-filter-form");
  var resetBtn = document.getElementById("reset-filters-btn");
  var prevBtn = document.getElementById("prev-page-btn");
  var nextBtn = document.getElementById("next-page-btn");

  fetchAndRenderJobs();

  if (filterForm) {
    filterForm.onsubmit = function(e) {
      e.preventDefault();
      currentPage = 1;
      fetchAndRenderJobs();
    };
  }

  if (resetBtn) {
    resetBtn.onclick = function() {
      document.getElementById("filter-title").value = "";
      document.getElementById("filter-skill").value = "";
      document.getElementById("filter-location").value = "";
      document.getElementById("filter-job-type").value = "";
      if (document.getElementById("filter-level")) document.getElementById("filter-level").value = "";
      currentPage = 1;
      fetchAndRenderJobs();
    };
  }

  if (prevBtn) {
    prevBtn.onclick = function() {
      if (currentPage > 1) {
        currentPage--;
        fetchAndRenderJobs();
      }
    };
  }
  if (nextBtn) {
    nextBtn.onclick = function() {
      currentPage++;
      fetchAndRenderJobs();
    };
  }
}

async function fetchAndRenderJobs() {
  var loadingEl = document.getElementById("jobs-loading");
  var emptyEl = document.getElementById("jobs-empty");
  var errorEl = document.getElementById("jobs-error");
  var gridEl = document.getElementById("jobs-grid");
  var prevBtn = document.getElementById("prev-page-btn");
  var nextBtn = document.getElementById("next-page-btn");
  var pageIndicator = document.getElementById("page-indicator");

  loadingEl.style.display = "block";
  emptyEl.style.display = "none";
  if (errorEl) errorEl.style.display = "none";
  gridEl.innerHTML = "";

  var title = document.getElementById("filter-title") ? document.getElementById("filter-title").value.trim() : "";
  var skill = document.getElementById("filter-skill") ? document.getElementById("filter-skill").value.trim() : "";
  var location = document.getElementById("filter-location") ? document.getElementById("filter-location").value.trim() : "";
  var jobType = document.getElementById("filter-job-type") ? document.getElementById("filter-job-type").value : "";
  var level = document.getElementById("filter-level") ? document.getElementById("filter-level").value : "";

  var offset = (currentPage - 1) * limit;
  var qs = [];
  if (title) qs.push("title=" + encodeURIComponent(title));
  if (skill) qs.push("skill=" + encodeURIComponent(skill));
  if (location) qs.push("location=" + encodeURIComponent(location));
  if (jobType) qs.push("job_type=" + encodeURIComponent(jobType));
  if (level) qs.push("experience_level=" + encodeURIComponent(level));
  qs.push("limit=" + limit);
  qs.push("offset=" + offset);

  try {
    var data = await apiFetch("/api/jobs?" + qs.join("&"));
    loadingEl.style.display = "none";

    var jobs = data.jobs || [];
    var total = data.total || 0;

    if (jobs.length === 0) {
      emptyEl.style.display = "block";
      if (prevBtn) prevBtn.disabled = true;
      if (nextBtn) nextBtn.disabled = true;
      if (pageIndicator) pageIndicator.innerText = "Page 1";
      return;
    }

    gridEl.innerHTML = jobs.map(function(j) {
      var reqSkills = j.required_skills || [];
      var isAuth = Boolean(localStorage.getItem("token"));

      return '<div class="card card-hover" style="display: flex; flex-direction: column; justify-content: space-between;">' +
        '<div>' +
          '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">' +
            '<h3 style="font-size: 1.15rem; font-weight: 700; color: var(--neutral-900);">' + escapeHtml(j.title) + '</h3>' +
            '<span class="badge badge-neutral">' + escapeHtml(j.job_type) + '</span>' +
          '</div>' +
          '<div style="color: var(--primary-600); font-weight: 600; font-size: 0.9rem; margin-top: 2px;">' + escapeHtml(j.company) + '</div>' +
          '<div style="font-size: 0.85rem; color: var(--neutral-500); margin-top: 4px;">📍 ' + escapeHtml(j.location) + ' • ' + escapeHtml(j.salary_range || 'Competitive') + '</div>' +
          
          '<p style="font-size: 0.875rem; color: var(--neutral-600); margin: 12px 0; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;">' +
            escapeHtml(j.description) +
          '</p>' +

          '<div class="chips-grid" style="margin-bottom: 16px;">' +
            reqSkills.slice(0, 4).map(function(s) { return '<span class="chip chip-tech">' + escapeHtml(s) + '</span>'; }).join('') +
            (reqSkills.length > 4 ? '<span class="chip">+' + (reqSkills.length - 4) + ' more</span>' : '') +
          '</div>' +
        '</div>' +

        '<div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--neutral-200); padding-top: 12px; margin-top: 12px;">' +
          '<span class="badge badge-info">' + escapeHtml(j.experience_level) + ' Level</span>' +
          '<div style="display: flex; gap: 8px;">' +
            (isAuth ? '<a href="job-form.html?id=' + Number(j.id) + '" class="btn btn-ghost btn-sm">Edit</a>' +
                      '<button onclick="confirmDeleteJob(' + Number(j.id) + ')" class="btn btn-danger btn-sm">Delete</button>' : '') +
          '</div>' +
        '</div>' +
      '</div>';
    }).join('');

    // Pagination status
    if (pageIndicator) pageIndicator.innerText = "Page " + currentPage + " of " + Math.ceil(total / limit);
    if (prevBtn) prevBtn.disabled = currentPage <= 1;
    if (nextBtn) nextBtn.disabled = (currentPage * limit) >= total;

  } catch (err) {
    loadingEl.style.display = "none";
    emptyEl.style.display = "none";
    if (errorEl) errorEl.style.display = "block";
  }
}

function confirmDeleteJob(jobId) {
  showConfirmModal({
    title: "Delete Job Posting",
    message: "Are you sure you want to delete this job posting? This action cannot be undone.",
    confirmText: "Delete Job",
    confirmClass: "btn-danger",
    onConfirm: async function() {
      try {
        await apiFetch("/api/jobs/" + jobId, { method: "DELETE" });
        showToast("Job posting deleted.", "info");
        fetchAndRenderJobs();
      } catch (err) {}
    }
  });
}

// --- JOB FORM PAGE LOGIC ---
async function initJobFormPage() {
  var form = document.getElementById("job-post-form");
  var titleEl = document.getElementById("form-header-title");
  var jobId = parseIdParam("id");

  if (jobId) {
    if (titleEl) titleEl.innerText = "Edit Job Posting";
    try {
      var job = await apiFetch("/api/jobs/" + jobId);
      document.getElementById("job-id").value = job.id;
      document.getElementById("job-title").value = job.title;
      document.getElementById("job-company").value = job.company;
      document.getElementById("job-location").value = job.location;
      document.getElementById("job-type").value = job.job_type;
      document.getElementById("job-level").value = job.experience_level;
      document.getElementById("job-min-years").value = job.min_years_experience;
      document.getElementById("job-degree").value = job.required_degree || "Bachelor";
      document.getElementById("job-skills").value = (job.required_skills || []).join(", ");
      document.getElementById("job-soft-skills").value = (job.soft_skills || []).join(", ");
      document.getElementById("job-salary").value = job.salary_range || "";
      document.getElementById("job-description").value = job.description;
    } catch (err) {
      showToast("Could not load job details.", "error");
    }
  }

  if (form) {
    form.onsubmit = async function(e) {
      e.preventDefault();
      var submitBtn = document.getElementById("save-job-btn");
      var id = document.getElementById("job-id").value;

      var title = document.getElementById("job-title").value.trim();
      var company = document.getElementById("job-company").value.trim();
      var location = document.getElementById("job-location").value.trim();
      var jobType = document.getElementById("job-type").value;
      var level = document.getElementById("job-level").value;
      var minYears = parseInt(document.getElementById("job-min-years").value) || 0;
      var degree = document.getElementById("job-degree").value;
      var skillsRaw = document.getElementById("job-skills").value;
      var softRaw = document.getElementById("job-soft-skills").value;
      var salary = document.getElementById("job-salary").value.trim();
      var description = document.getElementById("job-description").value.trim();

      if (!title || !company || !location || !skillsRaw || !description) {
        showToast("Please fill in all required fields.", "error");
        return;
      }

      var reqSkills = skillsRaw.split(",").map(function(s) { return s.trim(); }).filter(Boolean);
      var softSkills = softRaw.split(",").map(function(s) { return s.trim(); }).filter(Boolean);

      var payload = {
        title: title,
        company: company,
        location: location,
        job_type: jobType,
        experience_level: level,
        min_years_experience: minYears,
        required_degree: degree,
        required_skills: reqSkills,
        soft_skills: softSkills,
        salary_range: salary,
        description: description
      };

      submitBtn.classList.add("btn-loading");
      submitBtn.disabled = true;

      try {
        if (id) {
          await apiFetch("/api/jobs/" + id, { method: "PUT", body: JSON.stringify(payload) });
          showToast("Job updated successfully!", "success");
        } else {
          await apiFetch("/api/jobs", { method: "POST", body: JSON.stringify(payload) });
          showToast("Job created successfully!", "success");
        }
        setTimeout(function() { window.location.href = "jobs.html"; }, 600);
      } catch (err) {
        submitBtn.classList.remove("btn-loading");
        submitBtn.disabled = false;
      }
    };
  }
}

// --- RECOMMENDATIONS PAGE LOGIC ---
async function initRecommendationsPage() {
  var resumeId = parseIdParam("id");
  var selectEl = document.getElementById("resume-select");

  try {
    var resumes = await apiFetch("/api/resumes");
    var analyzedResumes = resumes.filter(function(r) { return r.has_analysis; });

    if (analyzedResumes.length === 0) {
      document.getElementById("recommendations-loading").style.display = "none";
      document.getElementById("recommendations-empty").style.display = "block";
      return;
    }

    if (selectEl) {
      selectEl.innerHTML = analyzedResumes.map(function(r) {
        var selected = String(r.id) === String(resumeId) ? 'selected' : '';
        return '<option value="' + (Number(r.id) || 0) + '" ' + selected + '>' + escapeHtml(r.title) + '</option>';
      }).join('');
    }

    var activeResumeId = resumeId || (analyzedResumes[0] ? analyzedResumes[0].id : null);
    if (activeResumeId) {
      loadJobRecommendations(activeResumeId);
    }
  } catch (err) {
    document.getElementById("recommendations-loading").style.display = "none";
    document.getElementById("recommendations-empty").style.display = "block";
  }
}

async function loadJobRecommendations(resumeId) {
  var loadingEl = document.getElementById("recommendations-loading");
  var emptyEl = document.getElementById("recommendations-empty");
  var gridEl = document.getElementById("recommendations-grid");

  loadingEl.style.display = "block";
  emptyEl.style.display = "none";
  gridEl.innerHTML = "";

  try {
    var data = await apiFetch("/api/resumes/" + resumeId + "/recommendations");
    loadingEl.style.display = "none";

    currentRecommendations = data.recommendations || [];

    if (currentRecommendations.length === 0) {
      emptyEl.style.display = "block";
      return;
    }

    renderSortedRecommendations();
  } catch (err) {
    loadingEl.style.display = "none";
    emptyEl.style.display = "block";
  }
}

function renderSortedRecommendations() {
  var sortVal = document.getElementById("sort-select") ? document.getElementById("sort-select").value : "score-desc";
  var gridEl = document.getElementById("recommendations-grid");

  var sorted = currentRecommendations.slice().sort(function(a, b) {
    if (sortVal === "score-desc") return b.match_score - a.match_score;
    if (sortVal === "score-asc") return a.match_score - b.match_score;
    if (sortVal === "title") return a.job.title.localeCompare(b.job.title);
    return 0;
  });

  gridEl.innerHTML = sorted.map(function(rec) {
    var job = rec.job;
    var score = rec.match_score;
    var scoreClass = score >= 70 ? "score-green" : (score >= 40 ? "score-amber" : "score-red");
    var matchedTech = rec.matched_technical_skills || [];
    var missingTech = rec.missing_technical_skills || [];

    return '<div class="card" style="display: flex; flex-direction: column; gap: 16px;">' +
      '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap;">' +
        '<div style="display: flex; gap: 16px; align-items: center;">' +
          '<div class="score-badge-circle ' + scoreClass + '">' + escapeHtml(Number(score) || 0) + '%</div>' +
          '<div>' +
            '<h3 style="font-size: 1.2rem; font-weight: 800; color: var(--neutral-900);">' + escapeHtml(job.title) + '</h3>' +
            '<div style="color: var(--primary-600); font-weight: 600; font-size: 0.95rem;">' + escapeHtml(job.company) + '</div>' +
            '<div style="font-size: 0.85rem; color: var(--neutral-500); margin-top: 2px;">📍 ' + escapeHtml(job.location) + ' • ' + escapeHtml(job.salary_range || 'Competitive') + '</div>' +
          '</div>' +
        '</div>' +
        '<span class="badge badge-info">' + escapeHtml(rec.match_grade) + '</span>' +
      '</div>' +

      '<div>' +
        '<p style="font-size: 0.925rem; color: var(--neutral-700); line-height: 1.5; background: var(--neutral-50); padding: 12px; border-radius: var(--radius-sm); border-left: 3px solid var(--primary-600);">' +
          escapeHtml(rec.explanation) +
        '</p>' +
      '</div>' +

      '<div class="grid grid-cols-2" style="gap: 12px;">' +
        '<div>' +
          '<h4 style="font-size: 0.8rem; font-weight: 700; color: var(--success-700); text-transform: uppercase; margin-bottom: 6px;">Matched Technical Skills</h4>' +
          '<div class="chips-grid">' +
            (matchedTech.length > 0 ? matchedTech.map(function(s) { return '<span class="chip chip-matched">✓ ' + escapeHtml(s) + '</span>'; }).join('') : '<span style="font-size:0.85rem; color:var(--neutral-500);">None</span>') +
          '</div>' +
        '</div>' +

        '<div>' +
          '<h4 style="font-size: 0.8rem; font-weight: 700; color: var(--danger-600); text-transform: uppercase; margin-bottom: 6px;">Missing Required Skills</h4>' +
          '<div class="chips-grid">' +
            (missingTech.length > 0 ? missingTech.map(function(s) { return '<span class="chip chip-missing">✕ ' + escapeHtml(s) + '</span>'; }).join('') : '<span style="font-size:0.85rem; color:var(--success-600);">All skills matched!</span>') +
          '</div>' +
        '</div>' +
      '</div>' +

      '<div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--neutral-200); padding-top: 12px; font-size: 0.85rem; color: var(--neutral-600);">' +
        '<span>Experience Fit: ' + escapeHtml(rec.experience_fit || 'Evaluated') + '</span>' +
        '<a href="career-advisor.html?job_id=' + (Number(job.id) || 0) + '" class="btn btn-ghost btn-sm">Ask Advisor about this job &rarr;</a>' +
      '</div>' +
    '</div>';
  }).join('');
}