/* Client-side career advisor interactive chat interface handlers */

var currentJobId = null;
var historyResumeId = null;

document.addEventListener("DOMContentLoaded", function() {
  if (window.location.pathname.includes("career-advisor.html")) {
    initAdvisorChat();
  }
});

async function initAdvisorChat() {
  var chatForm = document.getElementById("chat-form");
  var inputEl = document.getElementById("chat-user-input");
  var clearBtn = document.getElementById("clear-chat-btn");
  var resumeSelect = document.getElementById("chat-resume-select");
  var urlParams = new URLSearchParams(window.location.search);
  var targetResumeId = urlParams.get("resume_id");
  // Job context passed from "Ask Advisor about this job"
  var targetJobId = urlParams.get("job_id");
  currentJobId = targetJobId && /^\d+$/.test(targetJobId) ? parseInt(targetJobId, 10) : null;
  // Only scope history to a resume when the caller explicitly linked one
  historyResumeId = targetResumeId && /^\d+$/.test(targetResumeId) ? targetResumeId : null;

  // Load user's analyzed resumes into context dropdown
  try {
    var resumes = await apiFetch("/api/resumes");
    var analyzedResumes = resumes.filter(function(r) { return r.has_analysis; });

    if (resumeSelect) {
      if (analyzedResumes.length === 0) {
        resumeSelect.innerHTML = '<option value="">No analyzed resumes found</option>';
      } else {
        resumeSelect.innerHTML = analyzedResumes.map(function(r) {
          var selected = String(r.id) === String(targetResumeId) ? 'selected' : '';
          return '<option value="' + (Number(r.id) || 0) + '" ' + selected + '>' + escapeHtml(r.title) + '</option>';
        }).join('');
      }
    }
  } catch (err) {}

  // Static suggested-question chips (data-query avoids string-built onclick)
  var chipsBar = document.getElementById("suggested-chips-bar");
  if (chipsBar) {
    Array.prototype.forEach.call(chipsBar.querySelectorAll("[data-query]"), function(chip) {
      chip.addEventListener("click", function() { sendSuggestedQuery(chip.getAttribute("data-query")); });
    });
  }

  // Load past chat history
  loadChatHistory();

  // Clear chat button
  if (clearBtn) {
    clearBtn.onclick = function() {
      showConfirmModal({
        title: "Clear Chat History",
        message: "Are you sure you want to clear your conversation history with Career Advisor?",
        confirmText: "Clear History",
        confirmClass: "btn-danger",
        onConfirm: async function() {
          try {
            await apiFetch("/api/chat/history", { method: "DELETE" });
            var pane = document.getElementById("chat-messages-pane");
            if (pane) {
              pane.innerHTML =
                '<div class="chat-bubble chat-assistant">' +
                  '<strong>Chat history cleared.</strong>' +
                  '<p style="margin-top:6px;">How can I help you with your career today?</p>' +
                '</div>';
            }
            showToast("Chat history cleared.", "info");
          } catch (err) {}
        }
      });
    };
  }

  // Handle Send submit
  if (chatForm) {
    chatForm.onsubmit = function(e) {
      e.preventDefault();
      var message = inputEl.value.trim();
      if (!message) return;

      sendChatMessage(message);
      inputEl.value = "";
    };
  }
}

async function loadChatHistory() {
  var pane = document.getElementById("chat-messages-pane");
  if (!pane) return;

  try {
    var historyQs = "/api/chat/history";
    if (historyResumeId) {
      historyQs += "?resume_id=" + encodeURIComponent(historyResumeId);
    }
    var history = await apiFetch(historyQs);
    if (history && history.length > 0) {
      pane.innerHTML = history.map(function(msg) {
        var isUser = msg.sender === "user";
        var bubbleClass = isUser ? "chat-user" : "chat-assistant";
        var content = isUser ? escapeHtml(msg.message) : renderMarkdown(msg.message);

        return '<div class="chat-bubble ' + bubbleClass + '">' + content + '</div>';
      }).join('');
      pane.scrollTop = pane.scrollHeight;
    }
  } catch (err) {}
}

async function sendChatMessage(messageText) {
  var pane = document.getElementById("chat-messages-pane");
  var typingIndicator = document.getElementById("typing-indicator");
  var sendBtn = document.getElementById("chat-send-btn");
  var resumeSelect = document.getElementById("chat-resume-select");
  var selectedResumeId = resumeSelect ? resumeSelect.value : null;

  // Append user bubble
  var userBubble = document.createElement("div");
  userBubble.className = "chat-bubble chat-user";
  userBubble.innerText = messageText;
  pane.appendChild(userBubble);
  pane.scrollTop = pane.scrollHeight;

  // Show typing indicator
  if (typingIndicator) typingIndicator.style.display = "block";
  if (sendBtn) sendBtn.disabled = true;

  try {
    var payload = {
      message: messageText,
      resume_id: selectedResumeId ? parseInt(selectedResumeId, 10) : null,
      job_id: currentJobId
    };

    var response = await apiFetch("/api/chat", {
      method: "POST",
      body: JSON.stringify(payload)
    });

    if (typingIndicator) typingIndicator.style.display = "none";

    // Append Assistant response bubble
    var botBubble = document.createElement("div");
    botBubble.className = "chat-bubble chat-assistant";
    botBubble.innerHTML = renderMarkdown(response.reply);

    // If actionable recommendations exist in response
    if (response.actionable_recommendations && response.actionable_recommendations.length > 0) {
      var recsHtml = '<div style="margin-top:12px; border-top:1px solid var(--neutral-200); padding-top:8px;">' +
        '<strong style="font-size:0.85rem; color:var(--primary-700);">Recommended Action Items:</strong>' +
        '<ul style="margin-top:4px; padding-left:16px; font-size:0.85rem;">' +
        response.actionable_recommendations.map(function(r) {
          return '<li style="margin-bottom:4px;"><strong>' + escapeHtml(r.title) + '</strong> (' + escapeHtml(r.category) + ') — ' + escapeHtml(r.reason) + '</li>';
        }).join('') +
        '</ul></div>';
      botBubble.innerHTML += recsHtml;
    }

    pane.appendChild(botBubble);
    pane.scrollTop = pane.scrollHeight;

    // Update follow-up chips if present
    var chipsBar = document.getElementById("suggested-chips-bar");
    if (chipsBar && response.suggested_followups && response.suggested_followups.length > 0) {
      chipsBar.innerHTML = "";
      response.suggested_followups.forEach(function(q) {
        var chip = document.createElement("span");
        chip.className = "chip";
        chip.style.cursor = "pointer";
        chip.innerText = "💬 " + q;
        // Data is attached via dataset + listener (never string-built onclick)
        chip.addEventListener("click", function() { sendSuggestedQuery(q); });
        chipsBar.appendChild(chip);
      });
    }
  } catch (err) {
    if (typingIndicator) typingIndicator.style.display = "none";
    showToast("Failed to send message to Career Advisor.", "error");
  } finally {
    if (sendBtn) sendBtn.disabled = false;
  }
}

function sendSuggestedQuery(queryText) {
  var inputEl = document.getElementById("chat-user-input");
  if (inputEl) {
    inputEl.value = queryText;
    sendChatMessage(queryText);
    inputEl.value = "";
  }
}