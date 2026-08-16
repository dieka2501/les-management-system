const state = {
  data: null,
  lastCandidates: [],
  activeView: "beranda",
};

const pageConfig = {
  beranda: {
    eyebrow: "Report Operasional",
    title: "Dashboard Operasional Les",
    description: "Ringkasan kondisi data les, kesiapan operasional, dan jadwal aktif.",
  },
  cabang: {
    eyebrow: "Data Master",
    title: "Cabang",
    description: "Kelola cabang sebagai area kerja untuk orang tua, murid, guru, dan jadwal.",
  },
  "mata-pelajaran": {
    eyebrow: "Data Master",
    title: "Mata Pelajaran",
    description: "Kelola mata pelajaran yang dipilih murid, guru, jadwal, dan generator jadwal.",
  },
  "orang-tua-murid": {
    eyebrow: "Data Keluarga",
    title: "Orang Tua & Murid",
    description: "Kelola satu orang tua dengan beberapa anak/murid dalam satu halaman.",
  },
  guru: {
    eyebrow: "Data Pengajar",
    title: "Guru",
    description: "Kelola guru, mata pelajaran yang diajar, dan jam tersedia untuk penjadwalan.",
  },
  jadwal: {
    eyebrow: "Operasional Belajar",
    title: "Jadwal",
    description: "Buat manual, generate otomatis, edit, dan batalkan jadwal dari satu menu.",
  },
};

const viewAliases = {
  "orang-tua": "orang-tua-murid",
  murid: "orang-tua-murid",
  generator: "jadwal",
};

const dayOptions = [
  { value: 0, label: "Senin" },
  { value: 1, label: "Selasa" },
  { value: 2, label: "Rabu" },
  { value: 3, label: "Kamis" },
  { value: 4, label: "Jumat" },
  { value: 5, label: "Sabtu" },
  { value: 6, label: "Minggu" },
];

const resourceConfig = {
  branch: {
    path: "/api/branches",
    collection: "branches",
    formId: "branchForm",
    submitId: "branchSubmitButton",
    cancelId: "branchCancelEdit",
    createLabel: "Simpan cabang",
    updateLabel: "Update cabang",
  },
  subject: {
    path: "/api/subjects",
    collection: "subjects",
    formId: "subjectForm",
    submitId: "subjectSubmitButton",
    cancelId: "subjectCancelEdit",
    createLabel: "Simpan mata pelajaran",
    updateLabel: "Update mata pelajaran",
  },
  parent: {
    path: "/api/parents",
    collection: "parents",
    formId: "parentForm",
    submitId: "parentSubmitButton",
    cancelId: "parentCancelEdit",
    createLabel: "Simpan orang tua",
    updateLabel: "Update orang tua",
  },
  student: {
    path: "/api/students",
    collection: "students",
    formId: "studentForm",
    submitId: "studentSubmitButton",
    cancelId: "studentCancelEdit",
    createLabel: "Simpan murid",
    updateLabel: "Update murid",
  },
  tutor: {
    path: "/api/tutors",
    collection: "tutors",
    formId: "tutorForm",
    submitId: "tutorSubmitButton",
    cancelId: "tutorCancelEdit",
    createLabel: "Simpan guru",
    updateLabel: "Update guru",
  },
  schedule: {
    path: "/api/schedules",
    collection: "schedules",
    formId: "scheduleForm",
    submitId: "scheduleSubmitButton",
    cancelId: "scheduleCancelEdit",
    createLabel: "Simpan jadwal",
    updateLabel: "Update jadwal",
  },
};

document.addEventListener("DOMContentLoaded", () => {
  bindNavigation();
  bindForms();
  bindEditCancelButtons();
  bindTutorAvailabilityEditor();
  document.addEventListener("click", handleActionClick);
  document.getElementById("refreshButton").addEventListener("click", loadDashboard);
  document.getElementById("dashboardLogoutButton").addEventListener("click", logoutDashboard);
  showView(viewFromHash(), { replace: true, scroll: false });
  loadDashboard();
});

function bindNavigation() {
  document.addEventListener("click", (event) => {
    const link = event.target.closest("[data-view-link]");
    if (!link) return;

    const view = normalizeView(link.dataset.viewLink);
    if (!pageConfig[view]) return;

    event.preventDefault();
    showView(view);
  });

  window.addEventListener("popstate", () => {
    showView(viewFromHash(), { updateHistory: false });
  });
}

function viewFromHash() {
  const view = window.location.hash.replace("#", "");
  return normalizeView(view);
}

function showView(view, options = {}) {
  const nextView = normalizeView(view);
  const config = pageConfig[nextView];
  state.activeView = nextView;

  document.querySelectorAll(".section").forEach((section) => {
    section.classList.toggle("active-section", section.id === nextView);
  });

  document.querySelectorAll(".nav [data-view-link]").forEach((link) => {
    const active = link.dataset.viewLink === nextView;
    link.classList.toggle("active", active);
    if (active) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });

  document.getElementById("pageEyebrow").textContent = config.eyebrow;
  document.getElementById("pageTitle").textContent = config.title;
  document.getElementById("pageDescription").textContent = config.description;
  document.title = `${config.title} - Les Belajar`;

  if (options.updateHistory !== false) {
    const nextUrl = `${window.location.pathname}${window.location.search}#${nextView}`;
    const method = options.replace ? "replaceState" : "pushState";
    if (window.location.hash !== `#${nextView}` || options.replace) {
      window.history[method]({}, "", nextUrl);
    }
  }

  if (options.scroll !== false) {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

function normalizeView(view) {
  const normalized = viewAliases[view] || view;
  return pageConfig[normalized] ? normalized : "beranda";
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  let payload = {};
  try {
    payload = await response.json();
  } catch (error) {
    payload = {};
  }
  if (response.status === 401) {
    const next = encodeURIComponent(window.location.pathname + window.location.hash);
    window.location.href = `/client/login?next=${next}`;
    throw new Error("Sesi login berakhir. Silakan login ulang.");
  }
  if (!response.ok) {
    throw new Error(payload.message || payload.error || `Request gagal dengan status ${response.status}.`);
  }
  return payload;
}

async function logoutDashboard() {
  try {
    await api("/api/client/logout", { method: "POST", body: JSON.stringify({}) });
  } finally {
    window.location.href = "/client/login?next=/";
  }
}

async function loadDashboard() {
  state.data = await api("/api/dashboard-data");
  renderMetrics();
  renderReadiness();
  renderOptions();
  renderBranches();
  renderSubjects();
  renderFamilies();
  renderTutors();
  renderSchedules();
}

function bindForms() {
  document.getElementById("branchForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitResource("branch", event.target, collectBranchForm(event.target));
  });

  document.getElementById("subjectForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitResource("subject", event.target, collectSubjectForm(event.target));
  });

  document.getElementById("parentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitResource("parent", event.target, collectParentForm(event.target));
  });

  document.getElementById("studentForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitResource("student", event.target, collectStudentForm(event.target));
  });

  document.getElementById("tutorForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitResource("tutor", event.target, collectTutorForm(event.target));
  });

  document.getElementById("scheduleForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitResource("schedule", event.target, collectScheduleForm(event.target));
  });

  document.getElementById("generatorForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.target;
    const data = formToObject(form);
    data.branch_id = Number(data.branch_id);
    data.student_id = Number(data.student_id);
    data.subject_id = Number(data.subject_id);
    data.sessions_per_week = Number(data.sessions_per_week);
    data.duration_minutes = Number(data.duration_minutes);
    data.preferred_days = selectedValues(form.preferred_days).map(Number);
    try {
      const result = await api("/api/schedules/generate", {
        method: "POST",
        body: JSON.stringify(data),
      });
      const candidates = result.candidates || [];
      state.lastCandidates = candidates;
      if (!candidates.length) {
        renderCandidates(result.message);
        showToast(`Generate jadwal belum menemukan slot. ${result.message}`, true);
        return;
      }

      const saved = await saveGeneratedCandidate(candidates[0]);
      state.lastCandidates = [];
      renderGeneratedResult(saved.saved || [], candidates.length);
      showToast("Jadwal berhasil digenerate dan masuk ke menu Jadwal.");
      await loadDashboard();
      showView("jadwal");
    } catch (error) {
      showErrorToast(error, "Gagal generate jadwal.");
    }
  });
}

function bindTutorAvailabilityEditor() {
  const rows = document.getElementById("availabilityRows");
  document.getElementById("addAvailabilityButton").addEventListener("click", () => {
    addTutorAvailabilityRow();
  });
  rows.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action='remove-availability']");
    if (!button) return;
    button.closest(".availability-row")?.remove();
    updateAvailabilityRemoveButtons();
  });
  resetTutorAvailabilityRows();
}

function bindEditCancelButtons() {
  Object.values(resourceConfig).forEach((config) => {
    document.getElementById(config.cancelId)?.addEventListener("click", () => {
      const form = document.getElementById(config.formId);
      form.reset();
      resetFormMode(form, config);
    });
  });
}

async function submitResource(resource, form, data) {
  const config = resourceConfig[resource];
  const editId = form.dataset.editId;
  const path = editId ? `${config.path}/${editId}` : config.path;
  const method = editId ? "PUT" : "POST";

  try {
    await api(path, { method, body: JSON.stringify(data) });
    form.reset();
    resetFormMode(form, config);
    showToast(editId ? "Data berhasil diupdate." : "Data berhasil disimpan.");
    await loadDashboard();
  } catch (error) {
    const action = editId ? "mengupdate" : "menyimpan";
    showErrorToast(error, `Gagal ${action} ${labelFor(resource)}.`);
  }
}

async function handleActionClick(event) {
  const button = event.target.closest("[data-action]");
  if (!button) return;

  const [action, resource] = button.dataset.action.split("-");
  const id = Number(button.dataset.id);

  if (action === "edit") {
    startEdit(resource, id);
    return;
  }

  if (action === "archive") {
    await archiveResource(resource, id);
    return;
  }

  if (action === "cancel") {
    await cancelSchedule(id);
    return;
  }

  if (action === "confirm") {
    await confirmCandidate(Number(button.dataset.index));
  }
}

function startEdit(resource, id) {
  const config = resourceConfig[resource];
  const item = findItem(config.collection, id);
  if (!item) {
    showToast("Data tidak ditemukan. Coba refresh halaman.", true);
    return;
  }

  showView(viewForResource(resource), { scroll: false });

  const form = document.getElementById(config.formId);
  form.dataset.editId = String(id);
  document.getElementById(config.submitId).textContent = config.updateLabel;
  document.getElementById(config.cancelId).hidden = false;

  if (resource === "branch") fillBranchForm(form, item);
  if (resource === "subject") fillSubjectForm(form, item);
  if (resource === "parent") fillParentForm(form, item);
  if (resource === "student") fillStudentForm(form, item);
  if (resource === "tutor") fillTutorForm(form, item);
  if (resource === "schedule") fillScheduleForm(form, item);

  form.scrollIntoView({ behavior: "smooth", block: "center" });
  showToast(`Mode edit aktif untuk ${labelFor(resource)} ${item.code || ""}`.trim());
}

function viewForResource(resource) {
  return {
    branch: "cabang",
    subject: "mata-pelajaran",
    parent: "orang-tua-murid",
    student: "orang-tua-murid",
    tutor: "guru",
    schedule: "jadwal",
  }[resource] || "beranda";
}

function resetFormMode(form, config) {
  delete form.dataset.editId;
  document.getElementById(config.submitId).textContent = config.createLabel;
  document.getElementById(config.cancelId).hidden = true;
  if (form.id === "tutorForm") {
    resetTutorAvailabilityRows();
  }
}

async function archiveResource(resource, id) {
  const config = resourceConfig[resource];
  const item = findItem(config.collection, id);
  const label = item?.full_name || item?.name || item?.code || "data ini";
  if (!confirm(`Arsipkan ${label}?`)) return;
  try {
    await api(`${config.path}/${id}`, { method: "DELETE" });
    showToast("Data berhasil diarsipkan.");
    await loadDashboard();
  } catch (error) {
    showErrorToast(error, `Gagal mengarsipkan ${labelFor(resource)}.`);
  }
}

async function cancelSchedule(id) {
  const item = findItem("schedules", id);
  const label = item?.code || "jadwal ini";
  if (!confirm(`Batalkan ${label}?`)) return;
  try {
    await api(`/api/schedules/${id}`, { method: "DELETE" });
    showToast("Jadwal berhasil dibatalkan.");
    await loadDashboard();
  } catch (error) {
    showErrorToast(error, "Gagal membatalkan jadwal.");
  }
}

function findItem(collection, id) {
  return (state.data?.[collection] || []).find((item) => Number(item.id) === Number(id));
}

function labelFor(resource) {
  return {
    branch: "cabang",
    subject: "mata pelajaran",
    parent: "orang tua",
    student: "murid",
    tutor: "guru",
    schedule: "jadwal",
  }[resource] || "data";
}

function collectBranchForm(form) {
  return formToObject(form);
}

function collectSubjectForm(form) {
  return formToObject(form);
}

function collectParentForm(form) {
  const data = formToObject(form);
  data.branch_id = Number(data.branch_id);
  return data;
}

function collectStudentForm(form) {
  const data = formToObject(form);
  if (data.branch_id) {
    data.branch_id = Number(data.branch_id);
  } else {
    delete data.branch_id;
  }
  data.parent_id = Number(data.parent_id);
  data.subject_ids = selectedValues(form.subject_ids).map(Number);
  return data;
}

function collectTutorForm(form) {
  const data = formToObject(form);
  data.branch_id = Number(data.branch_id);
  data.subject_ids = selectedValues(form.subject_ids).map(Number);
  data.availabilities = collectTutorAvailabilities();
  return data;
}

function collectScheduleForm(form) {
  const data = formToObject(form);
  ["branch_id", "student_id", "tutor_id", "subject_id", "day_of_week"].forEach((key) => {
    data[key] = Number(data[key]);
  });
  return data;
}

function fillBranchForm(form, item) {
  setValue(form, "name", item.name);
  setValue(form, "city", item.city);
  setValue(form, "address", item.address);
}

function fillSubjectForm(form, item) {
  setValue(form, "name", item.name);
  setValue(form, "description", item.description);
}

function fillParentForm(form, item) {
  setValue(form, "branch_id", item.branch_id);
  setValue(form, "full_name", item.full_name);
  setValue(form, "phone", item.phone);
  setValue(form, "email", item.email);
  setValue(form, "address", item.address);
}

function fillStudentForm(form, item) {
  setValue(form, "branch_id", item.branch_id);
  setValue(form, "parent_id", item.parent_id);
  setValue(form, "full_name", item.full_name);
  setValue(form, "birthplace", item.birthplace);
  setValue(form, "birthdate", item.birthdate);
  setValue(form, "gender", item.gender);
  setMultipleValues(form.subject_ids, item.subject_ids || []);
  setValue(form, "notes", item.notes);
}

function fillTutorForm(form, item) {
  setValue(form, "branch_id", item.branch_id);
  setValue(form, "full_name", item.full_name);
  setValue(form, "education", item.education);
  setValue(form, "birthdate", item.birthdate);
  setValue(form, "gender", item.gender);
  setMultipleValues(form.subject_ids, item.subject_ids || []);
  setValue(form, "notes", item.notes);
  setTutorAvailabilityRows(item.availabilities || []);
}

function fillScheduleForm(form, item) {
  setValue(form, "branch_id", item.branch_id);
  setValue(form, "student_id", item.student_id);
  setValue(form, "tutor_id", item.tutor_id);
  setValue(form, "subject_id", item.subject_id);
  setValue(form, "day_of_week", item.day_of_week);
  setValue(form, "start_time", item.start_time);
  setValue(form, "end_time", item.end_time);
  setValue(form, "mode", item.mode);
  setValue(form, "location", item.location);
}

function setValue(form, name, value) {
  if (form.elements[name]) {
    form.elements[name].value = value ?? "";
  }
}

function setMultipleValues(select, values) {
  const selected = new Set((values || []).map(String));
  Array.from(select.options).forEach((option) => {
    option.selected = selected.has(option.value);
  });
}

function formToObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function selectedValues(select) {
  return Array.from(select.selectedOptions).map((option) => option.value);
}

function collectTutorAvailabilities() {
  return Array.from(document.querySelectorAll("#availabilityRows .availability-row")).map((row) => ({
    day_of_week: Number(row.querySelector("[data-availability-day]").value),
    start_time: row.querySelector("[data-availability-start]").value,
    end_time: row.querySelector("[data-availability-end]").value,
  }));
}

function resetTutorAvailabilityRows() {
  setTutorAvailabilityRows([{ day_of_week: 0, start_time: "15:00", end_time: "19:00" }]);
}

function setTutorAvailabilityRows(availabilities) {
  const rows = document.getElementById("availabilityRows");
  rows.innerHTML = "";
  const items = availabilities.length
    ? availabilities
    : [{ day_of_week: 0, start_time: "15:00", end_time: "19:00" }];
  items.forEach((availability) => addTutorAvailabilityRow(availability));
  updateAvailabilityRemoveButtons();
}

function addTutorAvailabilityRow(availability = {}) {
  const rows = document.getElementById("availabilityRows");
  const row = document.createElement("div");
  row.className = "availability-row";
  const selectedDay = Number(availability.day_of_week ?? 0);
  const daySelectHtml = dayOptions
    .map((day) => `<option value="${day.value}" ${day.value === selectedDay ? "selected" : ""}>${day.label}</option>`)
    .join("");
  row.innerHTML = `
    <label>
      Hari
      <select data-availability-day required>${daySelectHtml}</select>
    </label>
    <label>
      Mulai
      <input data-availability-start type="time" value="${escapeHtml(availability.start_time || "15:00")}" required />
    </label>
    <label>
      Selesai
      <input data-availability-end type="time" value="${escapeHtml(availability.end_time || "19:00")}" required />
    </label>
    <button class="mini-btn danger" type="button" data-action="remove-availability">Hapus</button>
  `;
  rows.append(row);
  updateAvailabilityRemoveButtons();
}

function updateAvailabilityRemoveButtons() {
  const buttons = document.querySelectorAll("#availabilityRows [data-action='remove-availability']");
  buttons.forEach((button) => {
    button.disabled = buttons.length <= 1;
  });
}

function renderMetrics() {
  const summary = state.data.summary;
  document.getElementById("metricParents").textContent = summary.parents;
  document.getElementById("metricStudents").textContent = summary.students;
  document.getElementById("metricTutors").textContent = summary.tutors;
  document.getElementById("metricSubjects").textContent = summary.subjects;
  document.getElementById("metricSchedules").textContent = summary.schedules;
  document.getElementById("metricBranches").textContent = summary.branches;
}

function renderReadiness() {
  const summary = state.data.summary;
  const items = [
    { label: "Cabang", count: summary.branches, view: "cabang", empty: "Buat minimal 1 cabang." },
    { label: "Mata pelajaran", count: summary.subjects, view: "mata-pelajaran", empty: "Tambahkan mata pelajaran." },
    { label: "Orang tua", count: summary.parents, view: "orang-tua-murid", empty: "Catat kontak orang tua." },
    { label: "Murid", count: summary.students, view: "orang-tua-murid", empty: "Tambahkan murid aktif." },
    { label: "Guru", count: summary.tutors, view: "guru", empty: "Lengkapi data guru." },
    { label: "Jadwal", count: summary.schedules, view: "jadwal", empty: "Buat jadwal belajar." },
  ];

  const list = document.getElementById("readinessList");
  list.innerHTML = items
    .map((item) => {
      const ready = Number(item.count) > 0;
      return `
        <article class="readiness-item">
          <div>
            <strong>${escapeHtml(item.label)}</strong>
            <span>${ready ? `${Number(item.count)} data aktif` : item.empty}</span>
          </div>
          <a class="mini-btn ${ready ? "" : "danger"}" href="#${item.view}" data-view-link="${item.view}">
            ${ready ? "Buka" : "Lengkapi"}
          </a>
        </article>
      `;
    })
    .join("");
}

function renderOptions() {
  const branchOptions = state.data.branches
    .map((branch) => `<option value="${branch.id}">${escapeHtml(branch.name)} • ${escapeHtml(branch.city)}</option>`)
    .join("");
  const parentOptions = state.data.parents
    .map((parent) => `<option value="${parent.id}">${escapeHtml(parent.full_name)} • ${escapeHtml(parent.branch_city)}</option>`)
    .join("");
  const subjectOptions = state.data.subjects
    .map((subject) => `<option value="${subject.id}">${escapeHtml(subject.name)}</option>`)
    .join("");
  const studentOptions = state.data.students
    .map((student) => `<option value="${student.id}">${escapeHtml(student.full_name)} • ${escapeHtml(student.branch_city)}</option>`)
    .join("");
  const tutorOptions = state.data.tutors
    .map((tutor) => `<option value="${tutor.id}">${escapeHtml(tutor.full_name)} • ${escapeHtml(tutor.branch_city)}</option>`)
    .join("");

  setOptions("parentBranchSelect", branchOptions);
  setOptions("studentBranchSelect", branchOptions);
  setOptions("tutorBranchSelect", branchOptions);
  setOptions("scheduleBranchSelect", branchOptions);
  setOptions("generatorBranchSelect", branchOptions);
  setOptions("studentParentSelect", parentOptions);
  setOptions("studentSubjectSelect", subjectOptions);
  setOptions("tutorSubjectSelect", subjectOptions);
  setOptions("scheduleStudentSelect", studentOptions);
  setOptions("scheduleTutorSelect", tutorOptions);
  setOptions("scheduleSubjectSelect", subjectOptions);
  setOptions("generatorStudentSelect", studentOptions);
  setOptions("generatorSubjectSelect", subjectOptions);
}

function setOptions(id, html) {
  const element = document.getElementById(id);
  if (element) {
    element.innerHTML = html || "<option value=\"\">Belum ada data</option>";
  }
}

function renderBranches() {
  const list = document.getElementById("branchList");
  list.innerHTML = state.data.branches.length
    ? state.data.branches.map((branch) => `
      <article class="data-card">
        <header>
          <div>
            <strong>${escapeHtml(branch.code)} • ${escapeHtml(branch.name)}</strong>
            <p>${escapeHtml(branch.address)}</p>
            <p>${escapeHtml(branch.city)}</p>
          </div>
          <span class="status">${escapeHtml(branch.status)}</span>
        </header>
        <div class="card-actions">
          <button class="mini-btn" data-action="edit-branch" data-id="${branch.id}">Edit</button>
          <button class="mini-btn danger" data-action="archive-branch" data-id="${branch.id}">Arsipkan</button>
        </div>
      </article>
    `).join("")
    : `<div class="empty-state">Belum ada data cabang.</div>`;
}

function renderSubjects() {
  const list = document.getElementById("subjectList");
  list.innerHTML = state.data.subjects.length
    ? state.data.subjects.map((subject) => `
      <article class="data-card">
        <header>
          <div>
            <strong>${escapeHtml(subject.code)} • ${escapeHtml(subject.name)}</strong>
            <p>${escapeHtml(subject.description || "Deskripsi belum diisi")}</p>
          </div>
          <span class="status">${escapeHtml(subject.status)}</span>
        </header>
        <div class="card-actions">
          <button class="mini-btn" data-action="edit-subject" data-id="${subject.id}">Edit</button>
          <button class="mini-btn danger" data-action="archive-subject" data-id="${subject.id}">Arsipkan</button>
        </div>
      </article>
    `).join("")
    : `<div class="empty-state">Belum ada data mata pelajaran.</div>`;
}

function renderFamilies() {
  const list = document.getElementById("familyList");
  const parents = state.data.parents || [];
  const students = state.data.students || [];

  if (!parents.length) {
    list.innerHTML = `<div class="empty-state">Belum ada data keluarga. Tambahkan orang tua dulu, lalu masukkan data murid.</div>`;
    return;
  }

  list.innerHTML = parents.map((parent) => {
    const children = students.filter((student) => Number(student.parent_id) === Number(parent.id));
    return `
      <article class="data-card family-card">
        <header>
          <div>
            <strong>${escapeHtml(parent.code)} • ${escapeHtml(parent.full_name)}</strong>
            <p>${escapeHtml(parent.phone)}${parent.email ? ` • ${escapeHtml(parent.email)}` : ""}</p>
            <p>Cabang: ${escapeHtml(parent.branch_name)} • ${escapeHtml(parent.branch_city)}</p>
            <p>${escapeHtml(parent.address || "Alamat belum diisi")}</p>
          </div>
          <span class="status">${children.length} anak</span>
        </header>
        <div class="card-actions">
          <button class="mini-btn" data-action="edit-parent" data-id="${parent.id}">Edit orang tua</button>
          <button class="mini-btn danger" data-action="archive-parent" data-id="${parent.id}">Arsipkan</button>
        </div>
        <div class="child-list">
          <div class="child-list-head">
            <strong>Anak/murid</strong>
            <span>${children.length ? `${children.length} data murid aktif` : "Belum ada murid"}</span>
          </div>
          ${
            children.length
              ? children.map(renderFamilyStudent).join("")
              : `<div class="empty-state compact">Belum ada murid untuk orang tua ini.</div>`
          }
        </div>
      </article>
    `;
  }).join("");
}

function renderFamilyStudent(student) {
  return `
    <article class="child-item">
      <div>
        <strong>${escapeHtml(student.code)} • ${escapeHtml(student.full_name)}</strong>
        <p>Mapel: ${escapeHtml(student.subjects || "Belum dipilih")}</p>
        <p>Cabang: ${escapeHtml(student.branch_name)} • ${escapeHtml(student.branch_city)}</p>
      </div>
      <div class="card-actions child-actions">
        <button class="mini-btn" data-action="edit-student" data-id="${student.id}">Edit murid</button>
        <button class="mini-btn danger" data-action="archive-student" data-id="${student.id}">Arsipkan</button>
      </div>
    </article>
  `;
}

function renderTutors() {
  const list = document.getElementById("tutorList");
  list.innerHTML = state.data.tutors.length
    ? state.data.tutors.map((tutor) => `
      <article class="data-card">
        <header>
          <div>
            <strong>${escapeHtml(tutor.code)} • ${escapeHtml(tutor.full_name)}</strong>
            <p>Cabang: ${escapeHtml(tutor.branch_name)} • ${escapeHtml(tutor.branch_city)}</p>
            <p>${escapeHtml(tutor.education || "Pendidikan belum diisi")}</p>
            <p>Mapel: ${escapeHtml(tutor.subjects || "Belum dipilih")}</p>
          </div>
          <span class="status">${escapeHtml(tutor.status)}</span>
        </header>
        <div class="chips">
          ${(tutor.availabilities || []).map((availability) => `
            <span class="chip">${availability.day_name}, ${availability.start_time}-${availability.end_time}</span>
          `).join("")}
        </div>
        <div class="card-actions">
          <button class="mini-btn" data-action="edit-tutor" data-id="${tutor.id}">Edit</button>
          <button class="mini-btn danger" data-action="archive-tutor" data-id="${tutor.id}">Arsipkan</button>
        </div>
      </article>
    `).join("")
    : `<div class="empty-state">Belum ada data guru.</div>`;
}

function renderSchedules() {
  const list = document.getElementById("scheduleList");
  const reportList = document.getElementById("reportScheduleList");
  list.innerHTML = scheduleCardsHtml(state.data.schedules, "Belum ada jadwal aktif.");
  reportList.innerHTML = scheduleCardsHtml(state.data.schedules.slice(0, 5), "Belum ada jadwal aktif.");
}

function scheduleCardsHtml(schedules, emptyMessage) {
  return schedules.length
    ? schedules.map((schedule) => `
      <article class="data-card">
        <header>
          <div>
            <strong>${escapeHtml(schedule.day_name)}, ${schedule.start_time}-${schedule.end_time}</strong>
            <p>${escapeHtml(schedule.subject_name)} • ${escapeHtml(schedule.student_name)} dengan ${escapeHtml(schedule.tutor_name)}</p>
            <p>Cabang: ${escapeHtml(schedule.branch_name)} • ${escapeHtml(schedule.branch_city)}</p>
            <p>Mode: ${escapeHtml(schedule.mode)}${schedule.location ? ` • ${escapeHtml(schedule.location)}` : ""}</p>
          </div>
          <span class="status">${escapeHtml(schedule.code)}</span>
        </header>
        <div class="card-actions">
          <button class="mini-btn" data-action="edit-schedule" data-id="${schedule.id}">Edit</button>
          <button class="mini-btn danger" data-action="cancel-schedule" data-id="${schedule.id}">Batalkan</button>
        </div>
      </article>
    `).join("")
    : `<div class="empty-state">${escapeHtml(emptyMessage)}</div>`;
}

function renderCandidates(message = "") {
  const list = document.getElementById("candidateList");
  if (!state.lastCandidates.length) {
    list.innerHTML = `<div class="empty-state">${escapeHtml(message || "Tidak ada kandidat.")}</div>`;
    return;
  }
  list.innerHTML = state.lastCandidates.map((candidate, index) => `
    <article class="data-card">
      <header>
        <div>
          <strong>${escapeHtml(candidate.tutor_name)} • ${escapeHtml(candidate.subject_name)}</strong>
          <p>Cabang: ${escapeHtml(candidate.branch_name)} • ${escapeHtml(candidate.branch_city)}</p>
          <p>${escapeHtml(candidate.reason)}</p>
        </div>
        <span class="status">Aman</span>
      </header>
      <div class="chips">
        ${candidate.slots.map((slot) => `
          <span class="chip">${escapeHtml(slot.day_name)}, ${slot.start_time}-${slot.end_time}</span>
        `).join("")}
      </div>
      <button class="btn secondary" style="margin-top:12px" data-action="confirm-candidate" data-index="${index}">
        Konfirmasi jadwal ini
      </button>
    </article>
  `).join("");
}

function renderGeneratedResult(savedSchedules, candidateCount) {
  const list = document.getElementById("candidateList");
  if (!savedSchedules.length) {
    list.innerHTML = `<div class="empty-state">Generate selesai, tapi jadwal belum tersimpan.</div>`;
    return;
  }

  list.innerHTML = `
    <article class="data-card">
      <header>
        <div>
          <strong>${savedSchedules.length} jadwal tersimpan</strong>
          <p>Dipilih dari ${candidateCount} kandidat aman dan sudah masuk ke menu Jadwal.</p>
        </div>
        <span class="status">Tersimpan</span>
      </header>
      <div class="chips">
        ${savedSchedules.map((schedule) => `
          <span class="chip">${escapeHtml(schedule.day_name)}, ${schedule.start_time}-${schedule.end_time}</span>
        `).join("")}
      </div>
    </article>
  `;
}

function saveGeneratedCandidate(candidate) {
  return api("/api/schedules/confirm", {
    method: "POST",
    body: JSON.stringify({ slots: candidate.slots }),
  });
}

async function confirmCandidate(index) {
  const candidate = state.lastCandidates[index];
  if (!candidate) return;
  try {
    await saveGeneratedCandidate(candidate);
    showToast("Jadwal kandidat berhasil dikonfirmasi.");
    state.lastCandidates = [];
    renderCandidates("Jadwal sudah disimpan.");
    await loadDashboard();
    showView("jadwal");
  } catch (error) {
    showErrorToast(error, "Gagal mengonfirmasi jadwal.");
  }
}

function showErrorToast(error, context) {
  const detail = error?.message || "Terjadi kendala yang belum diketahui.";
  const message = detail.startsWith(context) ? detail : `${context} ${detail}`;
  showToast(message, true);
}

function showToast(message, isError = false) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.hidden = false;
  setTimeout(() => {
    toast.hidden = true;
  }, 4500);
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
