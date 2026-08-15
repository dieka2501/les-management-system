const state = {
  sessions: [],
  activeSession: null,
  faqScript: [],
  trainingExamples: [],
  editingResponseId: null,
  replyMode: "rule_based",
};

const els = {};

document.addEventListener("DOMContentLoaded", () => {
  Object.assign(els, {
    sessionList: document.getElementById("sessionList"),
    sessionCount: document.getElementById("sessionCount"),
    sessionTitleInput: document.getElementById("sessionTitleInput"),
    activeSessionTitle: document.getElementById("activeSessionTitle"),
    activeSessionMeta: document.getElementById("activeSessionMeta"),
    stagePill: document.getElementById("stagePill"),
    chatThread: document.getElementById("chatThread"),
    messageForm: document.getElementById("messageForm"),
    messageInput: document.getElementById("messageInput"),
    replyModeSelect: document.getElementById("replyModeSelect"),
    trainingCount: document.getElementById("trainingCount"),
    trainingExamples: document.getElementById("trainingExamples"),
    faqScript: document.getElementById("faqScript"),
    toast: document.getElementById("toast"),
    logoutButton: document.getElementById("logoutButton"),
  });

  document.getElementById("refreshButton").addEventListener("click", loadAll);
  document.getElementById("newSessionButton").addEventListener("click", () => createSession(false));
  document.getElementById("seedButton").addEventListener("click", () => createSession(true));
  document.getElementById("copyTrainingButton").addEventListener("click", copyTrainingExamples);
  els.logoutButton.addEventListener("click", logoutProvider);
  els.replyModeSelect.addEventListener("change", handleReplyModeChange);
  els.messageForm.addEventListener("submit", sendMessage);
  els.sessionList.addEventListener("click", handleSessionClick);
  els.chatThread.addEventListener("click", handleChatThreadClick);
  els.chatThread.addEventListener("submit", handleChatThreadSubmit);

  state.replyMode = normalizeReplyMode(localStorage.getItem("providerChatReplyMode"));
  els.replyModeSelect.value = state.replyMode;
  loadAll();
});

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      window.location.href = "/provider/login";
      return new Promise(() => {});
    }
    throw new Error(payload.error || "Request gagal.");
  }
  return payload;
}

async function logoutProvider() {
  try {
    await api("/api/provider/logout", { method: "POST", body: JSON.stringify({}) });
  } catch {
    // Tetap arahkan ke login walaupun request logout gagal, agar user tidak tersangkut di UI.
  }
  window.location.href = "/provider/login";
}

async function loadAll() {
  try {
    const [sessionsPayload, faqPayload, trainingPayload] = await Promise.all([
      api("/api/provider/chat-simulations"),
      api("/api/provider/chat-simulations/faq-script"),
      api("/api/provider/chat-simulations/training-examples"),
    ]);
    state.sessions = sessionsPayload.items || [];
    state.faqScript = faqPayload.items || [];
    state.trainingExamples = trainingPayload.items || [];
    renderSessions();
    renderFaq();
    renderTrainingExamples();

    if (state.activeSession) {
      await openSession(state.activeSession.id, { silent: true });
    } else if (state.sessions.length) {
      await openSession(state.sessions[0].id, { silent: true });
    } else {
      renderActiveSession();
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

async function createSession(seedFromFaq) {
  const title = els.sessionTitleInput.value.trim() || "Latihan CS Knowledge Base";
  try {
    const session = await api("/api/provider/chat-simulations", {
      method: "POST",
      body: JSON.stringify({ title, seed_from_faq: seedFromFaq }),
    });
    state.activeSession = session;
    showToast(seedFromFaq ? "Sesi knowledge base siap." : "Sesi baru siap.");
    await loadAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function openSession(sessionId, options = {}) {
  try {
    state.activeSession = await api(`/api/provider/chat-simulations/${sessionId}`);
    renderActiveSession();
    renderSessions();
    if (!options.silent) {
      showToast(`Membuka ${state.activeSession.code}.`);
    }
  } catch (error) {
    showToast(error.message, true);
  }
}

async function sendMessage(event) {
  event.preventDefault();
  if (!state.activeSession) {
    showToast("Buat sesi dulu.", true);
    return;
  }
  const message = els.messageInput.value.trim();
  if (!message) return;

  setComposerDisabled(true);
  try {
    const result = await api(`/api/provider/chat-simulations/${state.activeSession.id}/messages`, {
      method: "POST",
      body: JSON.stringify({ message, mode: state.replyMode }),
    });
    els.messageInput.value = "";
    state.activeSession = result.session;
    renderActiveSession();
    await refreshTrainingExamples();
  } catch (error) {
    showToast(error.message, true);
  } finally {
    setComposerDisabled(false);
    els.messageInput.focus();
  }
}

function handleReplyModeChange() {
  state.replyMode = normalizeReplyMode(els.replyModeSelect.value);
  els.replyModeSelect.value = state.replyMode;
  localStorage.setItem("providerChatReplyMode", state.replyMode);
  showToast(state.replyMode === "gemini" ? "Mode Gemini AI aktif." : "Mode rule-based aktif.");
}

function normalizeReplyMode(value) {
  return value === "gemini" ? "gemini" : "rule_based";
}

function handleSessionClick(event) {
  const button = event.target.closest("[data-session-id]");
  if (!button) return;
  openSession(Number(button.dataset.sessionId));
}

function renderSessions() {
  els.sessionCount.textContent = `${state.sessions.length} sesi`;
  if (!state.sessions.length) {
    els.sessionList.innerHTML = `<div class="empty-state">Belum ada sesi.</div>`;
    return;
  }

  els.sessionList.innerHTML = state.sessions
    .map((session) => {
      const active = state.activeSession && Number(state.activeSession.id) === Number(session.id);
      return `
        <button class="session-item ${active ? "active" : ""}" type="button" data-session-id="${session.id}">
          <span class="item-title">
            <span>${escapeHtml(session.code)}</span>
            <span class="status-pill ${session.current_stage === "needs_review" ? "review" : ""}">
              ${escapeHtml(session.current_stage)}
            </span>
          </span>
          <span class="item-meta">${escapeHtml(session.title)}</span>
          <span class="item-meta">${Number(session.message_count || 0)} pesan</span>
        </button>
      `;
    })
    .join("");
}

function renderActiveSession() {
  const session = state.activeSession;
  if (!session) {
    els.activeSessionTitle.textContent = "Belum ada sesi";
    els.activeSessionMeta.textContent = "Buat sesi untuk mulai simulasi.";
    els.stagePill.textContent = "start";
    els.stagePill.classList.remove("review");
    els.chatThread.innerHTML = `<div class="empty-state">Belum ada percakapan.</div>`;
    setComposerDisabled(true);
    return;
  }

  els.activeSessionTitle.textContent = `${session.code} - ${session.title}`;
  els.activeSessionMeta.textContent = `${session.channel} / ${session.source} / ${session.status}`;
  els.stagePill.textContent = session.current_stage;
  els.stagePill.classList.toggle("review", session.current_stage === "needs_review");
  const isTransferredToAdmin = session.current_stage === "transferred_to_admin";
  setComposerDisabled(isTransferredToAdmin);
  els.messageInput.placeholder = isTransferredToAdmin
    ? "Chat sudah diteruskan ke admin."
    : "Tulis pesan calon orang tua...";

  const messages = session.messages || [];
  if (!messages.length) {
    els.chatThread.innerHTML = `<div class="empty-state">Kirim pesan pertama dari calon orang tua.</div>`;
    return;
  }

  els.chatThread.innerHTML = messages.map(renderMessage).join("");
  els.chatThread.scrollTop = els.chatThread.scrollHeight;
}

function renderMessage(message) {
  const isParent = message.role === "parent";
  const label = isParent ? "Calon orang tua" : "Asisten";
  const isEditing = state.editingResponseId === Number(message.id);
  const tags = [
    message.intent,
    message.matched_reference,
    message.needs_review ? "needs review" : "",
  ].filter(Boolean);

  return `
    <article class="message ${isParent ? "parent" : "assistant"}" data-message-id="${message.id}">
      <small>${label}</small>
      ${
        isEditing
          ? `
            <form class="edit-response-form" data-message-id="${message.id}">
              <textarea name="message" rows="4" required>${escapeHtml(message.message)}</textarea>
              <div class="edit-actions">
                <button class="secondary compact" type="button" data-action="cancel-response-edit">Batal</button>
                <button class="compact" type="submit">Simpan respons</button>
              </div>
            </form>
          `
          : `<div>${escapeHtml(message.message)}</div>`
      }
      <div class="message-meta">
        ${tags.map((tag) => `<span class="tag ${message.needs_review ? "review" : ""}">${escapeHtml(tag)}</span>`).join("")}
      </div>
      ${
        !isParent && !isEditing
          ? `<div class="message-actions"><button class="text-button" type="button" data-action="edit-response" data-message-id="${message.id}">Edit respons</button></div>`
          : ""
      }
    </article>
  `;
}

function handleChatThreadClick(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;

  if (button.dataset.action === "edit-response") {
    state.editingResponseId = Number(button.dataset.messageId);
    renderActiveSession();
    focusResponseEditor();
  }

  if (button.dataset.action === "cancel-response-edit") {
    state.editingResponseId = null;
    renderActiveSession();
  }
}

async function handleChatThreadSubmit(event) {
  const form = event.target.closest(".edit-response-form");
  if (!form) return;
  event.preventDefault();
  if (!state.activeSession) return;

  const messageId = Number(form.dataset.messageId);
  const message = form.elements.message.value.trim();
  if (!message) {
    showToast("Respons tidak boleh kosong.", true);
    return;
  }

  try {
    const result = await api(`/api/provider/chat-simulations/${state.activeSession.id}/messages/${messageId}`, {
      method: "PUT",
      body: JSON.stringify({ message }),
    });
    state.editingResponseId = null;
    state.activeSession = result.session;
    renderActiveSession();
    await refreshTrainingExamples();
    showToast("Respons disimpan.");
  } catch (error) {
    showToast(error.message, true);
  }
}

function focusResponseEditor() {
  const editor = els.chatThread.querySelector(".edit-response-form textarea");
  if (editor) {
    editor.focus();
    editor.setSelectionRange(editor.value.length, editor.value.length);
  }
}

function renderFaq() {
  if (!state.faqScript.length) {
    els.faqScript.innerHTML = `<div class="empty-state">Knowledge base belum tersedia.</div>`;
    return;
  }

  els.faqScript.innerHTML = state.faqScript
    .map((item) => `
      <article class="faq-item">
        <strong>${escapeHtml(item.sequence)}. ${escapeHtml(item.intent)}</strong>
        <p>${escapeHtml(item.parent_message)}</p>
        <p>${escapeHtml(item.expected_reply)}</p>
      </article>
    `)
    .join("");
}

function renderTrainingExamples() {
  els.trainingCount.textContent = `${state.trainingExamples.length} contoh`;
  if (!state.trainingExamples.length) {
    els.trainingExamples.innerHTML = `<div class="empty-state">Belum ada dataset.</div>`;
    return;
  }

  els.trainingExamples.innerHTML = state.trainingExamples
    .slice()
    .reverse()
    .map((item) => `
      <article class="example-item">
        <strong>${escapeHtml(item.session_code)} / ${escapeHtml(item.intent || "unknown")}</strong>
        <p>${escapeHtml(item.parent_message)}</p>
        <p>${escapeHtml(item.expected_reply || "")}</p>
        <div class="message-meta">
          <span class="tag ${item.needs_review ? "review" : ""}">${item.needs_review ? "review" : "ready"}</span>
          ${item.edited_by_provider ? `<span class="tag">koreksi aktif</span>` : ""}
          <span class="tag">${escapeHtml(item.matched_reference || "no-ref")}</span>
        </div>
      </article>
    `)
    .join("");
}

async function refreshTrainingExamples() {
  const payload = await api("/api/provider/chat-simulations/training-examples");
  state.trainingExamples = payload.items || [];
  renderTrainingExamples();
}

async function copyTrainingExamples() {
  const text = JSON.stringify(state.trainingExamples, null, 2);
  try {
    await navigator.clipboard.writeText(text);
    showToast("Dataset disalin.");
  } catch {
    showToast("Clipboard browser menolak akses.", true);
  }
}

function setComposerDisabled(disabled) {
  els.messageInput.disabled = disabled;
  els.messageForm.querySelector("button").disabled = disabled;
}

function showToast(message, isError = false) {
  els.toast.textContent = message;
  els.toast.classList.toggle("error", isError);
  els.toast.hidden = false;
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => {
    els.toast.hidden = true;
  }, 3200);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
