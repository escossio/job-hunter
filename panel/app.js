const STATUS_OPTIONS = [
  "não avaliada",
  "revisar",
  "candidatura enviada",
  "não enviar",
  "aguardando retorno",
  "entrevista",
  "recusada",
];

const CLASS_ORDER = { Alta: 0, Média: 1, Baixa: 2, Ignorar: 3 };
const QUICK_FILTERS = {
  total: null,
  newToday: { newToday: true },
  newLastRun: { newLastRun: true },
  high: { classification: "Alta" },
  medium: { classification: "Média" },
  sent: { status: "candidatura enviada" },
  review: { status: "revisar" },
  block: { status: "não enviar" },
};
const STORAGE_KEYS = {
  filtersOpen: "job-hunter.filters-open",
  quickFilter: "job-hunter.quick-filter",
};

const state = {
  jobs: [],
  summary: null,
  selectedJobKey: null,
  refreshInFlight: null,
  quickFilterKey: "total",
  filtersOpen: false,
  detail: {
    initialStatus: "",
    initialObservacoes: "",
    dirty: false,
    suppressDirtyCheck: false,
  },
  filters: {
    text: "",
    origin: "",
    classification: "",
    status: "",
    modality: "",
    onlyHigh: false,
    onlyUnreviewed: false,
    onlySent: false,
    onlyReview: false,
    hideIgnore: false,
    sortBy: "priority_rank",
  },
};

let toastTimer = null;
let confirmResolve = null;

function byId(id) {
  return document.getElementById(id);
}

function jobByKey(jobKey) {
  return state.jobs.find((job) => job.job_key === jobKey) || null;
}

function formatValue(value) {
  return value == null || value === "" ? "—" : String(value);
}

function normalize(text) {
  return String(text || "").toLowerCase();
}

function boolValue(value) {
  if (typeof value === "boolean") return value;
  return ["1", "true", "yes", "sim"].includes(normalize(value).trim());
}

function localDateString(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function datePart(value) {
  return String(value || "").split("T")[0].split(" ")[0];
}

function slugify(text) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function safeStorageGet(key, fallback = "") {
  try {
    return window.localStorage.getItem(key) ?? fallback;
  } catch (_error) {
    return fallback;
  }
}

function safeStorageSet(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (_error) {
    return;
  }
}

function getQuickFilterCriteria() {
  return QUICK_FILTERS[state.quickFilterKey] || null;
}

function matchesFilters(job) {
  const quickFilter = getQuickFilterCriteria();
  if (quickFilter?.classification && normalize(job.classificacao) !== normalize(quickFilter.classification)) return false;
  if (quickFilter?.status && normalize(job.status_candidatura) !== normalize(quickFilter.status)) return false;
  if (quickFilter?.newToday && datePart(job.first_seen_at) !== localDateString()) return false;
  if (quickFilter?.newLastRun && !boolValue(job.is_new_in_run)) return false;

  const text = normalize(state.filters.text);
  if (text) {
    const haystack = [
      job.titulo,
      job.empresa,
      job.origem,
      job.modalidade,
      job.localidade,
      job.classificacao,
      job.status_candidatura,
      job.motivos_score,
      job.observacoes,
    ]
      .map(normalize)
      .join(" ");
    if (!haystack.includes(text)) return false;
  }
  if (state.filters.origin && normalize(job.origem) !== normalize(state.filters.origin)) return false;
  if (state.filters.classification && normalize(job.classificacao) !== normalize(state.filters.classification)) return false;
  if (state.filters.status && normalize(job.status_candidatura) !== normalize(state.filters.status)) return false;
  if (state.filters.modality && normalize(job.modalidade) !== normalize(state.filters.modality)) return false;
  if (state.filters.onlyHigh && normalize(job.classificacao) !== "alta") return false;
  if (state.filters.onlyUnreviewed && normalize(job.status_candidatura) !== "não avaliada") return false;
  if (state.filters.onlySent && normalize(job.status_candidatura) !== "candidatura enviada") return false;
  if (state.filters.onlyReview && normalize(job.status_candidatura) !== "revisar") return false;
  if (state.filters.hideIgnore && normalize(job.classificacao) === "ignorar") return false;
  return true;
}

function compareJobs(a, b) {
  const sortBy = state.filters.sortBy;
  if (sortBy === "priority_rank") {
    return (Number(b.priority_rank || 0) - Number(a.priority_rank || 0)) || compareJobsByTitle(a, b);
  }
  if (sortBy === "score_aderencia") {
    return (Number(b.score_aderencia || 0) - Number(a.score_aderencia || 0)) || compareJobsByTitle(a, b);
  }
  if (sortBy === "classificacao") {
    return (CLASS_ORDER[a.classificacao] ?? 99) - (CLASS_ORDER[b.classificacao] ?? 99) || compareJobsByTitle(a, b);
  }
  if (sortBy === "origem") return normalize(a.origem).localeCompare(normalize(b.origem)) || compareJobsByTitle(a, b);
  if (sortBy === "empresa") return normalize(a.empresa).localeCompare(normalize(b.empresa)) || compareJobsByTitle(a, b);
  if (sortBy === "titulo") return normalize(a.titulo).localeCompare(normalize(b.titulo));
  return 0;
}

function compareJobsByTitle(a, b) {
  return normalize(a.titulo).localeCompare(normalize(b.titulo));
}

function shortValue(value, fallback = "—") {
  const text = formatValue(value);
  return text === "—" ? fallback : text;
}

function formatClock(timestamp) {
  if (!timestamp) return "—";
  const text = String(timestamp);
  const timePart = text.includes("T") ? text.split("T")[1] : text;
  return timePart.split(".")[0].slice(0, 8) || "—";
}

function cleanCopyText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function buildSummaryText(job) {
  return cleanCopyText(
    [
      `${job.titulo || "Vaga"}`,
      job.empresa ? `na ${job.empresa}` : "",
      job.origem ? `(${job.origem})` : "",
      job.classificacao ? `classificação ${job.classificacao}` : "",
      job.score_aderencia != null ? `score ${job.score_aderencia}` : "",
      job.modalidade ? `modalidade ${job.modalidade}` : "",
      job.localidade ? `localidade ${job.localidade}` : "",
      job.status_candidatura ? `status ${job.status_candidatura}` : "",
    ]
      .filter(Boolean)
      .join(", ")
  );
}

function buildJobMetaText(job) {
  return [job.empresa, job.origem, job.modalidade, job.status_candidatura].filter(Boolean).join(" • ");
}

async function copyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.style.position = "fixed";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function createOption(value, label) {
  const option = document.createElement("option");
  option.value = value;
  option.textContent = label;
  return option;
}

function fillSelect(select, values) {
  values.forEach((value) => select.appendChild(createOption(value, value)));
}

function countActiveFilters() {
  const filters = state.filters;
  let count = 0;
  if (filters.text.trim()) count += 1;
  if (filters.origin) count += 1;
  if (filters.classification) count += 1;
  if (filters.status) count += 1;
  if (filters.modality) count += 1;
  if (filters.onlyHigh) count += 1;
  if (filters.onlyUnreviewed) count += 1;
  if (filters.onlySent) count += 1;
  if (filters.onlyReview) count += 1;
  if (filters.hideIgnore) count += 1;
  if (state.quickFilterKey && state.quickFilterKey !== "total") count += 1;
  return count;
}

function syncQuickFilterUi() {
  document.querySelectorAll(".summary-card").forEach((card) => {
    const key = card.dataset.quickFilter || "total";
    const active = key === state.quickFilterKey;
    card.classList.toggle("active", active);
    card.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function syncFiltersToggleUi() {
  const activeCount = countActiveFilters();
  const body = byId("filtersBody");
  const toggle = byId("filtersToggle");
  const count = byId("filtersToggleCount");
  body.classList.toggle("hidden", !state.filtersOpen);
  toggle.setAttribute("aria-expanded", state.filtersOpen ? "true" : "false");
  count.textContent = activeCount === 0 ? "0 ativos" : `${activeCount} ativo${activeCount === 1 ? "" : "s"}`;
  toggle.classList.toggle("active", activeCount > 0);
}

function setFiltersOpen(open, persist = true) {
  state.filtersOpen = Boolean(open);
  if (persist) safeStorageSet(STORAGE_KEYS.filtersOpen, state.filtersOpen ? "1" : "0");
  syncFiltersToggleUi();
}

function setQuickFilter(key, persist = true) {
  const nextKey = QUICK_FILTERS[key] ? key : "total";
  state.quickFilterKey = nextKey;
  if (persist) safeStorageSet(STORAGE_KEYS.quickFilter, nextKey);
  syncQuickFilterUi();
  syncFiltersToggleUi();
  renderJobs();
}

function setCardHandlers() {
  document.querySelectorAll(".summary-card").forEach((card) => {
    const activate = () => {
      const key = card.dataset.quickFilter || "total";
      if (key === state.quickFilterKey && key !== "total") {
        setQuickFilter("total");
      } else {
        setQuickFilter(key);
      }
    };
    card.addEventListener("click", activate);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        activate();
      }
    });
  });
}

function showToast(message, tone = "success") {
  const toast = byId("toast");
  toast.className = `toast ${tone}`.trim();
  toast.textContent = message;
  toast.classList.remove("hidden");
  if (toastTimer) window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toast.classList.add("hidden");
  }, 2600);
}

function openConfirmDialog(message) {
  return new Promise((resolve) => {
    confirmResolve = resolve;
    byId("confirmTitle").textContent = message;
    byId("confirmBackdrop").classList.remove("hidden");
    byId("confirmDialog").classList.remove("hidden");
    byId("confirmDialog").setAttribute("aria-hidden", "false");
  });
}

function closeConfirmDialog(result) {
  byId("confirmBackdrop").classList.add("hidden");
  byId("confirmDialog").classList.add("hidden");
  byId("confirmDialog").setAttribute("aria-hidden", "true");
  const resolve = confirmResolve;
  confirmResolve = null;
  if (resolve) resolve(result);
}

function currentDetailValues() {
  return {
    status: byId("detailStatus").value,
    observacoes: byId("detailObservacoes").value,
  };
}

function updateDetailDirtyState() {
  if (state.detail.suppressDirtyCheck) return;
  const current = currentDetailValues();
  state.detail.dirty = (
    current.status !== state.detail.initialStatus ||
    current.observacoes !== state.detail.initialObservacoes
  );
}

function syncDetailDirtyUi() {
  byId("detailPanel").classList.toggle("dirty", state.detail.dirty);
  byId("closeDetailBtn").textContent = state.detail.dirty ? "Voltar" : "Fechar";
}

function setDetailSnapshot(status, observacoes) {
  state.detail.initialStatus = status || "não avaliada";
  state.detail.initialObservacoes = observacoes || "";
  state.detail.dirty = false;
  syncDetailDirtyUi();
}

function applyDetailDraft(draft) {
  state.detail.suppressDirtyCheck = true;
  byId("detailStatus").value = draft.status ?? state.detail.initialStatus;
  byId("detailObservacoes").value = draft.observacoes ?? state.detail.initialObservacoes;
  state.detail.suppressDirtyCheck = false;
  updateDetailDirtyState();
  syncDetailDirtyUi();
}

function renderSummary() {
  const summary = state.summary || { total: 0, by_classification: {}, by_origin: {}, by_status: {}, data_file: "", data_file_mtime: "", updated_at: "" };
  byId("totalCount").textContent = summary.total ?? 0;
  byId("countNewToday").textContent = summary.total_new_today ?? 0;
  byId("countNewLastRun").textContent = summary.total_new_last_run ?? 0;
  byId("countHigh").textContent = summary.by_classification?.Alta ?? 0;
  byId("countMedium").textContent = summary.by_classification?.Média ?? 0;
  byId("countSent").textContent = summary.by_status?.["candidatura enviada"] ?? 0;
  byId("countReview").textContent = summary.by_status?.revisar ?? 0;
  byId("countBlock").textContent = summary.by_status?.["não enviar"] ?? 0;
  const updatedAt = formatClock(summary.updated_at);
  byId("panelSummary").textContent = `${summary.total ?? 0} vagas | Atualizado ${updatedAt}`;
  const dataFile = summary.data_file ? `${summary.data_file}${summary.data_file_mtime ? ` • ${summary.data_file_mtime}` : ""}` : "Nenhum CSV carregado";
  byId("dataFile").textContent = dataFile;
  syncQuickFilterUi();
  syncFiltersToggleUi();
}

function renderJobs() {
  const jobsList = byId("jobsList");
  if (!jobsList) {
    console.error("jobsList não encontrado");
    return;
  }
  jobsList.innerHTML = "";
  const template = byId("jobCardTemplate");
  if (!template) {
    console.error("jobCardTemplate não encontrado");
    jobsList.innerHTML = '<div class="empty-state">Erro ao carregar o template dos cards.</div>';
    return;
  }
  const filteredJobs = state.jobs.filter(matchesFilters).sort(compareJobs);
  console.info("renderJobs", {
    total: state.jobs.length,
    filtered: filteredJobs.length,
    quickFilter: state.quickFilterKey,
    filters: { ...state.filters },
    jobsList,
  });

  if (filteredJobs.length === 0) {
    jobsList.innerHTML = '<div class="empty-state">Nenhuma vaga encontrada com os filtros atuais. Limpe os filtros para ver todas.</div>';
    return;
  }

  const fragment = document.createDocumentFragment();

  filteredJobs.forEach((job) => {
    const card = template.content.firstElementChild.cloneNode(true);
    card.dataset.jobKey = job.job_key || "";
    card.classList.add(`class-${slugify(job.classificacao)}`);
    card.classList.add(`status-${slugify(job.status_candidatura)}`);

    const badge = card.querySelector(".job-card-badge");
    const statusSelect = card.querySelector(".status-select");
    const saveBtn = card.querySelector(".save-btn");
    const detailsBtn = card.querySelector(".details-btn");
    const openLink = card.querySelector(".open-link");
    const score = card.querySelector(".job-card-score");
    const title = card.querySelector(".job-card-title");
    const meta = card.querySelector(".job-card-meta");
    const motivos = card.querySelector(".job-card-motivos-text");
    const obs = card.querySelector(".observacoes-input");

    score.textContent = `${job.score_aderencia ?? 0}${job.score_bruto != null && job.score_bruto !== "" ? ` / ${job.score_bruto}` : ""}`;
    badge.textContent = job.classificacao || "Ignorar";
    badge.title = job.classificacao || "Ignorar";
    title.textContent = formatValue(job.titulo);
    title.title = job.titulo || "";
    meta.textContent = [job.empresa, job.modalidade, job.localidade, job.status_candidatura].filter(Boolean).join(" • ");
    meta.title = meta.textContent;
    motivos.textContent = formatValue(job.motivos_score);
    motivos.title = job.motivos_score || "";
    obs.value = job.observacoes || "";
    obs.title = job.observacoes || "";
    obs.setAttribute("aria-label", `Notas da vaga: ${job.titulo || "vaga"}`);

    statusSelect.innerHTML = "";
    STATUS_OPTIONS.forEach((status) => statusSelect.appendChild(createOption(status, status)));
    statusSelect.value = job.status_candidatura || "não avaliada";

    if (job.link) {
      openLink.href = job.link;
      openLink.classList.remove("disabled");
    } else {
      openLink.removeAttribute("href");
      openLink.classList.add("disabled");
      openLink.textContent = "Sem link";
    }

    saveBtn.addEventListener("click", async () => {
      saveBtn.disabled = true;
      try {
        await saveJobStatus(job.job_key, statusSelect.value, obs.value);
        job.status_candidatura = statusSelect.value;
        job.observacoes = obs.value;
        await loadSummary();
        renderSummary();
        renderJobs();
        showToast("Alterações salvas");
      } catch (error) {
        showToast(`Erro ao salvar: ${error.message || "falha inesperada"}`, "error");
      } finally {
        saveBtn.disabled = false;
      }
    });

    card.querySelector(".details-summary").textContent = buildSummaryText(job);
    card.querySelector(".details-motivos").textContent = formatValue(job.motivos_score);
    card.querySelector(".details-observacoes").textContent = formatValue(job.observacoes);
    card.querySelector(".details-status").textContent = formatValue(job.status_candidatura);
    card.querySelector(".details-meta").textContent = [job.empresa, job.modalidade, job.localidade].map(formatValue).join(" / ");
    const detailsLink = card.querySelector(".details-link");
    detailsLink.innerHTML = "";
    if (job.link) {
      const anchor = document.createElement("a");
      anchor.href = job.link;
      anchor.target = "_blank";
      anchor.rel = "noreferrer";
      anchor.textContent = job.link;
      detailsLink.appendChild(anchor);
    } else {
      detailsLink.textContent = "—";
    }

    detailsBtn.addEventListener("click", () => {
      const isOpen = card.classList.toggle("expanded");
      detailsBtn.textContent = isOpen ? "Ocultar detalhes" : "Ver detalhes";
    });

    card.addEventListener("click", (event) => {
      if (event.target.closest("button, a, input, select, textarea, label")) return;
      requestOpenDetail(job.job_key);
    });

    fragment.appendChild(card);
  });

  jobsList.appendChild(fragment);
  console.info("cards renderizados", jobsList.querySelectorAll(".job-card").length);
}

function refreshFiltersOptions() {
  const origins = [...new Set(state.jobs.map((job) => job.origem).filter(Boolean))].sort((a, b) => normalize(a).localeCompare(normalize(b)));
  const classifications = [...new Set(state.jobs.map((job) => job.classificacao).filter(Boolean))];
  const statuses = [...new Set(state.jobs.map((job) => job.status_candidatura).filter(Boolean))];
  const modalities = [...new Set(state.jobs.map((job) => job.modalidade).filter(Boolean))];

  const originSelect = byId("filterOrigin");
  const classSelect = byId("filterClass");
  const statusSelect = byId("filterStatus");
  const modalitySelect = byId("filterModalidade");

  [originSelect, classSelect, statusSelect, modalitySelect].forEach((select, index) => {
    const current = select.value;
    select.innerHTML = "";
    select.appendChild(createOption("", index === 0 ? "Todas" : "Todas"));
    if (select === originSelect) fillSelect(select, origins);
    if (select === classSelect) fillSelect(select, classifications);
    if (select === statusSelect) fillSelect(select, statuses);
    if (select === modalitySelect) fillSelect(select, modalities);
    select.value = current;
  });
}

async function loadSummary() {
  const response = await fetch("/api/summary", { cache: "no-store" });
  state.summary = await response.json();
}

async function loadJobs() {
  const response = await fetch("/api/jobs", { cache: "no-store" });
  const payload = await response.json();
  state.jobs = Array.isArray(payload.jobs) ? payload.jobs : [];
}

async function saveJobStatus(jobKey, status, observacoes) {
  const response = await fetch("/api/job-status", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_key: jobKey,
      status_candidatura: status,
      observacoes,
    }),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "Falha ao salvar status");
  }
}

function setDetailField(field, value) {
  const el = document.querySelector(`#detailGrid [data-field="${field}"]`);
  if (el) el.textContent = formatValue(value);
}

function fillDetailStatus(currentStatus) {
  const select = byId("detailStatus");
  select.innerHTML = "";
  STATUS_OPTIONS.forEach((status) => select.appendChild(createOption(status, status)));
  select.value = currentStatus || "não avaliada";
}

function openModal() {
  byId("detailBackdrop").classList.remove("hidden");
  byId("detailPanel").classList.remove("hidden");
  byId("detailPanel").setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
}

function forceCloseDetail() {
  byId("detailBackdrop").classList.add("hidden");
  byId("detailPanel").classList.add("hidden");
  byId("detailPanel").setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");
  state.selectedJobKey = null;
  state.detail.initialStatus = "";
  state.detail.initialObservacoes = "";
  state.detail.dirty = false;
  syncDetailDirtyUi();
}

async function requestCloseDetail() {
  if (!state.detail.dirty) {
    forceCloseDetail();
    return true;
  }
  const confirmed = await openConfirmDialog("Deseja descartar as alterações realizadas?");
  if (confirmed) forceCloseDetail();
  return confirmed;
}

function openDetail(jobKey, options = {}) {
  const job = jobByKey(jobKey);
  if (!job) return;
  state.selectedJobKey = jobKey;
  byId("detailTitle").textContent = job.titulo || "Vaga";
  byId("detailSubtitle").textContent = [job.empresa, job.origem, job.classificacao].filter(Boolean).join(" • ");

  setDetailField("titulo", job.titulo);
  setDetailField("empresa", job.empresa);
  setDetailField("origem", job.origem);
  setDetailField("classificacao", job.classificacao);
  setDetailField("score_aderencia", job.score_aderencia);
  setDetailField("score_bruto", job.score_bruto ?? "");
  setDetailField("modalidade", job.modalidade);
  setDetailField("localidade", job.localidade);
  setDetailField("salario", job.salario);
  setDetailField("regime_contratacao", job.regime_contratacao);
  setDetailField("nivel", job.nivel);
  setDetailField("status_candidatura", job.status_candidatura);
  byId("detailDescricao").textContent = formatValue(job.descricao);
  byId("detailRequisitos").textContent = formatValue(job.requisitos);
  byId("detailBeneficios").textContent = formatValue(job.beneficios);
  byId("detailTags").textContent = formatValue(job.tags);
  byId("detailMotivos").textContent = formatValue(job.motivos_score);
  const detailLink = byId("detailLink");
  detailLink.innerHTML = "";
  if (job.link) {
    const anchor = document.createElement("a");
    anchor.href = job.link;
    anchor.target = "_blank";
    anchor.rel = "noreferrer";
    anchor.textContent = job.link;
    detailLink.appendChild(anchor);
  } else {
    detailLink.textContent = "—";
  }
  const openOriginalBtn = byId("openOriginalBtn");
  if (job.link) {
    openOriginalBtn.href = job.link;
    openOriginalBtn.classList.remove("disabled");
  } else {
    openOriginalBtn.removeAttribute("href");
    openOriginalBtn.classList.add("disabled");
  }
  const preserveDraft = Boolean(options.preserveDraft);
  if (preserveDraft && state.detail.dirty && state.detail.initialStatus) {
    applyDetailDraft({
      status: byId("detailStatus").value || state.detail.initialStatus,
      observacoes: byId("detailObservacoes").value,
    });
  } else {
    state.detail.suppressDirtyCheck = true;
    fillDetailStatus(job.status_candidatura);
    byId("detailObservacoes").value = job.observacoes || "";
    state.detail.suppressDirtyCheck = false;
    setDetailSnapshot(byId("detailStatus").value, byId("detailObservacoes").value);
  }
  openModal();
}

function currentDetailJob() {
  return state.selectedJobKey ? jobByKey(state.selectedJobKey) : null;
}

async function requestOpenDetail(jobKey) {
  if (state.selectedJobKey === jobKey) {
    if (state.detail.dirty) return true;
    openDetail(jobKey);
    return true;
  }
  if (!state.selectedJobKey) {
    openDetail(jobKey);
    return true;
  }
  if (state.detail.dirty) {
    const confirmed = await openConfirmDialog("Deseja descartar as alterações realizadas?");
    if (!confirmed) return false;
  }
  openDetail(jobKey);
  return true;
}

async function saveDetailChanges() {
  const job = currentDetailJob();
  if (!job) return;
  const status = byId("detailStatus").value;
  const observacoes = byId("detailObservacoes").value;
  try {
    await saveJobStatus(job.job_key, status, observacoes);
    job.status_candidatura = status;
    job.observacoes = observacoes;
    setDetailSnapshot(status, observacoes);
    await loadSummary();
    renderSummary();
    renderJobs();
    openDetail(job.job_key, { preserveDraft: false });
    showToast("Alterações salvas");
  } catch (error) {
    showToast(`Erro ao salvar: ${error.message || "falha inesperada"}`, "error");
  }
}

async function copyDetailSummary() {
  const job = currentDetailJob();
  if (!job) return;
  const text = buildSummaryText(job);
  await copyToClipboard(text);
}

async function refreshAll() {
  if (state.refreshInFlight) return state.refreshInFlight;
  const detailIsOpen = !byId("detailPanel").classList.contains("hidden");
  const detailSnapshot = detailIsOpen
    ? {
        jobKey: state.selectedJobKey,
        status: byId("detailStatus").value,
        observacoes: byId("detailObservacoes").value,
        dirty: state.detail.dirty,
      }
    : null;
  state.refreshInFlight = (async () => {
    const health = await fetch("/api/health", { cache: "no-store" });
    if (!health.ok) throw new Error("Serviço indisponível");
    await Promise.all([loadSummary(), loadJobs()]);
    refreshFiltersOptions();
    renderSummary();
    renderJobs();
    if (detailSnapshot?.jobKey) {
      openDetail(detailSnapshot.jobKey, { preserveDraft: detailSnapshot.dirty });
      if (detailSnapshot.dirty) {
        applyDetailDraft(detailSnapshot);
      }
    }
  })();
  try {
    await state.refreshInFlight;
  } finally {
    state.refreshInFlight = null;
  }
}

function bindFilters() {
  const textInput = byId("filterText");
  textInput.addEventListener("input", () => {
    state.filters.text = textInput.value;
    syncFiltersToggleUi();
    renderJobs();
  });

  for (const id of ["filterOrigin", "filterClass", "filterStatus", "filterModalidade", "sortBy"]) {
    byId(id).addEventListener("change", (event) => {
      state.filters[id === "filterOrigin" ? "origin" : id === "filterClass" ? "classification" : id === "filterStatus" ? "status" : id === "filterModalidade" ? "modality" : "sortBy"] = event.target.value;
      syncFiltersToggleUi();
      renderJobs();
    });
  }

  byId("onlyHigh").addEventListener("change", (event) => {
    state.filters.onlyHigh = event.target.checked;
    syncFiltersToggleUi();
    renderJobs();
  });
  byId("onlyUnreviewed").addEventListener("change", (event) => {
    state.filters.onlyUnreviewed = event.target.checked;
    syncFiltersToggleUi();
    renderJobs();
  });
  byId("onlySent").addEventListener("change", (event) => {
    state.filters.onlySent = event.target.checked;
    syncFiltersToggleUi();
    renderJobs();
  });
  byId("onlyReview").addEventListener("change", (event) => {
    state.filters.onlyReview = event.target.checked;
    syncFiltersToggleUi();
    renderJobs();
  });
  byId("hideIgnore").addEventListener("change", (event) => {
    state.filters.hideIgnore = event.target.checked;
    syncFiltersToggleUi();
    renderJobs();
  });

  byId("refreshBtn").addEventListener("click", async () => {
    await refreshAll();
  });

  byId("filtersToggle").addEventListener("click", () => {
    setFiltersOpen(!state.filtersOpen);
  });

  byId("closeDetailBtn").addEventListener("click", async () => {
    await requestCloseDetail();
  });
  byId("detailBackdrop").addEventListener("click", async () => {
    await requestCloseDetail();
  });
  byId("confirmBackdrop").addEventListener("click", () => {
    closeConfirmDialog(false);
  });
  byId("confirmCancelBtn").addEventListener("click", () => {
    closeConfirmDialog(false);
  });
  byId("confirmDiscardBtn").addEventListener("click", () => {
    closeConfirmDialog(true);
  });
  byId("saveDetailBtn").addEventListener("click", async () => {
    await saveDetailChanges();
  });
  byId("copySummaryBtn").addEventListener("click", async () => {
    try {
      await copyDetailSummary();
      byId("copySummaryBtn").textContent = "Copiado";
      setTimeout(() => {
        byId("copySummaryBtn").textContent = "Copiar resumo";
      }, 1500);
    } catch (error) {
      byId("copySummaryBtn").textContent = "Falha ao copiar";
      setTimeout(() => {
        byId("copySummaryBtn").textContent = "Copiar resumo";
      }, 1500);
    }
  });

  byId("detailStatus").addEventListener("change", () => {
    updateDetailDirtyState();
    syncDetailDirtyUi();
  });
  byId("detailObservacoes").addEventListener("input", () => {
    updateDetailDirtyState();
    syncDetailDirtyUi();
  });
}

function startAutoRefresh() {
  window.setInterval(() => {
    refreshAll().catch(() => {
      // Atualizacao silenciosa: a proxima rodada tenta novamente.
    });
  }, 60000);
}

async function init() {
  bindFilters();
  setCardHandlers();
  setFiltersOpen(safeStorageGet(STORAGE_KEYS.filtersOpen, "0") === "1", false);
  setQuickFilter(safeStorageGet(STORAGE_KEYS.quickFilter, "total"), false);
  startAutoRefresh();
  try {
    await refreshAll();
  } catch (error) {
    byId("panelSummary").textContent = `Falha ao carregar dados: ${error.message}`;
    byId("dataFile").textContent = `Falha ao carregar dados: ${error.message}`;
  }
}

init();
