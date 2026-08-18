let sessionId = null;
let currentTurnIndex = 0;
let totalTopics = 0;
let ws = null;
let mediaRecorder = null;
let isInterviewActive = false;
let lockedDifficulty = "";
let submitRequestToken = 0;
let interviewStartTime = null;
let interviewTimerInterval = null;
const MAX_INTERVIEW_DURATION_MS = 10 * 60 * 1000; // 10 minutes

const $ = id => document.getElementById(id);

const REQUEST_TIMEOUT_MS = 20000;

// ── UI Enhancement Functions ──────────────────────────────────────────────

// Show a subtle toast notification
function showNotification(message, type = "info", duration = 3000) {
  const notification = document.createElement("div");
  notification.style.cssText = `
    position: fixed;
    top: 20px;
    right: 20px;
    padding: 1rem 1.5rem;
    border-radius: 10px;
    background: ${
      type === "success" ? "#10b981" : 
      type === "error" ? "#ef4444" : 
      "#3b82f6"
    };
    color: white;
    font-weight: 600;
    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.2);
    animation: slideIn 0.3s ease-out;
    z-index: 10000;
    font-size: 0.95rem;
    max-width: 400px;
  `;
  notification.textContent = message;
  document.body.appendChild(notification);
  
  setTimeout(() => {
    notification.style.animation = "slideOut 0.3s ease-in forwards";
    setTimeout(() => notification.remove(), 300);
  }, duration);
}

// Add animations to the document
const style = document.createElement("style");
style.textContent = `
  @keyframes slideIn {
    from { opacity: 0; transform: translateX(20px); }
    to { opacity: 1; transform: translateX(0); }
  }
  @keyframes slideOut {
    from { opacity: 1; transform: translateX(0); }
    to { opacity: 0; transform: translateX(20px); }
  }
`;
document.head.appendChild(style);

// Set loading state on buttons
function setButtonLoading(button, isLoading) {
  if (isLoading) {
    button.disabled = true;
    button.dataset.originalText = button.textContent;
    button.textContent = "⏳ Loading...";
    button.style.opacity = "0.6";
  } else {
    button.disabled = false;
    button.textContent = button.dataset.originalText || "Submit";
    button.style.opacity = "1";
  }
}

function setTimerVisible(visible) {
  const timerContainer = $("timer-container");
  if (!timerContainer) return;
  timerContainer.hidden = !visible;
}


async function fetchWithTimeout(url, options = {}, timeoutMs = REQUEST_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timeoutId);
  }
}

async function parseErrorMessage(res, fallbackMessage) {
  try {
    const payload = await res.json();
    if (payload && typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch (_) {
    // Non-JSON error bodies are common for 5xx responses; use fallback message.
  }
  return fallbackMessage;
}

function setInterviewActive(active, difficulty = "") {
  isInterviewActive = active;
  if (active) {
    lockedDifficulty = difficulty || "";
    $("difficulty-select").value = lockedDifficulty;
  } else {
    lockedDifficulty = "";
  }
  $("difficulty-select").disabled = active;
  $("context-select").disabled = active;
}

// Load session from localStorage on page load (C4: session recovery on refresh)
async function recoverSession() {
  const savedSessionId = localStorage.getItem("interviewSessionId");
  if (!savedSessionId) return false;

  try {
    const res = await fetch(`/interview/status/${savedSessionId}`);
    if (!res.ok) {
      localStorage.removeItem("interviewSessionId");
      return false;
    }
    const status = await res.json();
    sessionId = savedSessionId;
    totalTopics = status.total_topics;
    currentTurnIndex = status.global_turn_index;
    
    // Show interview UI; hide start controls
    $("answer-section").hidden = false;
    $("leave-btn").hidden = false;
    $("leave-btn").disabled = false;
    $("start-btn").hidden = true;
    $("context-select").hidden = true;
    $("difficulty-select").hidden = true;
    setTimerVisible(true);
    setInterviewActive(true, status.difficulty || "");
    totalTopics = status.total_topics || totalTopics || 0;
    const completedQuestions = Math.max(0, status.global_turn_index || 0);
    const currentQuestionNumber = Math.min(totalTopics || completedQuestions, completedQuestions + 1);
    updateProgress(currentQuestionNumber, totalTopics);
    
    // Start 10-minute timer (resumed)
    interviewStartTime = Date.now();
    if (interviewTimerInterval) clearInterval(interviewTimerInterval);
    interviewTimerInterval = setInterval(updateTimer, 1000);
    updateTimer();
    
    // Fetch and display current question
    // Note: For simplicity, show status; ideally fetch next question from backend
    $("question-text").textContent = `Resuming: ${status.current_topic_label || "Interview"}`;
    $("topic-badge").textContent = `Topic ${status.current_topic_index + 1} of ${status.total_topics}`;
    return true;
  } catch (e) {
    console.error("Session recovery failed:", e);
    localStorage.removeItem("interviewSessionId");
    return false;
  }
}

// Populate context dropdown on page load
async function loadContexts() {
  const res = await fetch("/interview/contexts");
  const data = await res.json();
  const sel = $("context-select");
  if (!data.contexts.length) {
    sel.innerHTML = '<option value="">No contexts found — upload via Admin</option>';
    $("start-btn").disabled = true;
    return;
  }
  sel.innerHTML = data.contexts
    .map(c => `<option value="${c}">${c.replace(/_/g, " ")}</option>`)
    .join("");
  $("start-btn").disabled = false;
}

function resetToMainPage() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close();
  }
  if (interviewTimerInterval) {
    clearInterval(interviewTimerInterval);
    interviewTimerInterval = null;
  }
  interviewStartTime = null;

  sessionId = null;
  // Invalidate in-flight submit responses so they cannot repopulate UI after leaving.
  submitRequestToken += 1;
  currentTurnIndex = 0;
  totalTopics = 0;
  setInterviewActive(false);
  localStorage.removeItem("interviewSessionId");

  $("answer-section").hidden = true;
  $("leave-btn").hidden = true;
  $("leave-btn").disabled = false;
  $("feedback-section").hidden = true;
  $("start-btn").hidden = false;
  $("start-btn").disabled = false;
  $("context-select").hidden = false;
  $("difficulty-select").hidden = false;
  setTimerVisible(false);

  $("text-answer").value = "";
  $("live-transcript").textContent = "";
  $("question-text").textContent = "Select a context below and press Start Interview.";
  $("topic-badge").textContent = "";
  $("stretch-badge").textContent = "";
  updateProgress(0, 0);
}

// On page load: try to recover session, then load contexts
(async () => {
  const recovered = await recoverSession();
  if (!recovered) loadContexts();
})();

async function startInterview() {
  const contextName = $("context-select").value;
  const difficulty = $("difficulty-select").value;
  if (!contextName) { 
    showNotification("📌 Please select a company context first.", "error");
    return; 
  }
  
  setButtonLoading($("start-btn"), true);
  showNotification("🚀 Starting interview...", "info", 1500);
  
  const res = await fetch("/interview/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ context_name: contextName, difficulty: difficulty || null }),
  });
  
  if (!res.ok) {
    setButtonLoading($("start-btn"), false);
    showNotification("❌ Failed to start interview. Check if context is set up.", "error", 4000);
    return;
  }
  
  const data = await res.json();
  sessionId = data.session_id;
  totalTopics = data.total_questions || data.first_question.total_topics || 0;
  setInterviewActive(true, difficulty || "");
  
  // Save to localStorage for recovery on refresh (C4)
  localStorage.setItem("interviewSessionId", sessionId);
  
  $("answer-section").hidden = false;
  $("leave-btn").hidden = false;
  $("leave-btn").disabled = false;
  $("start-btn").hidden = true;
  $("context-select").hidden = true;
  $("difficulty-select").hidden = true;
  setTimerVisible(true);
  
  // Start 10-minute timer
  interviewStartTime = Date.now();
  if (interviewTimerInterval) clearInterval(interviewTimerInterval);
  interviewTimerInterval = setInterval(updateTimer, 1000);
  updateTimer();
  displayQuestion(data.first_question);
  updateProgress(Math.max(1, (data.first_question.turn_index || 0) + 1), totalTopics);
  
  showNotification("✨ Interview started! Good luck!", "success", 2000);
}

function displayQuestion(q) {
  $("question-text").textContent = q.question_text;
  $("topic-badge").textContent = `Topic: ${q.topic_id}`;
  $("stretch-badge").textContent =
    q.question_type === "FOLLOW_UP" ? `Follow-up #${q.stretch_index}` : "Main Question";
  currentTurnIndex = q.turn_index;
  $("feedback-section").hidden = true;
  $("text-answer").value = "";
  $("live-transcript").textContent = "";
  $("submit-btn").disabled = false;

  // Keep progress in sync even when the next question comes from a follow-up path.
  const questionNumber = Math.max(1, (q.turn_index || 0) + 1);
  updateProgress(questionNumber, totalTopics || q.total_topics || 0);
}

function updateProgress(done, total) {
  const safeTotal = Math.max(0, total || 0);
  const safeDone = Math.max(0, Math.min(done || 0, safeTotal || done || 0));
  const pct = safeTotal > 0 ? (safeDone / safeTotal) * 100 : 0;
  $("progress-fill").style.width = pct + "%";
  $("progress-label").textContent = `${safeDone} / ${safeTotal} topics`;
}

function updateTimer() {
  if (!interviewStartTime) return;
  const elapsed = Date.now() - interviewStartTime;
  const remaining = Math.max(0, MAX_INTERVIEW_DURATION_MS - elapsed);
  const minutes = Math.floor(remaining / 60000);
  const seconds = Math.floor((remaining % 60000) / 1000);
  const timeStr = `${minutes}:${seconds.toString().padStart(2, '0')}`;
  
  const timerEl = $("interview-timer");
  if (timerEl) {
    timerEl.textContent = timeStr;
    timerEl.style.color = remaining < 60000 ? "#ef4444" : "inherit";
  }
  
  // Auto-end interview if time is up
  if (remaining === 0 && isInterviewActive) {
    alert("Interview time limit (10 minutes) reached. Ending interview.");
    leaveInterview();
  }
}

async function submitTextAnswer() {
  const answer = $("text-answer").value.trim();
  if (!answer) { 
    showNotification("📝 Please write an answer before submitting.", "error");
    return; 
  }
  
  const requestSessionId = sessionId;
  const requestToken = ++submitRequestToken;
  setButtonLoading($("submit-btn"), true);
  showNotification("🔄 Evaluating your answer...", "info", 2000);
  
  try {
    const res = await fetchWithTimeout("/interview/answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        session_id: sessionId,
        turn_index: currentTurnIndex,
        answer_text: answer,
        answer_mode: "TEXT",
      }),
    });

    if (!res.ok) {
      const message = await parseErrorMessage(res, "Failed to submit answer");
      showNotification(`❌ Error: ${message}`, "error", 4000);
      return;
    }

    const data = await res.json();
    if (requestToken !== submitRequestToken || requestSessionId !== sessionId) {
      return;
    }
    handleEvalResult(data);
  } catch (e) {
    if (e && e.name === "AbortError") {
      showNotification("⏱️ Request timed out. Please try again.", "error", 3000);
    } else {
      console.error("Submit answer request failed:", e);
      showNotification("❌ Network error. Please try again.", "error", 3000);
    }
  } finally {
    // If interview is still active, allow retry; completed flow keeps controls hidden.
    if (requestToken === submitRequestToken && sessionId) {
      setButtonLoading($("submit-btn"), false);
    }
  }
}

function handleEvalResult(data) {
  // Capture sessionId immediately before any state changes
  const completionSessionId = sessionId;
  
  const pct = Math.round(data.confidence_score * 100);
  $("score-pct").textContent = pct + "%";
  $("score-fill").style.width = pct + "%";
  $("score-fill").style.background =
    pct >= 80 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#ef4444";
  $("reasoning-text").textContent = data.reasoning;
  $("feedback-section").hidden = false;

  if (data.next_action === "COMPLETED") {
    setInterviewActive(false);
    $("answer-section").hidden = true;
    $("leave-btn").hidden = true;
    setTimerVisible(false);
    if (interviewTimerInterval) {
      clearInterval(interviewTimerInterval);
      interviewTimerInterval = null;
    }
    localStorage.removeItem("interviewSessionId");
    // Use captured completionSessionId instead of global sessionId
    setTimeout(() => { window.location.href = `/report/${completionSessionId}`; }, 2000);
  } else if (data.next_question) {
    currentTurnIndex = data.next_question.turn_index;
    // Update progress bar - show which question we're on (1-indexed for user display)
    updateProgress(data.next_question.turn_index + 1, totalTopics);
    setTimeout(() => displayQuestion(data.next_question), 1500);
  }
}

async function leaveInterview() {
  const reportSessionId = sessionId;
  if (!reportSessionId) {
    resetToMainPage();
    return;
  }

  // Show confirmation modal
  const confirmed = confirm("🛑 End interview? You'll see your feedback report on the next page.");
  if (!confirmed) {
    return;
  }

  $("leave-btn").disabled = true;
  showNotification("🔄 Ending interview...", "info", 1500);
  
  try {
    const res = await fetchWithTimeout(`/interview/leave/${reportSessionId}`, { method: "POST" });
    if (!res.ok && res.status !== 404) {
      const message = await parseErrorMessage(res, "unknown error");
      showNotification(`❌ Failed to leave: ${message}`, "error", 3000);
      $("leave-btn").disabled = false;
      return;
    }
  } catch (e) {
    if (e && e.name === "AbortError") {
      showNotification("⏱️ Request timed out. Redirecting to report...", "error", 2000);
    } else {
      console.error("Leave interview request failed:", e);
      showNotification("❌ Error ending interview. Redirecting...", "error", 2000);
    }
  }

  // Redirect to report page
  resetToMainPage();
  showNotification("📊 Loading your report...", "info", 1000);
  setTimeout(() => { window.location.href = `/report/${reportSessionId}`; }, 800);
}

function startAudioCapture() {
  if (!sessionId) return;
  ws = new WebSocket(`ws://${location.host}/ws/audio/${sessionId}`);
  ws.onmessage = e => {
    const msg = JSON.parse(e.data);
    if (msg.type === "partial") {
      $("live-transcript").textContent = msg.text;
    } else if (msg.type === "final") {
      $("text-answer").value += msg.text + " ";
      $("live-transcript").textContent = "";
    } else if (msg.type === "answer_result") {
      handleEvalResult(msg.data);
    }
  };
  navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
    // 250 ms chunks; browser sends webm or pcm depending on OS support
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = e => {
      if (ws.readyState === WebSocket.OPEN) ws.send(e.data);
    };
    mediaRecorder.start(250);
  });
}

function stopAudioCapture() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
  // Server-side silence timeout ends the Transcribe stream and triggers evaluation
}

$("start-btn").addEventListener("click", startInterview);
$("submit-btn").addEventListener("click", submitTextAnswer);
$("leave-btn").addEventListener("click", leaveInterview);
$("difficulty-select").addEventListener("change", () => {
  if (isInterviewActive) {
    $("difficulty-select").value = lockedDifficulty;
  }
});
$("mic-btn").addEventListener("mousedown", startAudioCapture);
$("mic-btn").addEventListener("mouseup", stopAudioCapture);
$("mic-btn").addEventListener("touchstart", startAudioCapture);
$("mic-btn").addEventListener("touchend", stopAudioCapture);
