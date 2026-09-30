/* Client-side resume improvement visualization handlers */

document.addEventListener("DOMContentLoaded", function() {
  if (window.location.pathname.includes("resume-improvements.html")) {
    initImprovementsPage();
  }
});

async function initImprovementsPage() {
  var resumeId = parseIdParam("id");
  var loadingEl = document.getElementById("improvements-loading");
  var contentEl = document.getElementById("improvements-content");

  if (!resumeId) {
    // If no resume ID in query, pick first analyzed resume
    try {
      var resumes = await apiFetch("/api/resumes");
      var analyzed = resumes.filter(function(r) { return r.has_analysis; });
      if (analyzed.length > 0) {
        resumeId = analyzed[0].id;
      } else {
        loadingEl.style.display = "none";
        showToast("No analyzed resumes found. Upload and analyze a resume first.", "error");
        return;
      }
    } catch (err) {
      loadingEl.style.display = "none";
      return;
    }
  }

  try {
    var data = await apiFetch("/api/resumes/" + resumeId + "/improvements");
    loadingEl.style.display = "none";
    contentEl.style.display = "grid";

    // Readiness Gauge Score
    var scoreGauge = document.getElementById("improvements-score-gauge");
    if (scoreGauge) {
      var score = data.overall_score || 80;
      scoreGauge.innerText = score;
      scoreGauge.className = "score-badge-circle " + (score >= 70 ? "score-green" : (score >= 40 ? "score-amber" : "score-red"));
    }

    // Key Strengths
    var strengthsList = document.getElementById("strengths-list");
    var strengths = data.strengths || [];
    strengthsList.innerHTML = strengths.length > 0 ?
      strengths.map(function(s) { return '<li>✓ ' + escapeHtml(s) + '</li>'; }).join('') :
      '<li>No strengths extracted.</li>';

    // Areas for Improvement (Weaknesses)
    var weaknessesList = document.getElementById("weaknesses-list");
    var weaknesses = data.weaknesses || [];
    weaknessesList.innerHTML = weaknesses.length > 0 ?
      weaknesses.map(function(w) { return '<li>✕ ' + escapeHtml(w) + '</li>'; }).join('') :
      '<li>No specific weaknesses detected.</li>';

    // Missing Skills Matrix
    var missingContainer = document.getElementById("missing-skills-container");
    var missingSkills = data.missing_critical_skills || [];
    missingContainer.innerHTML = missingSkills.length > 0 ? missingSkills.map(function(item) {
      var importanceBadge = item.importance === "High" ? "badge-danger" : "badge-warning";
      return '<div style="display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; background: var(--neutral-50); border: 1px solid var(--neutral-200); border-radius: var(--radius-sm); flex-wrap: wrap; gap: 8px;">' +
        '<div>' +
          '<strong style="color: var(--neutral-900); font-size: 0.95rem;">' + escapeHtml(item.skill) + '</strong>' +
          '<div style="font-size: 0.8rem; color: var(--neutral-500);">Appears in ' + (parseInt(item.appears_in_job_matches, 10) || 0) + ' matched job postings</div>' +
        '</div>' +
        '<span class="badge ' + importanceBadge + '">' + escapeHtml(item.importance) + ' Priority</span>' +
      '</div>';
    }).join('') : '<p style="color:var(--neutral-500);">No critical skill gaps identified!</p>';

    // Recommended Certifications
    var certsContainer = document.getElementById("certifications-container");
    var certs = data.recommended_certifications || [];
    certsContainer.innerHTML = certs.length > 0 ? certs.map(function(c) {
      // safeExternalUrl rejects non-http(s) values AND we escape before insertion
      var safeLink = safeExternalUrl(c.link);
      return '<div style="padding: 14px 16px; background: var(--neutral-50); border: 1px solid var(--neutral-200); border-radius: var(--radius-sm);">' +
        '<strong style="color: var(--neutral-900); display: block;">' + escapeHtml(c.title) + '</strong>' +
        '<span style="font-size: 0.85rem; color: var(--neutral-500);">' + escapeHtml(c.provider) + '</span>' +
        (safeLink ? '<div style="margin-top: 8px;"><a href="' + escapeHtml(safeLink) + '" target="_blank" rel="noopener noreferrer" class="btn btn-secondary btn-sm" style="font-size: 0.8rem;">Learn More &rarr;</a></div>' : '') +
      '</div>';
    }).join('') : '<p style="color:var(--neutral-500);">No specific certification recommendations.</p>';

    // Recommended Courses / Resources
    var resourcesContainer = document.getElementById("resources-container");
    var resources = data.learning_resources || [];
    resourcesContainer.innerHTML = resources.length > 0 ? resources.map(function(r) {
      var safeLink = safeExternalUrl(r.url);
      return '<div style="padding: 14px 16px; background: var(--neutral-50); border: 1px solid var(--neutral-200); border-radius: var(--radius-sm);">' +
        '<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">' +
          '<strong style="color: var(--neutral-900); font-size: 0.95rem;">' + escapeHtml(r.resource_name) + '</strong>' +
          '<span class="badge badge-info">' + escapeHtml(r.type || 'Course') + '</span>' +
        '</div>' +
        '<div style="font-size: 0.85rem; color: var(--neutral-500); margin-top: 4px;">Target Skill: ' + escapeHtml(r.skill) + '</div>' +
        (safeLink ? '<div style="margin-top: 8px;"><a href="' + escapeHtml(safeLink) + '" target="_blank" rel="noopener noreferrer" class="btn btn-primary btn-sm" style="font-size: 0.8rem;">Open Course &rarr;</a></div>' : '') +
      '</div>';
    }).join('') : '<p style="color:var(--neutral-500);">No learning resources recommended.</p>';

    // Actionable bullet-point edits
    var bulletsList = document.getElementById("bullet-improvements-container");
    if (bulletsList) {
      var bullets = data.actionable_bullet_improvements || [];
      bulletsList.innerHTML = bullets.length > 0 ?
        bullets.map(function(b) { return '<li>' + escapeHtml(b) + '</li>'; }).join('') :
        '<li>No specific edits suggested.</li>';
    }

  } catch (err) {
    loadingEl.style.display = "none";
    showToast("Could not load resume improvements.", "error");
  }
}