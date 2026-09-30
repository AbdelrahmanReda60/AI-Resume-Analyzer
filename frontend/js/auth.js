/* Client-side authentication logic and session state management */

function checkAuth() {
  var token = localStorage.getItem("token");
  var path = window.location.pathname;
  var isAuthPage = path.includes("login.html") || path.includes("register.html");
  var isPublicPage = path === "/" || path.includes("index.html") || path.includes("jobs.html");

  if (!token) {
    if (!isAuthPage && !isPublicPage) {
      window.location.href = "login.html";
    }
    return false;
  }

  if (isAuthPage) {
    window.location.href = "dashboard.html";
    return true;
  }

  return true;
}

function logoutUser() {
  var token = localStorage.getItem("token");

  // Tell the server first (best effort), then always clear the local session
  if (token) {
    fetch("/api/auth/logout", {
      method: "POST",
      headers: { "Authorization": "Bearer " + token }
    }).catch(function() { /* offline logout still succeeds locally */ });
  }

  localStorage.removeItem("token");
  localStorage.removeItem("user");
  showToast("Logged out successfully.", "info");
  setTimeout(function() {
    window.location.href = "index.html";
  }, 500);
}

function getToken() {
  return localStorage.getItem("token");
}

function getUser() {
  var userStr = localStorage.getItem("user");
  try {
    return userStr ? JSON.parse(userStr) : null;
  } catch (e) {
    return null;
  }
}

/* ---------------- Inline validation helpers ---------------- */

function setFieldError(inputId, message) {
  var input = document.getElementById(inputId);
  var errorEl = document.getElementById(inputId.replace(/^(login|register)-/, "") + "-error");
  if (input) input.classList.add("is-error");
  if (errorEl) errorEl.textContent = message;
}

function clearFieldError(inputId) {
  var input = document.getElementById(inputId);
  var errorEl = document.getElementById(inputId.replace(/^(login|register)-/, "") + "-error");
  if (input) input.classList.remove("is-error");
  if (errorEl) errorEl.textContent = "";
}

function isValidEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function bindLiveValidation(inputId, validator) {
  var input = document.getElementById(inputId);
  if (!input) return;
  input.addEventListener("input", function() {
    var value = input.value.trim();
    if (!value) { clearFieldError(inputId); return; }
    var message = validator(value);
    if (message) setFieldError(inputId, message);
    else clearFieldError(inputId);
  });
  input.addEventListener("blur", function() {
    var value = input.value.trim();
    if (!value) return;
    var message = validator(value);
    if (message) setFieldError(inputId, message);
    else clearFieldError(inputId);
  });
}

/* ---------------- Form bindings ---------------- */

document.addEventListener("DOMContentLoaded", function() {
  checkAuth();

  // Attach aria-live so screen readers announce inline errors
  ["email-error", "password-error", "name-error"].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) {
      el.setAttribute("aria-live", "polite");
      el.setAttribute("role", "alert");
    }
  });

  bindLiveValidation("login-email", function(v) {
    return isValidEmail(v) ? "" : "Enter a valid email address.";
  });
  bindLiveValidation("register-email", function(v) {
    return isValidEmail(v) ? "" : "Enter a valid email address.";
  });
  bindLiveValidation("register-name", function(v) {
    return v.length >= 2 ? "" : "Please enter your full name.";
  });
  bindLiveValidation("register-password", function(v) {
    return v.length >= 8 ? "" : "Password must be at least 8 characters long.";
  });

  var loginForm = document.getElementById("login-form");
  if (loginForm) {
    loginForm.onsubmit = async function(e) {
      e.preventDefault();
      var submitBtn = document.getElementById("login-submit-btn");
      var email = document.getElementById("login-email").value.trim();
      var password = document.getElementById("login-password").value;

      var valid = true;
      if (!email) { setFieldError("login-email", "Email is required."); valid = false; }
      else if (!isValidEmail(email)) { setFieldError("login-email", "Enter a valid email address."); valid = false; }
      else clearFieldError("login-email");

      if (!password) { setFieldError("login-password", "Password is required."); valid = false; }
      else clearFieldError("login-password");

      if (!valid) return;

      submitBtn.classList.add("btn-loading");
      submitBtn.disabled = true;

      try {
        var data = await apiFetch("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ email: email, password: password })
        });

        localStorage.setItem("token", data.access_token);
        localStorage.setItem("user", JSON.stringify(data.user));

        showToast("Login successful!", "success");
        setTimeout(function() {
          window.location.href = "dashboard.html";
        }, 500);
      } catch (err) {
        // apiFetch already surfaced the API's {"detail": "..."} message
        if (err && err.message && !err.isNetwork) {
          setFieldError("login-password", err.message);
        }
      } finally {
        submitBtn.classList.remove("btn-loading");
        submitBtn.disabled = false;
      }
    };
  }

  var registerForm = document.getElementById("register-form");
  if (registerForm) {
    registerForm.onsubmit = async function(e) {
      e.preventDefault();
      var submitBtn = document.getElementById("register-submit-btn");
      var name = document.getElementById("register-name").value.trim();
      var email = document.getElementById("register-email").value.trim();
      var password = document.getElementById("register-password").value;

      var valid = true;
      if (!name || name.length < 2) { setFieldError("register-name", "Please enter your full name."); valid = false; }
      else clearFieldError("register-name");

      if (!email) { setFieldError("register-email", "Email is required."); valid = false; }
      else if (!isValidEmail(email)) { setFieldError("register-email", "Enter a valid email address."); valid = false; }
      else clearFieldError("register-email");

      if (!password) { setFieldError("register-password", "Password is required."); valid = false; }
      else if (password.length < 8) { setFieldError("register-password", "Password must be at least 8 characters long."); valid = false; }
      else clearFieldError("register-password");

      if (!valid) return;

      submitBtn.classList.add("btn-loading");
      submitBtn.disabled = true;

      try {
        var data = await apiFetch("/api/auth/register", {
          method: "POST",
          body: JSON.stringify({ full_name: name, email: email, password: password })
        });

        localStorage.setItem("token", data.access_token);
        localStorage.setItem("user", JSON.stringify(data.user));

        showToast("Registration successful!", "success");
        setTimeout(function() {
          window.location.href = "dashboard.html";
        }, 500);
      } catch (err) {
        if (err && err.message && !err.isNetwork) {
          setFieldError("register-email", err.message);
        }
      } finally {
        submitBtn.classList.remove("btn-loading");
        submitBtn.disabled = false;
      }
    };
  }
});

var auth = {
  checkAuth: checkAuth,
  logout: logoutUser,
  getToken: getToken,
  getUser: getUser
};
