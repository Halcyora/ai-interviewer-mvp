let sessionId = null;
let currentTurnIndex = 0;
let totalTopics = 0;
let ws = null;
let mediaRecorder = null;
let isInterviewActive = false;
let lockedDifficulty = "";
let submitRequestToken = 0;

const $ = id => document.getElementById(id);

const REQUEST_TIMEOUT_MS = 20000;

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
    setInterviewActive(true, status.difficulty || "");
    updateProgress(status.current_topic_index, status.total_topics);
    
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
  if (!contextName) { alert("Please select a context."); return; }
  $("start-btn").disabled = true;
  const res = await fetch("/interview/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ context_name: contextName, difficulty: difficulty || null }),
  });
  if (!res.ok) {
    alert("Failed to start interview. Is the context ingested and questions file present?");
    $("start-btn").disabled = false;
    return;
  }
  const data = await res.json();
  sessionId = data.session_id;
  totalTopics = data.first_question.total_topics;
  setInterviewActive(true, difficulty || "");
  
  // Save to localStorage for recovery on refresh (C4)
  localStorage.setItem("interviewSessionId", sessionId);
  
  $("answer-section").hidden = false;
  $("leave-btn").hidden = false;
  $("leave-btn").disabled = false;
  $("start-btn").hidden = true;
  $("context-select").hidden = true;
  $("difficulty-select").hidden = true;
  displayQuestion(data.first_question);
  updateProgress(0, data.first_question.total_topics);
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
}

function updateProgress(done, total) {
  const pct = total > 0 ? (done / total) * 100 : 0;
  $("progress-fill").style.width = pct + "%";
  $("progress-label").textContent = `${done} / ${total} topics`;
}

async function submitTextAnswer() {
  const answer = $("text-answer").value.trim();
  if (!answer) return;
  const requestSessionId = sessionId;
  const requestToken = ++submitRequestToken;
  $("submit-btn").disabled = true;
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
      alert(`Error: ${message}`);
      return;
    }

    const data = await res.json();
    if (requestToken !== submitRequestToken || requestSessionId !== sessionId) {
      return;
    }
    handleEvalResult(data);
  } catch (e) {
    if (e && e.name === "AbortError") {
      alert("Submit timed out. Please try again.");
    } else {
      console.error("Submit answer request failed:", e);
      alert("Submit failed due to a network or server error.");
    }
  } finally {
    // If interview is still active, allow retry; completed flow keeps controls hidden.
    if (requestToken === submitRequestToken && sessionId) {
      $("submit-btn").disabled = false;
    }
  }
}

function handleEvalResult(data) {
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
    localStorage.removeItem("interviewSessionId");
    setTimeout(() => { window.location.href = `/report/${sessionId}`; }, 2000);
  } else if (data.next_question) {
    currentTurnIndex = data.next_question.turn_index;
    setTimeout(() => displayQuestion(data.next_question), 1500);
  }
}

async function leaveInterview() {
  if (!sessionId) {
    resetToMainPage();
    return;
  }

  $("leave-btn").disabled = true;
  try {
    const res = await fetchWithTimeout(`/interview/leave/${sessionId}`, { method: "POST" });
    if (!res.ok && res.status !== 404) {
      const message = await parseErrorMessage(res, "unknown error");
      alert(`Failed to leave interview: ${message}`);
      $("leave-btn").disabled = false;
      return;
    }
  } catch (e) {
    if (e && e.name === "AbortError") {
      alert("Leave request timed out. Returning to main page.");
    } else {
      console.error("Leave interview request failed:", e);
    }
  }

  resetToMainPage();
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
