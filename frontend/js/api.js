/* Central HTTP client fetch wrapper with JWT attachment and unified error handling.
   All pages must use apiFetch() instead of direct fetch() calls.
   - Attaches Authorization: Bearer <token> from localStorage
   - Handles JSON body and multipart FormData (file uploads)
   - Parses {"detail": "..."} errors into readable toasts (including on login/register)
   - On 401 outside auth pages: clears token/user and redirects to login
   - Never throws a bare network/parse error without telling the user
*/

async function apiFetch(endpoint, options) {
  options = options || {};
  var baseUrl = "/api";
  var fullUrl = endpoint.startsWith("/") ? endpoint : baseUrl + "/" + endpoint;
  var token = localStorage.getItem("token");
  var headers = {};

  if (options.headers) {
    var existingHeaders = options.headers;
    if (existingHeaders instanceof Headers) {
      existingHeaders.forEach(function(value, key) { headers[key] = value; });
    } else if (typeof existingHeaders === 'object') {
      Object.keys(existingHeaders).forEach(function(key) { headers[key] = existingHeaders[key]; });
    }
  }

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  if (token) {
    headers["Authorization"] = "Bearer " + token;
  }

  var response;
  try {
    response = await fetch(fullUrl, {
      method: options.method || "GET",
      headers: headers,
      body: options.body
    });
  } catch (networkErr) {
    console.error("API network error:", networkErr);
    showToast("Could not reach the server. Please check your connection and try again.", "error");
    var netError = new Error("Network error");
    netError.isNetwork = true;
    throw netError;
  }

  // Response body may be JSON, empty, or an HTML error page from a proxy
  var data = null;
  var raw = await response.text();
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch (parseErr) {
      data = null;
    }
  }

  if (response.status === 401) {
    var detail401 = (data && data.detail) || "Invalid email or password.";
    var onAuthPage =
      window.location.pathname.includes("login.html") ||
      window.location.pathname.includes("register.html");

    if (onAuthPage) {
      // Surface the API's own message (e.g. "Invalid email or password.")
      showToast(detail401, "error");
      throw new Error(detail401);
    }

    localStorage.removeItem("token");
    localStorage.removeItem("user");
    showToast("Session expired. Please log in again.", "error");
    setTimeout(function() { window.location.href = "login.html"; }, 1500);
    throw new Error("Unauthorized");
  }

  if (!response.ok) {
    var errorMessage = (data && data.detail)
      || ("Request failed with status " + response.status + ".");
    showToast(errorMessage, "error");
    throw new Error(errorMessage);
  }

  return data;
}
