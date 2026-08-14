const $ = id => document.getElementById(id);

async function loadContexts() {
  const res = await fetch("/admin/contexts");
  const data = await res.json();
  const list = $("contexts-list");
  const sel = $("gen-context-select");

  if (!data.contexts.length) {
    list.innerHTML = '<p class="muted">No context documents found. Upload one below.</p>';
    return;
  }

  list.innerHTML = data.contexts.map(c => `
    <div class="context-row">
      <span class="context-name">${c.context_name}</span>
      <span class="filename muted">${c.filename}</span>
      <span class="badge ${c.has_questions ? "badge-green" : "badge-yellow"}">
        ${c.has_questions ? "Questions ready" : "No questions yet"}
      </span>
    </div>
  `).join("");

  // Populate generate dropdown
  sel.innerHTML = '<option value="">Select context...</option>' +
    data.contexts.map(c =>
      `<option value="${c.context_name}">${c.context_name.replace(/_/g, " ")}</option>`
    ).join("");
}

async function uploadFile() {
  const fileInput = $("file-input");
  if (!fileInput.files.length) { alert("Please select a file first."); return; }

  const btn = $("upload-btn");
  btn.disabled = true;
  btn.textContent = "Ingesting...";

  const form = new FormData();
  form.append("file", fileInput.files[0]);

  const statusBox = $("upload-status");
  statusBox.hidden = false;
  statusBox.className = "status-box status-info";
  statusBox.textContent = `Uploading and chunking ${fileInput.files[0].name}...`;

  const res = await fetch("/admin/upload", { method: "POST", body: form });
  const data = await res.json();

  if (res.ok) {
    statusBox.className = "status-box status-success";
    statusBox.textContent =
      `✓ Ingested "${data.context_name}" — ` +
      `${data.chunks_inserted} new chunks (${data.chunks_cached} cached, ${data.total_chunks} total).`;
    loadContexts();
  } else {
    statusBox.className = "status-box status-error";
    statusBox.textContent = `✗ Error: ${data.detail || JSON.stringify(data)}`;
  }

  btn.disabled = false;
  btn.textContent = "Upload & Ingest";
}

async function generateQuestions() {
  const contextName = $("gen-context-select").value;
  const numTopics = parseInt($("num-topics").value) || 5;
  if (!contextName) { alert("Please select a context."); return; }

  const btn = $("gen-btn");
  btn.disabled = true;
  btn.textContent = "Generating...";

  const statusBox = $("gen-status");
  statusBox.hidden = false;
  statusBox.className = "status-box status-info";
  statusBox.textContent = `Calling Claude Sonnet to generate ${numTopics} questions for "${contextName}"...`;

  const form = new FormData();
  form.append("context_name", contextName);
  form.append("num_topics", numTopics);

  const res = await fetch("/admin/generate-questions", { method: "POST", body: form });
  const data = await res.json();

  if (res.ok) {
    statusBox.className = "status-box status-success";
    statusBox.textContent = `✓ Generated ${data.num_topics} questions. Saved to ${data.saved_to}`;

    const preview = $("topics-preview");
    preview.innerHTML = data.topics.map((t, i) => `
      <div class="topic-card">
        <strong>${i + 1}. ${t.topic_label}</strong>
        <p>${t.seed_question}</p>
      </div>
    `).join("");
    $("gen-results").hidden = false;
    loadContexts();
  } else {
    statusBox.className = "status-box status-error";
    statusBox.textContent = `✗ Error: ${data.detail || JSON.stringify(data)}`;
  }

  btn.disabled = false;
  btn.textContent = "Generate";
}

loadContexts();
