let sessionId = null;
let currentTurnIndex = 0;
let totalTopics = 0;
let ws = null;
let mediaRecorder = null;

const $ = id => document.getElementById(id);

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
    $("start-btn").hidden = true;
    $("context-select").hidden = true;
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

// On page load: try to recover session, then load contexts
(async () => {
  const recovered = await recoverSession();
  if (!recovered) loadContexts();
})();

async function startInterview() {
  const contextName = $("context-select").value;
  if (!contextName) { alert("Please select a context."); return; }
  $("start-btn").disabled = true;
  const res = await fetch("/interview/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ context_name: contextName }),
  });
  if (!res.ok) {
    alert("Failed to start interview. Is the context ingested and questions file present?");
    $("start-btn").disabled = false;
    return;
  }
  const data = await res.json();
  sessionId = data.session_id;
  totalTopics = data.first_question.total_topics;
  
  // Save to localStorage for recovery on refresh (C4)
  localStorage.setItem("interviewSessionId", sessionId);
  
  $("answer-section").hidden = false;
  $("start-btn").hidden = true;
  $("context-select").hidden = true;
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
  $("submit-btn").disabled = true;
  const res = await fetch("/interview/answer", {
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
    const error = await res.json();
    alert(`Error: ${error.detail || "Failed to submit answer"}`);
    $("submit-btn").disabled = false;
    return;
  }
  
  const data = await res.json();
  handleEvalResult(data);
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
    $("answer-section").hidden = true;
    localStorage.removeItem("interviewSessionId");
    setTimeout(() => { window.location.href = `/report/${sessionId}`; }, 2000);
  } else if (data.next_question) {
    currentTurnIndex = data.next_question.turn_index;
    setTimeout(() => displayQuestion(data.next_question), 1500);
  }
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
$("mic-btn").addEventListener("mousedown", startAudioCapture);
$("mic-btn").addEventListener("mouseup", stopAudioCapture);
$("mic-btn").addEventListener("touchstart", startAudioCapture);
$("mic-btn").addEventListener("touchend", stopAudioCapture);
