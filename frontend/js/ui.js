/* ==========================================================================
   AI Resume Analyzer — Shared UI Utilities & Component Renderers
   ========================================================================== */

/**
 * Escapes HTML characters to prevent XSS.
 */
function escapeHtml(text) {
  if (text === null || text === undefined) return "";
  var div = document.createElement("div");
  div.textContent = String(text);
  return div.innerHTML;
}

/**
 * Returns a normalized http/https URL, or null for anything else
 * (javascript:, data:, missing quotes, unparseable values).
 * Always pass the result through escapeHtml() before inserting it.
 */
function safeExternalUrl(value) {
  if (!value) return null;
  try {
    var url = new URL(String(value));
    if (url.protocol === "http:" || url.protocol === "https:") return url.href;
  } catch (e) { /* invalid URL */ }
  return null;
}

/**
 * Reads an integer id from the query string. Returns null unless the value is
 * purely numeric, which also neutralises reflected XSS through ?id=.
 */
function parseIdParam(name) {
  var value = new URLSearchParams(window.location.search).get(name);
  if (value === null || !/^\d+$/.test(value)) return null;
  return value;
}

/**
 * Safe Markdown-light parser:
 * 1. Escapes HTML first to avoid XSS.
 * 2. Formats bold (**text**), italic (*text*), code (`code`), lists (- item or * item), and line breaks.
 */
function renderMarkdown(text) {
  if (!text) return "";
  var safe = escapeHtml(text);

  // Bold **text**
  safe = safe.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italic *text*
  safe = safe.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Inline code `code`
  safe = safe.replace(/`(.*?)`/g, '<code style="background:var(--neutral-100); padding:2px 6px; border-radius:4px; font-family:var(--font-mono); font-size:0.875em;">$1</code>');
  
  // Bullet lists (- item or * item)
  var lines = safe.split('\n');
  var inList = false;
  var htmlLines = [];

  lines.forEach(function(line) {
    var trimmed = line.trim();
    if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
      if (!inList) {
        inList = true;
        htmlLines.push('<ul style="margin:8px 0; padding-left:20px;">');
      }
      htmlLines.push('<li>' + trimmed.substring(2) + '</li>');
    } else {
      if (inList) {
        inList = false;
        htmlLines.push('</ul>');
      }
      if (trimmed === '') {
        htmlLines.push('<br>');
      } else {
        htmlLines.push('<p style="margin-bottom:8px;">' + line + '</p>');
      }
    }
  });

  if (inList) {
    htmlLines.push('</ul>');
  }

  return htmlLines.join('');
}

/**
 * Displays floating toast notifications with accessibility support.
 */
function showToast(message, type) {
  type = type || "info";
  var container = document.getElementById("toast-container");
  if (!container) {
    container = document.createElement("div");
    container.id = "toast-container";
    container.className = "toast-container";
    container.setAttribute("aria-live", "polite");
    document.body.appendChild(container);
  }

  var toast = document.createElement("div");
  toast.className = "toast toast-" + type;
  toast.innerHTML = "<span>" + escapeHtml(message) + "</span>" +
    "<button style='background:none; border:none; color:white; cursor:pointer; font-weight:bold; margin-left:12px;' onclick='this.parentElement.remove()'>&times;</button>";

  container.appendChild(toast);

  setTimeout(function() {
    if (toast.parentElement) toast.remove();
  }, 4000);
}

/**
 * Displays a generic modal dialog (e.g. for confirming deletions).
 */
function showConfirmModal(options) {
  options = options || {};
  var title = options.title || "Confirm Action";
  var message = options.message || "Are you sure you want to proceed?";
  var confirmText = options.confirmText || "Confirm";
  var confirmClass = options.confirmClass || "btn-danger";

  var backdrop = document.createElement("div");
  backdrop.className = "modal-backdrop is-open";
  backdrop.innerHTML =
    '<div class="modal-dialog" role="dialog" aria-modal="true" aria-labelledby="modal-title">' +
      '<div class="card-header" style="margin-bottom:12px;">' +
        '<h3 id="modal-title" class="card-title">' + escapeHtml(title) + '</h3>' +
        '<button class="btn btn-ghost btn-sm" id="modal-close-btn">&times;</button>' +
      '</div>' +
      '<p style="color:var(--neutral-600); margin-bottom:20px;">' + escapeHtml(message) + '</p>' +
      '<div style="display:flex; justify-content:flex-end; gap:12px;">' +
        '<button class="btn btn-secondary" id="modal-cancel-btn">Cancel</button>' +
        '<button class="btn ' + confirmClass + '" id="modal-confirm-btn">' + escapeHtml(confirmText) + '</button>' +
      '</div>' +
    '</div>';

  document.body.appendChild(backdrop);

  var previouslyFocused = document.activeElement;
  var confirmBtn = backdrop.querySelector("#modal-confirm-btn");
  var cancelBtn = backdrop.querySelector("#modal-cancel-btn");
  var closeBtn = backdrop.querySelector("#modal-close-btn");

  // Move focus into the dialog so keyboard users are not stranded behind it
  if (confirmBtn) confirmBtn.focus();

  function closeModal() {
    document.removeEventListener("keydown", onKeydown, true);
    backdrop.classList.remove("is-open");
    setTimeout(function() {
      backdrop.remove();
      if (previouslyFocused && previouslyFocused.focus) previouslyFocused.focus();
    }, 200);
  }

  function onKeydown(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      closeModal();
      return;
    }
    if (e.key !== "Tab") return;
    // Simple focus trap: cycle through the dialog's focusable buttons
    var focusable = [closeBtn, cancelBtn, confirmBtn].filter(Boolean);
    var index = focusable.indexOf(document.activeElement);
    e.preventDefault();
    var next = e.shiftKey
      ? focusable[(index - 1 + focusable.length) % focusable.length]
      : focusable[(index + 1) % focusable.length];
    if (next) next.focus();
  }

  document.addEventListener("keydown", onKeydown, true);

  // Clicking the backdrop (outside the dialog) cancels
  backdrop.addEventListener("click", function(e) {
    if (e.target === backdrop) closeModal();
  });

  closeBtn.onclick = closeModal;
  cancelBtn.onclick = closeModal;
  confirmBtn.onclick = function() {
    closeModal();
    if (typeof options.onConfirm === "function") {
      options.onConfirm();
    }
  };
}

/**
 * Toggles password input visibility between password and text.
 */
function togglePasswordVisibility(inputId, toggleBtn) {
  var input = document.getElementById(inputId);
  if (!input) return;
  if (input.type === "password") {
    input.type = "text";
    toggleBtn.innerHTML = '<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.875 18.825A10.05 10.05 0 0112 19c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24M1 1l22 22"/></svg>';
  } else {
    input.type = "password";
    toggleBtn.innerHTML = '<svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/></svg>';
  }
}

/**
 * Renders the top navigation header dynamically based on authentication state.
 */
function renderNavbar() {
  var navContainer = document.getElementById("navbar-container");
  if (!navContainer) return;

  var userRaw = localStorage.getItem("user");
  var token = localStorage.getItem("token");
  var isLoggedIn = Boolean(token && userRaw);
  var userName = "";

  if (isLoggedIn) {
    try {
      var user = JSON.parse(userRaw);
      userName = user.full_name || user.email || "User";
    } catch(e) {
      userName = "User";
    }
  }

  var currentPath = window.location.pathname;

  function isActive(path) {
    return currentPath.indexOf(path) !== -1 ? 'active' : '';
  }

  var linksHtml = '';
  var authHtml = '';
  var mobileItemsHtml = '';

  if (isLoggedIn) {
    linksHtml =
      '<li><a href="dashboard.html" class="nav-link ' + isActive('dashboard.html') + '">Dashboard</a></li>' +
      '<li><a href="upload-resume.html" class="nav-link ' + isActive('upload-resume.html') + '">Upload Resume</a></li>' +
      '<li><a href="jobs.html" class="nav-link ' + isActive('jobs.html') + '">Browse Jobs</a></li>' +
      '<li><a href="career-advisor.html" class="nav-link ' + isActive('career-advisor.html') + '">Career Advisor</a></li>';

    authHtml =
      '<div class="nav-user-menu">' +
        '<button class="nav-user-btn" id="nav-user-btn" aria-haspopup="true" aria-expanded="false" aria-label="Account menu">' +
          '<span class="nav-user-avatar" aria-hidden="true">' + escapeHtml((userName || "U").charAt(0).toUpperCase()) + '</span>' +
          '<span class="nav-user-name">' + escapeHtml(userName) + '</span>' +
          '<svg width="14" height="14" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>' +
        '</button>' +
        '<div class="nav-user-dropdown" id="nav-user-dropdown" role="menu">' +
          '<a href="dashboard.html" role="menuitem">Dashboard</a>' +
          '<a href="upload-resume.html" role="menuitem">Upload Resume</a>' +
          '<button type="button" id="global-logout-btn" role="menuitem">Logout</button>' +
        '</div>' +
      '</div>';

    mobileItemsHtml = '<li class="nav-mobile-auth"><button type="button" class="btn btn-ghost btn-sm btn-block" id="mobile-logout-btn">Logout</button></li>';
  } else {
    linksHtml =
      '<li><a href="index.html" class="nav-link ' + (currentPath === '/' || isActive('index.html') ? 'active' : '') + '">Home</a></li>' +
      '<li><a href="jobs.html" class="nav-link ' + isActive('jobs.html') + '">Browse Jobs</a></li>';

    authHtml =
      '<a href="login.html" class="btn btn-ghost btn-sm nav-desktop-auth">Login</a>' +
      '<a href="register.html" class="btn btn-primary btn-sm nav-desktop-auth">Register</a>';

    mobileItemsHtml =
      '<li class="nav-mobile-auth"><a href="login.html" class="btn btn-ghost btn-sm btn-block">Login</a></li>' +
      '<li class="nav-mobile-auth"><a href="register.html" class="btn btn-primary btn-sm btn-block">Register</a></li>';
  }

  navContainer.innerHTML =
    '<header class="header-nav">' +
      '<div class="nav-container">' +
        '<a href="index.html" class="nav-brand">' +
          '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>' +
          'AI Resume Analyzer' +
        '</a>' +
        '<button class="nav-toggle" id="nav-toggle-btn" aria-label="Toggle navigation" aria-expanded="false" aria-controls="nav-links-menu">' +
          '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/></svg>' +
        '</button>' +
        '<ul class="nav-links nav-links-menu" id="nav-links-menu">' +
          linksHtml +
          mobileItemsHtml +
        '</ul>' +
        '<div class="nav-actions">' +
          authHtml +
        '</div>' +
      '</div>' +
    '</header>';

  // Mobile menu toggle
  var toggleBtn = document.getElementById("nav-toggle-btn");
  var menu = document.getElementById("nav-links-menu");
  if (toggleBtn && menu) {
    toggleBtn.onclick = function() {
      var open = menu.classList.toggle("is-open");
      toggleBtn.setAttribute("aria-expanded", open ? "true" : "false");
    };
  }

  // User dropdown menu (click toggles, Escape/outside click closes)
  var userBtn = document.getElementById("nav-user-btn");
  var userDropdown = document.getElementById("nav-user-dropdown");
  if (userBtn && userDropdown) {
    userBtn.onclick = function(e) {
      e.stopPropagation();
      var open = userDropdown.classList.toggle("is-open");
      userBtn.setAttribute("aria-expanded", open ? "true" : "false");
    };
    document.addEventListener("click", function(e) {
      if (!userDropdown.contains(e.target) && e.target !== userBtn) {
        userDropdown.classList.remove("is-open");
        userBtn.setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", function(e) {
      if (e.key === "Escape") {
        userDropdown.classList.remove("is-open");
        userBtn.setAttribute("aria-expanded", "false");
      }
    });
  }

  // Logout handlers (dropdown + mobile menu entry)
  function bindLogout(id) {
    var btn = document.getElementById(id);
    if (!btn) return;
    btn.onclick = function() {
      if (typeof logoutUser === "function") {
        logoutUser();
      } else {
        localStorage.removeItem("token");
        localStorage.removeItem("user");
        showToast("Logged out successfully.", "info");
        setTimeout(function() { window.location.href = "index.html"; }, 500);
      }
    };
  }
  bindLogout("global-logout-btn");
  bindLogout("mobile-logout-btn");
}

/**
 * Renders the global footer dynamically.
 */
function renderFooter() {
  var footerContainer = document.getElementById("footer-container");
  if (!footerContainer) return;

  footerContainer.innerHTML =
    '<footer class="footer">' +
      '<div class="footer-container">' +
        '<div>&copy; 2026 AI Resume Analyzer. University Project. All rights reserved.</div>' +
        '<div class="footer-links">' +
          '<a href="index.html">Home</a>' +
          '<a href="jobs.html">Browse Jobs</a>' +
          '<a href="/docs" target="_blank" rel="noopener noreferrer">API Docs</a>' +
        '</div>' +
      '</div>' +
    '</footer>';
}

// Automatically render Navbar and Footer when DOM is ready
document.addEventListener("DOMContentLoaded", function() {
  renderNavbar();
  renderFooter();
});