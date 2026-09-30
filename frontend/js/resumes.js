/* Client-side resume management and rendering handlers */

document.addEventListener("DOMContentLoaded", function() {
  var path = window.location.pathname;

  if (path.includes("dashboard.html")) {
    initDashboard();
  } else if (path.includes("upload-resume.html")) {
    initUploadPage();
  } else if (path.includes("resume-analysis.html")) {
    initAnalysisPage();
  }
});

// --- DASHBOARD LOGIC ---
async function initDashboard() {
  var loadingEl = document.getElementById("resumes-loading");
  var emptyEl = document.getElementById("resumes-empty");
  var errorEl = document.getElementById("resumes-error");
  var containerEl = document.getElementById("resumes-table-container");
  var tbody = document.getElementById("resumes-tbody");

  try {
    var resumes = await apiFetch("/api/resumes");
    loadingEl.style.display = "none";

    document.getElementById("stat-resumes-count").innerText = resumes.length;
    var analyzed = resumes.filter(function(r) { return r.has_analysis; });
    document.getElementById("stat-analyses-count").innerText = analyzed.length;

    // Average match score across the user's analyzed resumes (cheap: no LLM pass)
    var avgEl = document.getElementById("stat-matches-count");
    if (analyzed.length === 0) {
      avgEl.innerText = "—";
    } else {
      try {
        var perResume = await Promise.all(analyzed.map(function(r) {
          return apiFetch("/api/resumes/" + r.id + "/recommendations?min_score=0&limit=1&explain=false");
        }));
        var scores = [];
        perResume.forEach(function(res) {
          (res.recommendations || []).forEach(function(rec) {
            if (typeof rec.match_score === "number") scores.push(rec.match_score);
          });
        });
        avgEl.innerText = scores.length > 0
          ? Math.round(scores.reduce(function(a, b) { return a + b; }, 0) / scores.length) + "%"
          : "—";
      } catch (scoreErr) {
        avgEl.innerText = "—";
      }
    }

    if (resumes.length === 0) {
      emptyEl.style.display = "block";
      containerEl.style.display = "none";
      return;
    }

    emptyEl.style.display = "none";
    containerEl.style.display = "block";

    tbody.innerHTML = resumes.map(function(r) {
      var dateStr = new Date(r.created_at).toLocaleDateString();
      var badgeClass = r.has_analysis ? "badge-success" : "badge-warning";
      var badgeText = r.has_analysis ? "Analyzed" : "Pending Analysis";

      // Coerce the id to a number so it can never break out of href/on* attributes
      var rid = Number(r.id) || 0;
      return '<tr class="resume-row">' +
        '<td class="resume-cell" data-label="Title" style="font-weight: 600; color: var(--neutral-900);">' + escapeHtml(r.title) + '</td>' +
        '<td class="resume-cell" data-label="Format"><span class="badge badge-neutral">' + escapeHtml(r.file_type.toUpperCase()) + '</span></td>' +
        '<td class="resume-cell" data-label="Upload Date" style="color: var(--neutral-600);">' + escapeHtml(dateStr) + '</td>' +
        '<td class="resume-cell" data-label="Status"><span class="badge ' + badgeClass + '">' + badgeText + '</span></td>' +
        '<td class="resume-cell resume-cell-actions" data-label="Actions" style="text-align: right;">' +
          '<div style="display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap;">' +
            (r.has_analysis ?
              '<a href="resume-analysis.html?id=' + rid + '" class="btn btn-secondary btn-sm">View Analysis</a>' +
              '<a href="job-recommendations.html?id=' + rid + '" class="btn btn-primary btn-sm">Matches</a>' +
              '<a href="resume-improvements.html?id=' + rid + '" class="btn btn-ghost btn-sm">Improvements</a>' :
              '<button onclick="triggerAnalyze(' + rid + ', this)" class="btn btn-primary btn-sm">Analyze Now</button>') +
            '<button onclick="confirmDeleteResume(' + rid + ')" class="btn btn-danger btn-sm">Delete</button>' +
          '</div>' +
        '</td>' +
      '</tr>';
    }).join('');
  } catch (err) {
    // Distinguish "request failed" from "you have no resumes"
    loadingEl.style.display = "none";
    emptyEl.style.display = "none";
    containerEl.style.display = "none";
    if (errorEl) errorEl.style.display = "block";
  }
}

async function triggerAnalyze(resumeId, btnEl) {
  if (btnEl) {
    btnEl.classList.add("btn-loading");
    btnEl.disabled = true;
  }
  try {
    await apiFetch("/api/resumes/" + resumeId + "/analyze", { method: "POST" });
    showToast("Resume analyzed successfully!", "success");
    setTimeout(function() {
      window.location.href = "resume-analysis.html?id=" + resumeId;
    }, 500);
  } catch (err) {
    if (btnEl) {
      btnEl.classList.remove("btn-loading");
      btnEl.disabled = false;
    }
  }
}

function confirmDeleteResume(resumeId) {
  showConfirmModal({
    title: "Delete Resume",
    message: "Are you sure you want to delete this resume? All related analyses and recommendations will be permanently removed.",
    confirmText: "Delete Resume",
    confirmClass: "btn-danger",
    onConfirm: async function() {
      try {
        await apiFetch("/api/resumes/" + resumeId, { method: "DELETE" });
        showToast("Resume deleted.", "info");
        initDashboard();
      } catch (err) {}
    }
  });
}

// --- UPLOAD PAGE LOGIC ---
function initUploadPage() {
  var form = document.getElementById("upload-resume-form");
  var dropzone = document.getElementById("dropzone");
  var fileInput = document.getElementById("file-input");
  var preview = document.getElementById("file-preview");
  var previewFilename = document.getElementById("preview-filename");
  var previewFilesize = document.getElementById("preview-filesize");
  var removeBtn = document.getElementById("remove-file-btn");
  var selectedFile = null;

  if (!form) return;

  // Drag & drop handlers
  ['dragenter', 'dragover'].forEach(function(eventName) {
    dropzone.addEventListener(eventName, function(e) {
      e.preventDefault();
      dropzone.style.borderColor = "var(--primary-600)";
      dropzone.style.backgroundColor = "var(--primary-50)";
    });
  });

  ['dragleave', 'drop'].forEach(function(eventName) {
    dropzone.addEventListener(eventName, function(e) {
      e.preventDefault();
      dropzone.style.borderColor = "var(--neutral-300)";
      dropzone.style.backgroundColor = "var(--neutral-50)";
    });
  });

  dropzone.addEventListener("drop", function(e) {
    var dt = e.dataTransfer;
    if (dt.files && dt.files.length > 0) {
      handleFileSelect(dt.files[0]);
    }
  });

  fileInput.addEventListener("change", function() {
    if (fileInput.files.length > 0) {
      handleFileSelect(fileInput.files[0]);
    }
  });

  // Click (or Enter/Space) anywhere in the zone opens the file picker
  dropzone.addEventListener("click", function(e) {
    if (e.target.closest("button, a, input")) return;
    fileInput.click();
  });
  dropzone.addEventListener("keydown", function(e) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      fileInput.click();
    }
  });

  function handleFileSelect(file) {
    var ext = file.name.split('.').pop().toLowerCase();
    if (ext !== 'pdf' && ext !== 'docx') {
      showToast("Only PDF and DOCX files are allowed.", "error");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      showToast("File size exceeds maximum limit of 5MB.", "error");
      return;
    }

    selectedFile = file;
    previewFilename.innerText = file.name;
    previewFilesize.innerText = (file.size / 1024).toFixed(1) + " KB";
    preview.style.display = "flex";
  }

  removeBtn.onclick = function() {
    selectedFile = null;
    fileInput.value = "";
    preview.style.display = "none";
  };

  form.onsubmit = async function(e) {
    e.preventDefault();
    if (!selectedFile) {
      showToast("Please select a resume file to upload.", "error");
      return;
    }

    var submitBtn = document.getElementById("upload-submit-btn");
    var title = document.getElementById("resume-title").value.trim() || selectedFile.name;
    var progressContainer = document.getElementById("upload-progress-container");
    var progressBarFill = document.getElementById("progress-bar-fill");
    var progressStatus = document.getElementById("progress-status-text");
    var progressPercent = document.getElementById("progress-percent");

    submitBtn.classList.add("btn-loading");
    submitBtn.disabled = true;
    progressContainer.style.display = "block";

    // Step 1: Uploading
    setStepActive(1);
    progressBarFill.style.width = "30%";
    progressPercent.innerText = "30%";
    progressStatus.innerText = "Uploading file to server...";

    try {
      var formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("title", title);

      var uploadResult = await apiFetch("/api/resumes/upload", {
        method: "POST",
        body: formData
      });

      // Step 2: Text Extraction
      setStepActive(2);
      progressBarFill.style.width = "65%";
      progressPercent.innerText = "65%";
      progressStatus.innerText = "Extracting text content from document...";

      // Step 3: Trigger AI Analysis
      setStepActive(3);
      progressBarFill.style.width = "90%";
      progressPercent.innerText = "90%";
      progressStatus.innerText = "Running AI Resume Analyzer agent...";

      await apiFetch("/api/resumes/" + uploadResult.id + "/analyze", { method: "POST" });

      progressBarFill.style.width = "100%";
      progressPercent.innerText = "100%";
      progressStatus.innerText = "Analysis complete!";

      showToast("Resume uploaded and analyzed successfully!", "success");
      setTimeout(function() {
        window.location.href = "resume-analysis.html?id=" + uploadResult.id;
      }, 600);
    } catch (err) {
      progressContainer.style.display = "none";
      submitBtn.classList.remove("btn-loading");
      submitBtn.disabled = false;
    }
  };

  function setStepActive(stepNum) {
    [1, 2, 3].forEach(function(n) {
      var el = document.getElementById("step-" + n);
      if (el) {
        if (n < stepNum) {
          el.className = "step completed";
        } else if (n === stepNum) {
          el.className = "step active";
        } else {
          el.className = "step";
        }
      }
    });
  }
}

// --- ANALYSIS VIEW LOGIC ---
async function initAnalysisPage() {
  // parseIdParam only accepts digits, so ?id= can never inject markup
  var resumeId = parseIdParam("id");
  var loadingEl = document.getElementById("analysis-loading");
  var contentEl = document.getElementById("analysis-content");

  if (!resumeId) {
    showToast("No resume ID provided.", "error");
    window.location.href = "dashboard.html";
    return;
  }

  // Action links
  var actionsContainer = document.getElementById("analysis-actions");
  if (actionsContainer) {
    actionsContainer.innerHTML =
      '<a href="job-recommendations.html?id=' + resumeId + '" class="btn btn-primary btn-sm">Job Recommendations</a>' +
      '<a href="resume-improvements.html?id=' + resumeId + '" class="btn btn-secondary btn-sm">View Improvements</a>' +
      '<a href="career-advisor.html?resume_id=' + resumeId + '" class="btn btn-ghost btn-sm">Ask Advisor</a>';
  }

  try {
    var data = await apiFetch("/api/resumes/" + resumeId + "/analysis");
    loadingEl.style.display = "none";
    contentEl.style.display = "grid";

    var result = data.result || {};
    document.getElementById("candidate-name").innerText = result.full_name || "Candidate Profile";
    document.getElementById("candidate-email").innerText = "📧 " + (result.email || "N/A");
    document.getElementById("candidate-phone").innerText = "📞 " + (result.phone || "N/A");
    document.getElementById("candidate-location").innerText = "📍 " + (result.location || "N/A");
    document.getElementById("years-exp-badge").innerText = (result.years_of_experience || 0) + " Years Experience";
    document.getElementById("candidate-summary").innerText = result.summary || "No summary provided.";

    // Render Tech Skills
    var techChips = document.getElementById("technical-skills-chips");
    var techSkills = result.technical_skills || [];
    techChips.innerHTML = techSkills.length > 0 ?
      techSkills.map(function(s) { return '<span class="chip chip-tech">' + escapeHtml(s) + '</span>'; }).join('') :
      '<span style="color:var(--neutral-500); font-size:0.9rem;">None detected</span>';

    // Render Soft Skills
    var softChips = document.getElementById("soft-skills-chips");
    var softSkills = result.soft_skills || [];
    softChips.innerHTML = softSkills.length > 0 ?
      softSkills.map(function(s) { return '<span class="chip chip-soft">' + escapeHtml(s) + '</span>'; }).join('') :
      '<span style="color:var(--neutral-500); font-size:0.9rem;">None detected</span>';

    // Experience Timeline
    var expList = document.getElementById("experience-list");
    var experiences = result.experience || [];
    expList.innerHTML = experiences.length > 0 ? experiences.map(function(e) {
      var resp = e.responsibilities || [];
      return '<div style="border-left: 3px solid var(--primary-600); padding-left: 16px; margin-left: 4px;">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap;">' +
          '<div>' +
            '<strong style="font-size: 1.05rem; color: var(--neutral-900);">' + escapeHtml(e.role || "Role") + '</strong>' +
            '<div style="color: var(--primary-600); font-weight: 600; font-size: 0.9rem;">' + escapeHtml(e.company || "Company") + '</div>' +
          '</div>' +
          '<span class="badge badge-neutral">' + escapeHtml(e.duration || "Duration") + '</span>' +
        '</div>' +
        (resp.length > 0 ? '<ul style="margin-top: 8px; padding-left: 20px; color: var(--neutral-700); font-size: 0.9rem;">' +
          resp.map(function(r) { return '<li style="margin-bottom: 4px;">' + escapeHtml(r) + '</li>'; }).join('') +
        '</ul>' : '') +
      '</div>';
    }).join('') : '<p style="color:var(--neutral-500);">No experience entries extracted.</p>';

    // Education
    var eduList = document.getElementById("education-list");
    var education = result.education || [];
    eduList.innerHTML = education.length > 0 ? education.map(function(ed) {
      return '<div style="background: var(--neutral-50); padding: 12px 16px; border-radius: var(--radius-sm); border: 1px solid var(--neutral-200);">' +
        '<strong style="color: var(--neutral-900);">' + escapeHtml(ed.degree || "Degree") + '</strong>' +
        '<div style="color: var(--neutral-600); font-size: 0.875rem;">' + escapeHtml(ed.institution || "Institution") + ' • ' + escapeHtml(ed.year || "Year") + '</div>' +
      '</div>';
    }).join('') : '<p style="color:var(--neutral-500);">No education entries extracted.</p>';

  } catch (err) {
    loadingEl.style.display = "none";
    showToast("Could not load resume analysis.", "error");
  }
}