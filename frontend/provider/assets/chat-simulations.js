const state = {
  sessions: [],
  activeSession: null,
  faqScript: [],
  trainingExamples: [],
  editingResponseId: null,
  sessionFilter: "all",
  currentView: "chat",
};

const els = {};

document.addEventListener("DOMContentLoaded", () => {
  Object.assign(els, {
    pageTitle: document.getElementById("pageTitle"),
    navLinks: Array.from(document.querySelectorAll("[data-view-target]")),
    viewPanels: Array.from(document.querySelectorAll("[data-view-panel]")),
    sessionList: document.getElementById("sessionList"),
    sessionFilters: document.getElementById("sessionFilters"),
    sessionCount: document.getElementById("sessionCount"),
    sessionTitleInput: document.getElementById("sessionTitleInput"),
    activeSessionTitle: document.getElementById("activeSessionTitle"),
    activeSessionMeta: document.getElementById("activeSessionMeta"),
    stagePill: document.getElementById("stagePill"),
    supervisionActions: document.getElementById("supervisionActions"),
    chatThread: document.getElementById("chatThread"),
    messageForm: document.getElementById("messageForm"),
    messageInput: document.getElementById("messageInput"),
    messageSubmitButton: document.getElementById("messageSubmitButton"),
    seedButton: document.getElementById("seedButton"),
    newSessionButton: document.getElementById("newSessionButton"),
    trainingCount: document.getElementById("trainingCount"),
    trainingExamples: document.getElementById("trainingExamples"),
    faqScript: document.getElementById("faqScript"),
    toast: document.getElementById("toast"),
    logoutButton: document.getElementById("logoutButton"),
  });

  document.getElementById("refreshButton").addEventListener("click", loadAll);
  els.newSessionButton.addEventListener("click", () => createSession(false));
  els.seedButton.addEventListener("click", () => createSession(true));
  document.getElementById("copyTrainingButton").addEventListener("click", copyTrainingExamples);
  els.navLinks.forEach((link) => link.addEventListener("click", handleViewNavigation));
  els.logoutButton.addEventListener("click", logoutAdmin);
  els.messageForm.addEventListener("submit", sendMessage);
  els.sessionList.addEventListener("click", handleSessionClick);
  els.sessionFilters.addEventListener("click", handleSessionFilterClick);
  els.supervisionActions.addEventListener("click", handleSupervisionClick);
  els.chatThread.addEventListener("click", handleChatThreadClick);
  els.chatThread.addEventListener("submit", handleChatThreadSubmit);
  els.trainingExamples.addEventListener("click", handleTrainingExampleClick);
  window.addEventListener("hashchange", () => setCurrentView(viewFromHash()));

  setCurrentView(viewFromHash(), { silent: true });
  loadAll();
});

function viewFromHash() {
  const hash = window.location.hash.replace("#", "");
  const aliases = {
    chat: "chat",
    corrections: "corrections",
    koreksi: "corrections",
    training: "corrections",
    knowledge: "knowledge",
    faq: "knowledge",
  };
  return aliases[hash] || "chat";
}

function handleViewNavigation(event) {
  const link = event.currentTarget;
  const view = link.dataset.viewTarget;
  if (!view) return;
  event.preventDefault();
  setCurrentView(view);
  window.history.replaceState(null, "", `#${view}`);
}

function setCurrentView(view, options = {}) {
  const labels = {
    chat: "Latih Chatbot",
    corrections: "Koreksi Jawaban",
    knowledge: "Knowledge Base",
  };
  state.currentView = labels[view] ? view : "chat";
  els.pageTitle.textContent = labels[state.currentView];
  els.navLinks.forEach((link) => {
    link.classList.toggle("active", link.dataset.viewTarget === state.currentView);
  });
  els.viewPanels.forEach((panel) => {
    panel.hidden = panel.dataset.viewPanel !== state.currentView;
  });
  const isChatView = state.currentView === "chat";
  els.seedButton.hidden = !isChatView;
  els.newSessionButton.hidden = !isChatView;
  if (!options.silent) {
    showToast(`Membuka ${labels[state.currentView]}.`);
  }
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    if (response.status === 401) {
      window.location.href = "/client/login?next=/client/chatbot";
      return new Promise(() => {});
    }
    throw new Error(payload.error || "Request gagal.");
  }
  return payload;
}

async function logoutAdmin() {
  try {
    await api("/api/client/logout", { method: "POST", body: JSON.stringify({}) });
  } catch {
    // Tetap arahkan ke login walaupun request logout gagal, agar user tidak tersangkut di UI.
  }
  window.location.href = "/client/login?next=/client/chatbot";
}

async function loadAll() {
  try {
    const [sessionsPayload, faqPayload, trainingPayload] = await Promise.all([
      api("/api/client/chat-simulations"),
      api("/api/client/chat-simulations/faq-script"),
      api("/api/client/chat-simulations/training-examples"),
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
  const title = els.sessionTitleInput.value.trim() || "Latihan jawaban chatbot";
  try {
    const session = await api("/api/client/chat-simulations", {
      method: "POST",
      body: JSON.stringify({ title, seed_from_faq: seedFromFaq }),
    });
    state.activeSession = session;
    showToast(seedFromFaq ? "Contoh awal chatbot dimuat." : "Latihan baru siap.");
    await loadAll();
  } catch (error) {
    showToast(error.message, true);
  }
}

async function openSession(sessionId, options = {}) {
  try {
    state.activeSession = await api(`/api/client/chat-simulations/${sessionId}`);
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
    const result = isManualWhatsappMode(state.activeSession)
      ? await api(`/api/client/chat-simulations/${state.activeSession.id}/manual-reply`, {
          method: "POST",
          body: JSON.stringify({ message }),
        })
      : await api(`/api/client/chat-simulations/${state.activeSession.id}/messages`, {
          method: "POST",
          body: JSON.stringify({ message }),
        });
    els.messageInput.value = "";
    state.activeSession = result.session;
    renderActiveSession();
    await refreshTrainingExamples();
    if (isManualWhatsappMode(state.activeSession)) {
      showToast("Balasan admin terkirim ke WhatsApp.");
    }
  } catch (error) {
    showToast(error.message, true);
  } finally {
    applyComposerMode(state.activeSession);
    els.messageInput.focus();
  }
}

function handleSessionClick(event) {
  const button = event.target.closest("[data-session-id]");
  if (!button) return;
  openSession(Number(button.dataset.sessionId));
}

function handleSessionFilterClick(event) {
  const button = event.target.closest("[data-filter]");
  if (!button) return;
  state.sessionFilter = button.dataset.filter || "all";
  renderSessions();
}

async function handleSupervisionClick(event) {
  const button = event.target.closest("[data-supervision-action]");
  if (!button || !state.activeSession) return;
  const action = button.dataset.supervisionAction;
  try {
    const session = await api(`/api/client/chat-simulations/${state.activeSession.id}/supervision`, {
      method: "PUT",
      body: JSON.stringify({ action }),
    });
    state.activeSession = session;
    renderActiveSession();
    await loadAll();
    showToast(action === "resume_bot" ? "Bot aktif lagi untuk sesi ini." : "Admin mengambil alih percakapan.");
  } catch (error) {
    showToast(error.message, true);
  }
}

function renderSessions() {
  const filteredSessions = filteredSessionList();
  els.sessionCount.textContent = `${filteredSessions.length} dari ${state.sessions.length} sesi`;
  renderSessionFilterButtons();
  if (!filteredSessions.length) {
    els.sessionList.innerHTML = `<div class="empty-state">Belum ada sesi.</div>`;
    return;
  }

  els.sessionList.innerHTML = filteredSessions
    .map((session) => {
      const active = state.activeSession && Number(state.activeSession.id) === Number(session.id);
      const metadata = session.metadata || {};
      const needsAdmin = session.current_stage === "transferred_to_admin";
      return `
        <button class="session-item ${active ? "active" : ""}" type="button" data-session-id="${session.id}">
          <span class="item-title">
            <span>${escapeHtml(session.code)}</span>
            <span class="session-badges">
              <span class="channel-badge ${escapeHtml(session.channel || "provider")}">${escapeHtml(formatChannelShort(session.channel))}</span>
              <span class="status-pill ${needsAdmin || session.current_stage === "needs_review" ? "review" : ""}">
                ${escapeHtml(formatStage(session.current_stage))}
              </span>
            </span>
          </span>
          <span class="item-meta">${escapeHtml(sessionDisplayTitle(session))}</span>
          <span class="item-meta">${Number(session.message_count || 0)} pesan${metadata.sender_number ? ` / ${escapeHtml(metadata.sender_number)}` : ""}</span>
        </button>
      `;
    })
    .join("");
}

function filteredSessionList() {
  return state.sessions.filter((session) => {
    if (state.sessionFilter === "all") return true;
    if (state.sessionFilter === "needs_admin") return session.current_stage === "transferred_to_admin";
    return session.channel === state.sessionFilter;
  });
}

function renderSessionFilterButtons() {
  els.sessionFilters.querySelectorAll("[data-filter]").forEach((button) => {
    button.classList.toggle("active", button.dataset.filter === state.sessionFilter);
  });
}

function renderActiveSession() {
  const session = state.activeSession;
  if (!session) {
    els.activeSessionTitle.textContent = "Belum ada sesi";
    els.activeSessionMeta.textContent = "Buat latihan untuk mulai menguji jawaban chatbot.";
    els.stagePill.textContent = "Mulai";
    els.stagePill.classList.remove("review");
    els.supervisionActions.innerHTML = "";
    els.chatThread.innerHTML = `<div class="empty-state">Belum ada latihan percakapan.</div>`;
    setComposerDisabled(true);
    return;
  }

  els.activeSessionTitle.textContent = `${session.code} - ${sessionDisplayTitle(session)}`;
  els.activeSessionMeta.textContent = activeSessionMetaText(session);
  els.stagePill.textContent = formatStage(session.current_stage);
  els.stagePill.classList.toggle(
    "review",
    session.current_stage === "needs_review" || session.current_stage === "transferred_to_admin"
  );
  renderSupervisionActions(session);
  applyComposerMode(session);

  const messages = session.messages || [];
  if (!messages.length) {
    els.chatThread.innerHTML = `<div class="empty-state">Kirim contoh pertanyaan dari calon orang tua.</div>`;
    return;
  }

  els.chatThread.innerHTML = messages.map(renderMessage).join("");
  els.chatThread.scrollTop = els.chatThread.scrollHeight;
}

function renderSupervisionActions(session) {
  if (!isLiveSession(session)) {
    els.supervisionActions.innerHTML = "";
    return;
  }

  if (session.current_stage === "transferred_to_admin") {
    els.supervisionActions.innerHTML = `
      <button class="secondary compact" type="button" data-supervision-action="resume_bot">Aktifkan bot</button>
    `;
    return;
  }

  els.supervisionActions.innerHTML = `
    <button class="compact" type="button" data-supervision-action="take_over">Ambil alih</button>
  `;
}

function applyComposerMode(session) {
  if (!session) {
    els.messageSubmitButton.textContent = "Kirim";
    setComposerDisabled(true);
    return;
  }

  if (isManualWhatsappMode(session)) {
    els.messageInput.placeholder = "Tulis balasan admin ke WhatsApp...";
    els.messageSubmitButton.textContent = "Balas WA";
    setComposerDisabled(false);
    return;
  }

  if (isLiveSession(session)) {
    els.messageInput.placeholder = "Ambil alih dulu untuk membalas manual.";
    els.messageSubmitButton.textContent = "Bot aktif";
    setComposerDisabled(true);
    return;
  }

  const isTransferredToAdmin = session.current_stage === "transferred_to_admin";
  els.messageInput.placeholder = isTransferredToAdmin
    ? "Chat sudah diteruskan ke admin manusia."
    : "Tulis pesan calon orang tua...";
  els.messageSubmitButton.textContent = "Kirim";
  setComposerDisabled(isTransferredToAdmin);
}

function isLiveSession(session) {
  return ["whatsapp", "instagram"].includes(session?.channel);
}

function isManualWhatsappMode(session) {
  return session?.channel === "whatsapp" && session.current_stage === "transferred_to_admin";
}

function renderMessage(message) {
  const isParent = message.role === "parent";
  const label = messageLabel(message);
  const isEditing = state.editingResponseId === Number(message.id);
  const tags = [
    formatIntent(message.intent),
    formatReference(message.matched_reference),
    message.metadata?.source_channel ? formatChannel(message.metadata.source_channel) : "",
    message.metadata?.sent_by_admin ? "balasan admin" : "",
    message.needs_review ? "perlu cek" : "",
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
          ? `<div class="message-actions"><button class="text-button" type="button" data-action="edit-response" data-message-id="${message.id}">Koreksi jawaban</button></div>`
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
    showToast("Jawaban koreksi tidak boleh kosong.", true);
    return;
  }

  try {
    const result = await api(`/api/client/chat-simulations/${state.activeSession.id}/messages/${messageId}`, {
      method: "PUT",
      body: JSON.stringify({ message }),
    });
    state.editingResponseId = null;
    state.activeSession = result.session;
    renderActiveSession();
    await refreshTrainingExamples();
    showToast("Koreksi jawaban disimpan.");
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
    els.faqScript.innerHTML = `<div class="empty-state">Knowledge base awal belum tersedia.</div>`;
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
    els.trainingExamples.innerHTML = `<div class="empty-state">Belum ada koreksi jawaban.</div>`;
    return;
  }

  els.trainingExamples.innerHTML = state.trainingExamples
    .slice()
    .reverse()
    .map((item) => `
      <article class="example-item">
        <strong>${escapeHtml(item.session_code)} / ${escapeHtml(formatIntent(item.intent) || "Belum terdeteksi")}</strong>
        <div class="qa-grid">
          <section>
            <span class="field-label">Pertanyaan</span>
            <p>${escapeHtml(item.parent_message)}</p>
          </section>
          <section>
            <span class="field-label">Jawaban</span>
            <p>${escapeHtml(item.expected_reply || "")}</p>
          </section>
        </div>
        <div class="message-meta">
          <span class="tag ${item.needs_review ? "review" : ""}">${item.needs_review ? "perlu cek" : "siap"}</span>
          ${item.edited_by_provider ? `<span class="tag">koreksi aktif</span>` : ""}
          <span class="tag">${escapeHtml(formatReference(item.matched_reference) || "Tanpa referensi")}</span>
        </div>
        <div class="example-actions">
          <button class="secondary compact" type="button" data-open-session-id="${item.session_id}">Buka percakapan</button>
        </div>
      </article>
    `)
    .join("");
}

function handleTrainingExampleClick(event) {
  const button = event.target.closest("[data-open-session-id]");
  if (!button) return;
  setCurrentView("chat", { silent: true });
  window.history.replaceState(null, "", "#chat");
  openSession(Number(button.dataset.openSessionId));
}

async function refreshTrainingExamples() {
  const payload = await api("/api/client/chat-simulations/training-examples");
  state.trainingExamples = payload.items || [];
  renderTrainingExamples();
}

async function copyTrainingExamples() {
  const text = JSON.stringify(state.trainingExamples, null, 2);
  try {
    await navigator.clipboard.writeText(text);
    showToast("Dataset koreksi disalin.");
  } catch {
    showToast("Clipboard browser menolak akses.", true);
  }
}

function formatChannel(value) {
  const labels = {
    provider: "Latihan admin",
    whatsapp: "WhatsApp",
    instagram: "Instagram",
  };
  return labels[value] || value || "-";
}

function formatChannelShort(value) {
  const labels = {
    provider: "Latihan",
    whatsapp: "WA",
    instagram: "IG",
  };
  return labels[value] || value || "-";
}

function sessionDisplayTitle(session) {
  const metadata = session?.metadata || {};
  if (session?.channel === "whatsapp") {
    const name = metadata.sender_name ? `${metadata.sender_name} / ` : "";
    return `${name}${session.title}`;
  }
  return session?.title || "-";
}

function activeSessionMetaText(session) {
  const metadata = session?.metadata || {};
  const parts = [formatChannel(session.channel), formatSource(session.source), formatStatus(session.status)];
  if (metadata.sender_number) {
    parts.push(`Nomor ${metadata.sender_number}`);
  }
  if (metadata.sender_id) {
    parts.push(`Sender ${metadata.sender_id}`);
  }
  return parts.filter(Boolean).join(" / ");
}

function messageLabel(message) {
  const channel = message.metadata?.source_channel;
  if (message.role === "parent") {
    if (channel === "whatsapp") return "Orang tua via WA";
    if (channel === "instagram") return "Orang tua via IG";
    return "Calon orang tua";
  }
  if (message.metadata?.sent_by_admin) {
    return "Admin les";
  }
  return "Chatbot";
}

function formatSource(value) {
  const labels = {
    knowledge_base: "Knowledge base",
    fonnte_webhook: "Webhook Fonnte",
    instagram_webhook: "Webhook Instagram",
  };
  return labels[value] || value || "-";
}

function formatStatus(value) {
  const labels = {
    open: "Aktif",
    closed: "Selesai",
  };
  return labels[value] || value || "-";
}

function formatStage(value) {
  const labels = {
    start: "Mulai",
    knowledge_seeded: "Contoh awal",
    greeting: "Sapaan",
    clarify_package: "Butuh detail",
    ask_child_profile: "Profil anak",
    ask_package_selection: "Pilih paket",
    answered_price: "Info biaya",
    answered_package_materials: "Info paket",
    answered_package_recommendation: "Rekomendasi paket",
    answered_coverage: "Area layanan",
    answered_contact_info: "Info kontak",
    close_confirmation_prompt: "Konfirmasi admin",
    continue_qa: "Tanya jawab",
    db_training_override: "Pakai koreksi",
    needs_admin_confirmation: "Perlu admin",
    needs_review: "Perlu cek",
    out_of_scope: "Di luar topik",
    transferred_to_admin: "Admin manusia",
  };
  return labels[value] || formatToken(value);
}

function formatIntent(value) {
  const labels = {
    greeting: "Sapaan",
    package_price: "Harga paket",
    package_recommendation: "Rekomendasi paket",
    list_packages: "Daftar paket",
    coverage_area: "Area layanan",
    close_confirmation_prompt: "Konfirmasi admin",
    admin_handoff_confirmed: "Diteruskan ke admin",
  };
  return labels[value] || formatToken(value);
}

function formatReference(value) {
  if (!value) return "";
  return String(value)
    .replaceAll("db/provider-training:", "Koreksi admin ")
    .replaceAll("knowledge_base:", "Knowledge base ")
    .replaceAll("faq:", "FAQ ")
    .replaceAll("_", " ");
}

function formatToken(value) {
  if (!value) return "";
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
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
