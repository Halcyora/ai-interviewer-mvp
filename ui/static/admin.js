const $ = id => document.getElementById(id);

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

async function loadContexts() {
  const res = await fetch("/admin/contexts");
  const data = await res.json();
  const list = $("contexts-list");
  const sel = $("gen-context-select");

  if (!data.contexts.length) {
    list.innerHTML = '<p class="muted">📭 No context documents found. Upload one below to get started!</p>';
    return;
  }

  list.innerHTML = data.contexts.map(c => `
    <div class="context-row">
      <span class="context-name">${c.context_name}</span>
      <span class="filename muted">${c.filename}</span>
      <span class="badge ${c.has_questions ? "badge-green" : "badge-yellow"}">
        ${c.has_questions ? "✓ Ready" : "⚠ Pending"}
      </span>
    </div>
  `).join("");

  // Populate generate dropdown
  sel.innerHTML = '<option value="">📖 Select a context...</option>' +
    data.contexts.map(c =>
      `<option value="${c.context_name}">${c.context_name.replace(/_/g, " ")}</option>`
    ).join("");
}

async function uploadFile() {
  const fileInput = $("file-input");
  if (!fileInput.files.length) { 
    showNotification("📁 Please select a file first.", "error");
    return; 
  }

  const btn = $("upload-btn");
  btn.disabled = true;
  btn.textContent = "⏳ Ingesting...";

  const form = new FormData();
  form.append("file", fileInput.files[0]);

  const statusBox = $("upload-status");
  statusBox.hidden = false;
  statusBox.className = "status-box status-info";
  statusBox.textContent = `📤 Uploading and chunking ${fileInput.files[0].name}...`;

  showNotification("🔄 Processing your document...", "info", 2000);

  const res = await fetch("/admin/upload", { method: "POST", body: form });
  const data = await res.json();

  if (res.ok) {
    statusBox.className = "status-box status-success";
    statusBox.textContent =
      `✅ Ingested "${data.context_name}" — ` +
      `${data.chunks_inserted} new chunks (${data.chunks_cached} cached, ${data.total_chunks} total).`;
    fileInput.value = "";
    loadContexts();
    showNotification("✨ Document ingested successfully!", "success", 3000);
  } else {
    statusBox.className = "status-box status-error";
    statusBox.textContent = `❌ Error: ${data.detail || JSON.stringify(data)}`;
    showNotification("❌ Failed to ingest document. Check the error details.", "error", 4000);
  }

  btn.disabled = false;
  btn.textContent = "📤 Upload & Ingest";
}

async function generateQuestions() {
  const contextName = $("gen-context-select").value;
  const numTopics = parseInt($("num-topics").value) || 5;
  if (!contextName) { 
    showNotification("📌 Please select a context first.", "error");
    return; 
  }

  const btn = $("gen-btn");
  btn.disabled = true;
  btn.textContent = "⏳ Generating...";

  const statusBox = $("gen-status");
  statusBox.hidden = false;
  statusBox.className = "status-box status-info";
  statusBox.textContent = `⚙️ Calling Claude to generate ${numTopics} questions for "${contextName}"...`;

  showNotification("🤖 AI is creating questions...", "info", 2000);

  const form = new FormData();
  form.append("context_name", contextName);
  form.append("num_topics", numTopics);

  const res = await fetch("/admin/generate-questions", { method: "POST", body: form });
  const data = await res.json();

  if (res.ok) {
    statusBox.className = "status-box status-success";
    statusBox.textContent = `✅ Generated ${data.num_topics} questions. Saved to ${data.saved_to}`;

    const preview = $("topics-preview");
    preview.innerHTML = data.topics.map((t, i) => `
      <div class="topic-card">
        <strong>${i + 1}. ${t.topic_label}</strong>
        <p>${t.seed_question}</p>
      </div>
    `).join("");
    $("gen-results").hidden = false;
    loadContexts();
    showNotification("✨ Questions generated successfully!", "success", 3000);
  } else {
    statusBox.className = "status-box status-error";
    statusBox.textContent = `❌ Error: ${data.detail || JSON.stringify(data)}`;
    showNotification("❌ Failed to generate questions. Check the error.", "error", 4000);
  }

  btn.disabled = false;
  btn.textContent = "✨ Generate";
}

loadContexts();
