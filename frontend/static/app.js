const state = {
  data: null,
  lastCandidates: [],
};

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
  bindForms();
  bindEditCancelButtons();
  document.addEventListener("click", handleActionClick);
  document.getElementById("refreshButton").addEventListener("click", loadDashboard);
  loadDashboard();
});

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Request gagal.");
  }
  return payload;
}

async function loadDashboard() {
  state.data = await api("/api/dashboard-data");
  renderMetrics();
  renderOptions();
  renderBranches();
  renderParents();
  renderStudents();
  renderTutors();
  renderSchedules();
}

function bindForms() {
  document.getElementById("branchForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await submitResource("branch", event.target, collectBranchForm(event.target));
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
      state.lastCandidates = result.candidates || [];
      renderCandidates(result.message);
    } catch (error) {
      showToast(error.message, true);
    }
  });
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
    showToast(error.message, true);
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

  const form = document.getElementById(config.formId);
  form.dataset.editId = String(id);
  document.getElementById(config.submitId).textContent = config.updateLabel;
  document.getElementById(config.cancelId).hidden = false;

  if (resource === "branch") fillBranchForm(form, item);
  if (resource === "parent") fillParentForm(form, item);
  if (resource === "student") fillStudentForm(form, item);
  if (resource === "tutor") fillTutorForm(form, item);
  if (resource === "schedule") fillScheduleForm(form, item);

  form.scrollIntoView({ behavior: "smooth", block: "center" });
  showToast(`Mode edit aktif untuk ${labelFor(resource)} ${item.code || ""}`.trim());
}

function resetFormMode(form, config) {
  delete form.dataset.editId;
  document.getElementById(config.submitId).textContent = config.createLabel;
  document.getElementById(config.cancelId).hidden = true;
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
    showToast(error.message, true);
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
    showToast(error.message, true);
  }
}

function findItem(collection, id) {
  return (state.data?.[collection] || []).find((item) => Number(item.id) === Number(id));
}

function labelFor(resource) {
  return {
    branch: "cabang",
    parent: "orang tua",
    student: "murid",
    tutor: "guru",
    schedule: "jadwal",
  }[resource] || "data";
}

function collectBranchForm(form) {
  return formToObject(form);
}

function collectParentForm(form) {
  const data = formToObject(form);
  data.branch_id = Number(data.branch_id);
  return data;
}

function collectStudentForm(form) {
  const data = formToObject(form);
  data.branch_id = Number(data.branch_id);
  data.parent_id = Number(data.parent_id);
  data.subject_ids = selectedValues(form.subject_ids).map(Number);
  return data;
}

function collectTutorForm(form) {
  const data = formToObject(form);
  data.branch_id = Number(data.branch_id);
  data.subject_ids = selectedValues(form.subject_ids).map(Number);
  data.availabilities = [
    {
      day_of_week: Number(data.availability_day),
      start_time: data.availability_start,
      end_time: data.availability_end,
    },
  ];
  delete data.availability_day;
  delete data.availability_start;
  delete data.availability_end;
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

  const availability = (item.availabilities || [])[0];
  if (availability) {
    setValue(form, "availability_day", availability.day_of_week);
    setValue(form, "availability_start", availability.start_time);
    setValue(form, "availability_end", availability.end_time);
  }
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

function renderMetrics() {
  const summary = state.data.summary;
  document.getElementById("metricParents").textContent = summary.parents;
  document.getElementById("metricStudents").textContent = summary.students;
  document.getElementById("metricTutors").textContent = summary.tutors;
  document.getElementById("metricSchedules").textContent = summary.schedules;
  document.getElementById("metricBranches").textContent = summary.branches;
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

function renderParents() {
  const list = document.getElementById("parentList");
  list.innerHTML = state.data.parents.length
    ? state.data.parents.map((parent) => `
      <article class="data-card">
        <header>
          <div>
            <strong>${escapeHtml(parent.code)} • ${escapeHtml(parent.full_name)}</strong>
            <p>${escapeHtml(parent.phone)}${parent.email ? ` • ${escapeHtml(parent.email)}` : ""}</p>
            <p>Cabang: ${escapeHtml(parent.branch_name)} • ${escapeHtml(parent.branch_city)}</p>
            <p>${escapeHtml(parent.address || "Alamat belum diisi")}</p>
          </div>
          <span class="status">${parent.student_count} anak</span>
        </header>
        <div class="card-actions">
          <button class="mini-btn" data-action="edit-parent" data-id="${parent.id}">Edit</button>
          <button class="mini-btn danger" data-action="archive-parent" data-id="${parent.id}">Arsipkan</button>
        </div>
      </article>
    `).join("")
    : `<div class="empty-state">Belum ada data orang tua.</div>`;
}

function renderStudents() {
  const list = document.getElementById("studentList");
  list.innerHTML = state.data.students.length
    ? state.data.students.map((student) => `
      <article class="data-card">
        <header>
          <div>
            <strong>${escapeHtml(student.code)} • ${escapeHtml(student.full_name)}</strong>
            <p>Orang tua: ${escapeHtml(student.parent_name)}</p>
            <p>Cabang: ${escapeHtml(student.branch_name)} • ${escapeHtml(student.branch_city)}</p>
            <p>Mapel: ${escapeHtml(student.subjects || "Belum dipilih")}</p>
          </div>
          <span class="status">${escapeHtml(student.status)}</span>
        </header>
        <div class="card-actions">
          <button class="mini-btn" data-action="edit-student" data-id="${student.id}">Edit</button>
          <button class="mini-btn danger" data-action="archive-student" data-id="${student.id}">Arsipkan</button>
        </div>
      </article>
    `).join("")
    : `<div class="empty-state">Belum ada data murid.</div>`;
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
  list.innerHTML = state.data.schedules.length
    ? state.data.schedules.map((schedule) => `
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
    : `<div class="empty-state">Belum ada jadwal aktif.</div>`;
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

async function confirmCandidate(index) {
  const candidate = state.lastCandidates[index];
  if (!candidate) return;
  try {
    await api("/api/schedules/confirm", {
      method: "POST",
      body: JSON.stringify({ slots: candidate.slots }),
    });
    showToast("Jadwal kandidat berhasil dikonfirmasi.");
    state.lastCandidates = [];
    renderCandidates("Jadwal sudah disimpan.");
    await loadDashboard();
  } catch (error) {
    showToast(error.message, true);
  }
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
