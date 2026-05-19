let competencies = [];
let curriculumCourses = [];
let competencyGroupNames = [];
let periods = [];
const pipelineSteps = [
  ["Carga PDF", "Registro de tesis, período académico y metadatos."],
  ["Extracción", "Texto seleccionable u OCR cuando el documento está escaneado."],
  ["Segmentación", "División en chunks con superposición contextual."],
  ["Representación", "Embeddings IA para criterios y fragmentos."],
  ["Resultados", "Mapa de calor, métricas agregadas y justificación textual."]
];

const state = {
  currentPeriodId: null,
  selectedCell: null,
  currentGroup: "all",
  criterionFilter: "all",
  running: false,
  activeStep: -1,
  computeDevice: "auto",
  apiReady: false,
  analysisScores: {},
  apiEvidence: [],
  cellDetails: {},
  expandedComments: {},
  loadingCellDetail: null,
  analysisProgress: null,
  progressTimer: null,
  lastProgressSignature: ""
};

const API_BASE_URL = "http://localhost:8000/api/v1";
const DEMO_TOKEN = "demo-academic-admin";
const ACCEPTED_FILE_EXTENSIONS = [".pdf", ".docx", ".txt"];
const HIDDEN_GROUP_FILTERS = new Set(["Universidad", "UNIVERSIDAD"]);

function fixMojibake(value) {
  if (typeof value !== "string" || !/[ÃÂ]/.test(value)) return value;
  try {
    const bytes = Uint8Array.from(value, (char) => char.charCodeAt(0) & 0xff);
    const decoded = new TextDecoder("utf-8", { fatal: false }).decode(bytes);
    return decoded.includes("�") ? value : decoded;
  } catch (_error) {
    return value;
  }
}

function cleanText(value) {
  return fixMojibake(value);
}

async function apiRequest(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set("Authorization", `Bearer ${DEMO_TOKEN}`);
  if (options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers
  });

  if (!response.ok) {
    throw new Error(`API ${response.status}: ${await response.text()}`);
  }
  return response.json();
}

function deviceLabel(device) {
  if (device === "gpu" || device === "cuda") return "GPU";
  if (device === "cpu") return "CPU";
  return "Auto";
}

function progressSignature(progress) {
  if (!progress) return "";
  return [
    progress.status,
    progress.step,
    progress.current_document_id,
    progress.current_index,
    progress.progress,
    progress.message
  ].join("|");
}

function logProgress(progress) {
  const signature = progressSignature(progress);
  if (!signature || signature === state.lastProgressSignature) return;
  state.lastProgressSignature = signature;
  console.info(
    `[Análisis IA] ${cleanText(progress.message || progress.step)} (${progress.progress || 0}%)`,
    {
      periodo: progress.period_id,
      tesis: cleanText(progress.current_document_title),
      indice: progress.current_index,
      total: progress.total_documents,
      dispositivo: progress.device
    }
  );
}

function escapeHtml(value) {
  return String(cleanText(value) ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function normalizePeriodFromApi(period) {
  return {
    ...period,
    metrics: {
      thesis: period.metrics?.thesis ?? period.thesis?.length ?? 0,
      recall: period.metrics?.recall ?? 0,
      automation: period.metrics?.automation ?? 0
    },
    thesis: period.thesis || []
  };
}

function acceptedThesisFiles(files) {
  return Array.from(files).filter((file) => {
    const name = file.name.toLowerCase();
    return ACCEPTED_FILE_EXTENSIONS.some((extension) => name.endsWith(extension));
  });
}

function isHiddenGroup(groupName) {
  return HIDDEN_GROUP_FILTERS.has(groupName);
}

function visibleEvidenceCompetencies() {
  return competencies.filter((competency) => !isHiddenGroup(competency.group));
}

function competencyFilterValue(competency) {
  return `competency:${competency.id}`;
}

function selectedCompetencyCode(filter) {
  if (filter === "all") return null;
  if (filter.startsWith("competency:")) return filter.replace("competency:", "");

  const legacyIndex = Number(filter);
  return Number.isNaN(legacyIndex) ? null : competencies[legacyIndex]?.id || null;
}

function scoreKey(course, competency) {
  return `${course.db_id || course.code || course.title}::${competency.db_id || competency.id}`;
}

function cellDetailKey(periodId, course, competency) {
  return `${periodId}::${scoreKey(course, competency)}`;
}

async function hydrateFromApi() {
  try {
    await apiRequest("/health");
    const [matrix, apiPeriods] = await Promise.all([
      apiRequest("/curricula/current/matrix"),
      apiRequest("/periods")
    ]);

    competencies = matrix.competencies;
    curriculumCourses = matrix.courses;
    competencyGroupNames = [...new Set(competencies.map((competency) => competency.group))];
    periods = apiPeriods.map(normalizePeriodFromApi);
    state.apiReady = true;
    state.currentPeriodId = periods[0]?.id || null;
    state.selectedCell = firstTributedCell();
    await refreshApiAnalysis();
    renderAll();
  } catch (error) {
    state.apiReady = false;
    state.currentPeriodId = null;
    state.selectedCell = null;
    renderAll();
  }
}

async function refreshApiAnalysis() {
  if (!state.apiReady || !state.currentPeriodId) return;
  try {
    const analysis = await apiRequest(`/periods/${state.currentPeriodId}/analysis`);
    const scores = {};
    analysis.cells.forEach((cell) => {
      scores[`${cell.course_id}::${cell.competency_id}`] = cell.score;
    });
    state.analysisScores[state.currentPeriodId] = scores;
    state.apiEvidence = await apiRequest(`/evidence?period_id=${state.currentPeriodId}&limit=50`);
    state.cellDetails = {};
    state.expandedComments = {};
  } catch (error) {
    state.analysisScores[state.currentPeriodId] = {};
    state.apiEvidence = [];
    state.cellDetails = {};
    state.expandedComments = {};
  }
}

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function currentPeriod() {
  return periods.find((period) => period.id === state.currentPeriodId) || null;
}

function statusMeta(status) {
  if (status === "ready") {
    return { label: "Resultados reutilizables", className: "ready" };
  }
  if (status === "processing") {
    return { label: "Procesando", className: "info" };
  }
  if (status === "empty") {
    return { label: "Sin tesis cargadas", className: "danger" };
  }
  return { label: "Cambios sin recalcular", className: "warning" };
}

function scoreClass(value) {
  if (value >= 75) return "high";
  if (value >= 55) return "mid";
  return "low";
}

function scoreLabel(value) {
  if (value >= 75) return "Evidencia alta";
  if (value >= 55) return "Evidencia media";
  return "Evidencia baja";
}

function cellColor(value) {
  if (value >= 75) {
    const lightness = 86 - (value - 75) * 0.95;
    return `hsl(105, 38%, ${Math.max(lightness, 54)}%)`;
  }
  if (value >= 55) {
    const lightness = 88 - (value - 55) * 0.75;
    return `hsl(39, 80%, ${Math.max(lightness, 67)}%)`;
  }
  const lightness = 89 - value * 0.42;
  return `hsl(8, 58%, ${Math.max(lightness, 64)}%)`;
}

function isTributed(courseIndex, criterionIndex) {
  return curriculumCourses[courseIndex]?.t.includes(criterionIndex) || false;
}

function visibleCompetencyIndexes() {
  return visibleCompetencyIndexesFor(state.currentGroup);
}

function visibleCompetencyIndexesFor(groupName) {
  return competencies
    .map((competency, index) => ({ competency, index }))
    .filter(({ competency }) => groupName === "all" || competency.group === groupName)
    .map(({ index }) => index);
}

function visibleCourseIndexes(groupName = state.currentGroup) {
  const visible = new Set(visibleCompetencyIndexesFor(groupName));

  return curriculumCourses
    .map((course, index) => ({ course, index }))
    .filter(({ course }) => course.t.some((criterionIndex) => visible.has(criterionIndex)))
    .map(({ index }) => index);
}

function groupTributatedCount(groupName) {
  const visible = new Set(visibleCompetencyIndexesFor(groupName));

  return curriculumCourses.reduce(
    (total, course) => total + course.t.filter((criterionIndex) => visible.has(criterionIndex)).length,
    0
  );
}

function scoreFor(courseIndex, criterionIndex, period = currentPeriod()) {
  if (!period || !isTributed(courseIndex, criterionIndex) || !state.apiReady) return null;
  const course = curriculumCourses[courseIndex];
  const competency = competencies[criterionIndex];
  if (!course || !competency) return null;
  const apiScore = state.analysisScores[period.id]?.[scoreKey(course, competency)];
  return apiScore ?? null;
}

function periodStats(period = currentPeriod()) {
  if (!period) {
    return { average: null, gaps: 0, high: 0, medium: 0, low: 0 };
  }
  const scores = [];
  curriculumCourses.forEach((course, courseIndex) => {
    course.t.forEach((criterionIndex) => {
      const score = scoreFor(courseIndex, criterionIndex, period);
      if (score !== null) scores.push(score);
    });
  });

  if (!scores.length) {
    return { average: null, gaps: 0, high: 0, medium: 0, low: 0 };
  }

  const average = Math.round(scores.reduce((sum, value) => sum + value, 0) / scores.length);
  return {
    average,
    gaps: scores.filter((value) => value < 55).length,
    high: scores.filter((value) => value >= 75).length,
    medium: scores.filter((value) => value >= 55 && value < 75).length,
    low: scores.filter((value) => value < 55).length
  };
}

function firstTributedCell(groupName = state.currentGroup) {
  const visible = new Set(visibleCompetencyIndexesFor(groupName));
  const courseIndex = visibleCourseIndexes(groupName)[0] ?? 0;
  if (!curriculumCourses[courseIndex]) return null;

  return {
    courseIndex,
    criterionIndex:
      curriculumCourses[courseIndex]?.t.find((criterionIndex) => visible.has(criterionIndex)) ??
      [...visible][0] ??
      0
  };
}

function renderIcons() {
  if (window.lucide) {
    window.lucide.createIcons();
  }
}

function renderRuntimeState() {
  const runButton = $("#runAnalysis");
  const buttonLabel = $("#runAnalysis span");
  if (runButton) {
    runButton.classList.toggle("is-running", state.running);
    runButton.setAttribute("aria-busy", state.running ? "true" : "false");
    runButton.disabled = !state.apiReady || !state.currentPeriodId || state.running;
  }
  if (buttonLabel && !state.running) {
    buttonLabel.textContent = state.apiReady ? "Analizar con API" : "Sin backend";
  }

  const deviceSelect = $("#computeDevice");
  if (deviceSelect) {
    deviceSelect.value = state.computeDevice;
    deviceSelect.disabled = state.running;
  }

  const note = $(".sidebar-note");
  if (note) {
    note.innerHTML = state.apiReady
      ? `
        <span class="dot ready"></span>
        <div>
          <strong>Backend conectado</strong>
          <p>La interfaz consume la API local y conserva trazabilidad de evidencia.</p>
        </div>
      `
      : `
        <span class="dot ready"></span>
        <div>
          <strong>Backend desconectado</strong>
          <p>No hay datos reales disponibles para mostrar.</p>
        </div>
      `;
  }
}

function renderPeriodOptions() {
  const select = $("#periodSelect");
  if (!periods.length) {
    select.innerHTML = `<option value="">Sin periodos</option>`;
    select.value = "";
    select.disabled = true;
    return;
  }
  select.disabled = false;
  select.innerHTML = periods
    .map((period) => `<option value="${escapeHtml(period.id)}">${escapeHtml(period.name)}</option>`)
    .join("");
  select.value = state.currentPeriodId || periods[0].id;
}

function renderSummary() {
  const period = currentPeriod();
  const currentGroupLabel = state.currentGroup === "all" ? "Toda la matriz" : state.currentGroup;
  const visibleCompetencies = visibleCompetencyIndexes();
  const visibleCourses = visibleCourseIndexes();
  const visibleTributated = groupTributatedCount(state.currentGroup);
  const visibleBlank = visibleCourses.length * visibleCompetencies.length - visibleTributated;
  const cards = [
    ["Tesis analizadas", period?.metrics?.thesis ?? 0, period ? `${period.thesis.length} registradas` : "Sin periodo seleccionado"],
    ["Bloque visible", currentGroupLabel, `${visibleCompetencies.length} competencias en la vista`],
    ["Ramos visibles", visibleCourses.length, `${visibleTributated} cruces ramo-competencia con X`],
    ["Celdas en blanco", visibleBlank, "Dentro de los ramos que aportan al bloque"]
  ];

  $("#summaryGrid").innerHTML = cards
    .map(
      ([label, value, detail]) => `
        <article class="metric-card">
          <span>${label}</span>
          <strong>${value}</strong>
          <p>${detail}</p>
        </article>
      `
    )
    .join("");
}

function renderGroupFilter() {
  if (HIDDEN_GROUP_FILTERS.has(state.currentGroup)) {
    state.currentGroup = "all";
  }

  const groups = ["all", ...competencyGroupNames.filter((group) => !HIDDEN_GROUP_FILTERS.has(group))];
  $("#groupFilter").innerHTML = groups.length && competencies.length
    ? groups
    .map((groupName) => {
      const active = state.currentGroup === groupName;
      const label = groupName === "all" ? "Todas" : groupName;
      const count = visibleCourseIndexes(groupName).length;
      return `
        <button
          class="group-chip ${active ? "active" : ""}"
          type="button"
          data-group="${encodeURIComponent(groupName)}"
          aria-pressed="${active}"
        >
          <span>${label}</span>
          <strong>${count}</strong>
        </button>
      `;
    })
    .join("")
    : "";
}

function renderHeatmap() {
  const period = currentPeriod();
  const heatmap = $("#heatmap");
  const visibleIndexes = visibleCompetencyIndexes();
  const visibleCourses = visibleCourseIndexes();
  if (!period || !visibleIndexes.length || !visibleCourses.length) {
    heatmap.style.gridTemplateColumns = "";
    heatmap.style.minWidth = "";
    heatmap.innerHTML = `<div class="detail-empty">No hay matriz o periodo cargado desde el backend.</div>`;
    return;
  }
  const cells = [`<div class="heatmap-corner">Ramo / Competencia</div>`];

  visibleIndexes.forEach((criterionIndex) => {
    const competency = competencies[criterionIndex];
    cells.push(`
      <div class="heatmap-label competency" title="${competency.name}">
        <strong>${competency.id}</strong>
        <span>${competency.group}</span>
      </div>
    `);
  });

  visibleCourses.forEach((rowIndex) => {
    const course = curriculumCourses[rowIndex];
    const code = course.code || "S/C";
    cells.push(`
      <div class="heatmap-label course" title="${code} ${course.title}">
        <strong>${code}</strong>
        <span>${course.title}</span>
        <small>${course.semester ? `Sem. ${course.semester}` : "Sin semestre"}</small>
      </div>
    `);

    visibleIndexes.forEach((criterionIndex) => {
      const competency = competencies[criterionIndex];
      if (!isTributed(rowIndex, criterionIndex)) {
        cells.push(`
          <div
            class="heatmap-cell blank"
            role="gridcell"
            aria-label="${course.title} no tributa a ${competency.id}"
            title="Sin tributación en la matriz"
          ></div>
        `);
        return;
      }

      const value = scoreFor(rowIndex, criterionIndex, period);
      const selected =
        state.selectedCell?.courseIndex === rowIndex &&
        state.selectedCell?.criterionIndex === criterionIndex;
      const label = value === null ? "Pend." : `${value}%`;
      const style = value === null ? "" : `style="background:${cellColor(value)}"`;

      cells.push(`
        <button
          class="heatmap-cell ${value === null ? "pending" : ""} ${selected ? "selected" : ""}"
          ${style}
          data-row="${rowIndex}"
          data-col="${criterionIndex}"
          type="button"
          role="gridcell"
          aria-label="${course.title}, ${competency.id}, ${value === null ? "pendiente" : `${value}%`}"
          title="${competency.name}"
        >
          ${label}
        </button>
      `);
    });
  });

  heatmap.style.gridTemplateColumns = `230px repeat(${visibleIndexes.length}, minmax(86px, 1fr))`;
  heatmap.style.minWidth = `${230 + visibleIndexes.length * 92}px`;
  heatmap.innerHTML = cells.join("");
}

async function loadCellDetail(courseIndex, criterionIndex) {
  if (!state.apiReady) return;
  const period = currentPeriod();
  const course = curriculumCourses[courseIndex];
  const competency = competencies[criterionIndex];
  if (!course?.db_id || !competency?.db_id) return;

  const key = cellDetailKey(period.id, course, competency);
  if (state.cellDetails[key] || state.loadingCellDetail === key) return;

  state.loadingCellDetail = key;
  try {
    state.cellDetails[key] = await apiRequest(
      `/periods/${period.id}/analysis/cell-detail?course_id=${encodeURIComponent(course.db_id)}&competency_id=${encodeURIComponent(competency.db_id)}`
    );
  } catch (error) {
    delete state.cellDetails[key];
  } finally {
    if (state.loadingCellDetail === key) {
      state.loadingCellDetail = null;
    }
    const selected = state.selectedCell;
    if (selected.courseIndex === courseIndex && selected.criterionIndex === criterionIndex) {
      renderCellDetail();
    }
  }
}

function renderCellDetail() {
  if (!state.selectedCell || !currentPeriod()) {
    $("#cellDetail").className = "detail-empty";
    $("#cellDetail").textContent = "No hay una celda seleccionada.";
    return;
  }

  const { courseIndex, criterionIndex } = state.selectedCell;

  if (!isTributed(courseIndex, criterionIndex)) {
    state.selectedCell = firstTributedCell();
    if (!state.selectedCell) {
      $("#cellDetail").className = "detail-empty";
      $("#cellDetail").textContent = "No hay celdas tributadas disponibles.";
      return;
    }
  }

  const selected = state.selectedCell;
  const value = scoreFor(selected.courseIndex, selected.criterionIndex);
  const course = curriculumCourses[selected.courseIndex];
  const competency = competencies[selected.criterionIndex];
  if (!course || !competency) {
    $("#cellDetail").className = "detail-empty";
    $("#cellDetail").textContent = "No hay detalle disponible.";
    return;
  }
  const detailKey = cellDetailKey(currentPeriod().id, course, competency);
  const aiDetail = state.apiReady ? state.cellDetails[detailKey] : null;
  const levelClass = value === null ? "mid" : scoreClass(value);
  const isLoadingDetail = state.apiReady && !aiDetail;
  const generalComment = aiDetail?.general_comment || "";
  const commentIsLong = generalComment.length > 460;
  const commentExpanded = Boolean(state.expandedComments[detailKey]);
  const commentMeta = aiDetail
    ? `${aiDetail.general_evidence_document_count || 0} de ${aiDetail.general_document_count || 0} tesis con evidencia - ${aiDetail.general_evidence_count || 0} evidencias`
    : "";
  const origin = aiDetail
    ? [aiDetail.evidence_origin, aiDetail.evidence_page ? `Pagina ${aiDetail.evidence_page}` : ""]
        .filter(Boolean)
        .join(" · ")
    : "";

  $("#cellDetail").className = "detail-content";
  $("#cellDetail").innerHTML = `
    <div class="score-line">
      <div>
        <h3>${escapeHtml(course.code || "S/C")} · ${escapeHtml(course.title)}</h3>
        <p>${escapeHtml(competency.id)} · ${escapeHtml(competency.group)}</p>
      </div>
      <span class="score-badge ${levelClass}">${value === null ? "Pend." : `${value}%`}</span>
    </div>

    <div class="quote-box">
      <strong>Competencia tributada</strong>
      <p>${escapeHtml(competency.name)}</p>
    </div>

    ${
      isLoadingDetail
        ? `
          <div class="detail-loading" role="status" aria-live="polite">
            <span class="loading-spinner" aria-hidden="true"></span>
            <div>
              <strong>Generando comentario IA</strong>
              <p>Recuperando evidencia y redactando justificación trazable.</p>
            </div>
          </div>
        `
        : ""
    }

    ${
      aiDetail
        ? `
          <div class="quote-box">
            <strong>Justificacion IA trazable</strong>
            <p>${escapeHtml(aiDetail.justification)}</p>
          </div>

          <div class="quote-box general-comment-box">
            <strong>Comentario general</strong>
            <p class="general-comment ${commentIsLong && !commentExpanded ? "clamped" : ""}">${escapeHtml(generalComment)}</p>
            <p class="evidence-meta">${escapeHtml(commentMeta)}</p>
            ${
              commentIsLong
                ? `<button class="text-toggle toggle-general-comment" type="button" data-detail-key="${escapeHtml(detailKey)}">${commentExpanded ? "Ver menos" : "Ver m&aacute;s"}</button>`
                : ""
            }
          </div>

          <div class="action-box">
            <strong>Accion sugerida</strong>
            <p>${escapeHtml(aiDetail.suggested_action)}</p>
          </div>
        `
        : ""
    }
  `;

  if (isLoadingDetail) {
    loadCellDetail(selected.courseIndex, selected.criterionIndex);
  }
}

function renderPeriodList() {
  $("#periodList").innerHTML = periods.length
    ? periods
    .map((period) => {
      const meta = statusMeta(period.status);
      return `
        <button class="period-item ${period.id === state.currentPeriodId ? "active" : ""}" data-period="${period.id}" type="button">
          <strong>${period.name}</strong>
          <span class="status-pill ${meta.className}">${meta.label}</span>
          <span class="period-meta">
            <span>${period.metrics.thesis} tesis</span>
            <span>Última actualización: ${period.updatedAt}</span>
          </span>
        </button>
      `;
    })
    .join("")
    : `<div class="detail-empty">No hay periodos cargados.</div>`;
}

function renderAnalysisProgress() {
  const container = $("#analysisProgress");
  if (!container) return;
  const progress = state.analysisProgress;
  const isCurrentPeriod = progress?.period_id === currentPeriod()?.id;
  const visible = Boolean(
    progress &&
      isCurrentPeriod &&
      ["running", "failed"].includes(progress.status)
  );
  container.classList.toggle("active", visible);
  if (!visible) {
    container.innerHTML = "";
    return;
  }

  const title = progress.current_document_title
    ? `Tesis ${progress.current_index}/${progress.total_documents}: ${progress.current_document_title}`
    : progress.status === "failed"
      ? "Análisis detenido"
    : "Evaluando matriz de tributacion";
  container.innerHTML = `
    <div>
      <strong>${escapeHtml(title)}</strong>
      <p>${escapeHtml(progress.error || progress.message || "Procesando analisis documental.")}</p>
      <p>Dispositivo: ${escapeHtml(deviceLabel(progress.device))}</p>
    </div>
    <div class="progress-track" aria-hidden="true">
      <div class="progress-fill" style="width:${Math.max(0, Math.min(100, progress.progress || 0))}%"></div>
    </div>
  `;
}

function renderThesisTable() {
  const period = currentPeriod();
  if (!period) {
    $("#thesisTable").innerHTML = `<tr><td colspan="5">No hay periodo seleccionado.</td></tr>`;
    return;
  }
  const progress = state.analysisProgress;
  const rows = period.thesis.map(
    ([title, author, pages, status, documentId], index) => {
      const isCurrent =
        state.running &&
        progress?.period_id === period.id &&
        progress?.status === "running" &&
        documentId &&
        progress.current_document_id === documentId;
      return `
      <tr class="${isCurrent ? "current-thesis" : ""}">
        <td>${escapeHtml(title)}</td>
        <td>${escapeHtml(author)}</td>
        <td>
          <div class="thesis-status">
            <span class="status-pill ${status.includes("reciente") ? "warning" : "ready"}">${escapeHtml(status)}</span>
            ${
              isCurrent
                ? `<span class="processing-now"><span class="mini-spinner" aria-hidden="true"></span>Procesando ahora</span>`
                : ""
            }
          </div>
        </td>
        <td>${escapeHtml(pages)}</td>
        <td>
          <button class="icon-button delete-thesis" data-index="${index}" data-document-id="${escapeHtml(documentId || "")}" type="button" aria-label="Eliminar tesis ${escapeHtml(title)}">
            <i data-lucide="trash-2"></i>
          </button>
        </td>
      </tr>
    `;
    }
  );

  $("#thesisTable").innerHTML =
    rows.join("") ||
    `<tr><td colspan="5">Este período aún no tiene tesis cargadas.</td></tr>`;
}

function renderPipeline() {
  $("#pipeline").innerHTML = pipelineSteps
    .map(([title, detail], index) => {
      const done = state.running && index < state.activeStep;
      const active = state.running && index === state.activeStep;
      return `
        <article class="pipeline-step ${done ? "done" : ""} ${active ? "active" : ""}">
          <span class="step-number">${index + 1}</span>
          <strong>${title}</strong>
          <p>${detail}</p>
        </article>
      `;
    })
    .join("");
}

function renderEvidence() {
  const evidenceCounts = new Map();
  state.apiEvidence.forEach((item) => {
    if (isHiddenGroup(item.competency_group)) return;
    evidenceCounts.set(item.competency_code, (evidenceCounts.get(item.competency_code) || 0) + 1);
  });

  const availableCompetencies = visibleEvidenceCompetencies().filter((competency) => {
    if (!state.apiReady || !state.apiEvidence.length) return true;
    return evidenceCounts.has(competency.id);
  });
  const validFilters = new Set(["all", ...availableCompetencies.map(competencyFilterValue)]);
  if (!validFilters.has(state.criterionFilter)) {
    state.criterionFilter = "all";
  }

  const filter = state.criterionFilter;
  const filterCode = selectedCompetencyCode(filter);
  const criterionOptions = [
    `<option value="all">Todas las competencias</option>`,
    ...competencies.map((competency, index) => `<option value="${index}">${competency.id} · ${competency.group}</option>`)
  ];
  const usefulCriterionOptions = [
    `<option value="all">Todas las competencias</option>`,
    ...availableCompetencies.map((competency) => {
      const count = evidenceCounts.get(competency.id);
      const suffix = count ? ` (${count})` : "";
      return `<option value="${competencyFilterValue(competency)}">${competency.id} · ${competency.group}${suffix}</option>`;
    })
  ];
  $("#criterionFilter").innerHTML = usefulCriterionOptions.join("");
  $("#criterionFilter").value = filter;

  if (!state.apiReady || !currentPeriod()) {
    $("#evidenceList").innerHTML = `<article class="evidence-item"><p>No hay evidencia cargada desde el backend.</p></article>`;
    return;
  }

  if (state.apiReady) {
    const apiItems = state.apiEvidence.filter((item) => {
      if (isHiddenGroup(item.competency_group)) return false;
      if (!filterCode) return true;
      return item.competency_code === filterCode;
    });

    $("#evidenceList").innerHTML =
      apiItems
        .slice(0, 12)
        .map(
          (item) => `
            <article class="evidence-item">
              <div>
                <h3>${escapeHtml(item.course_code) || "S/C"} · ${escapeHtml(item.course_title)}</h3>
                <p>${escapeHtml(item.text)}</p>
                <div class="evidence-meta">
                  <span>${escapeHtml(item.competency_code)}</span>
                  <span>Página ${escapeHtml(item.page)}</span>
                  <span>${escapeHtml(item.document_title)}</span>
                </div>
              </div>
              <span class="similarity">${Math.round(item.confidence * 100)}%</span>
            </article>
          `
        )
        .join("") || `<article class="evidence-item"><p>No hay evidencia real procesada para este filtro.</p></article>`;
    return;
  }
}

function renderKpis() {
  const period = currentPeriod();
  const stats = periodStats(period);
  if (!period) {
    $("#kpiBars").innerHTML = `<article class="evidence-item"><p>No hay indicadores disponibles.</p></article>`;
    return;
  }
  const kpis = [
    [
      "Trazabilidad por criterio",
      stats.traceability ?? stats.average,
      "Porcentaje promedio de tesis con evidencia explicita por criterio."
    ],
    [
      "Brechas detectadas",
      stats.gaps,
      "Celdas tributadas con evidencia bajo el umbral esperado."
    ],
    [
      "Evidencias recuperadas",
      state.apiEvidence.length,
      "Fragmentos trazables cargados desde el backend para el periodo."
    ]
  ];

  $("#kpiBars").innerHTML = kpis
    .map(
      ([title, value, description]) => `
        <article class="kpi-bar">
          <div class="kpi-row">
            <span>${title}</span>
            <strong>${value === null ? "Sin datos" : value}</strong>
          </div>
          <div class="bar-track" aria-hidden="true">
            <div class="bar-fill" style="width:${value === null ? 0 : Math.min(100, value)}%"></div>
          </div>
          <p>${description}</p>
        </article>
      `
    )
    .join("");
}

function renderAll() {
  renderRuntimeState();
  renderPeriodOptions();
  renderSummary();
  renderGroupFilter();
  renderHeatmap();
  renderCellDetail();
  renderPeriodList();
  renderAnalysisProgress();
  renderThesisTable();
  renderPipeline();
  renderEvidence();
  renderKpis();
  renderIcons();
}

async function setPeriod(periodId) {
  state.currentPeriodId = periodId;
  state.selectedCell = firstTributedCell();
  await refreshApiAnalysis();
  renderAll();
}

function setView(viewId) {
  $$(".view").forEach((view) => view.classList.toggle("active", view.id === viewId));
  $$(".nav-item").forEach((item) => item.classList.toggle("active", item.dataset.view === viewId));
}

function markPeriodChanged(period) {
  period.status = period.thesis.length ? "warning" : "empty";
  period.updatedAt = "Ahora";
  period.analyzedAt = period.thesis.length ? "Pendiente de recálculo" : "Sin análisis";
  period.metrics.thesis = period.thesis.length;
}

function stopAnalysisProgressPolling() {
  if (state.progressTimer) {
    window.clearInterval(state.progressTimer);
    state.progressTimer = null;
  }
}

async function pollAnalysisProgress(periodId) {
  const progress = await apiRequest(`/periods/${periodId}/analysis/progress`);
  state.analysisProgress = progress;
  state.activeStep = progress.status === "running" ? Math.max(0, progress.ui_step ?? 0) : -1;
  logProgress(progress);
  renderRuntimeState();
  renderAnalysisProgress();
  renderThesisTable();
  renderPeriodList();
  renderPipeline();
  renderIcons();

  if (progress.status === "completed" || progress.status === "failed") {
    stopAnalysisProgressPolling();
    state.running = false;
    state.activeStep = -1;
    const apiPeriods = await apiRequest("/periods");
    periods = apiPeriods.map(normalizePeriodFromApi);
    await refreshApiAnalysis();
    renderAll();
  }
}

function startAnalysisProgressPolling(periodId) {
  stopAnalysisProgressPolling();
  state.lastProgressSignature = "";
  pollAnalysisProgress(periodId).catch((error) => {
    console.warn("[Análisis IA] No se pudo leer el progreso inicial.", error);
  });
  state.progressTimer = window.setInterval(() => {
    pollAnalysisProgress(periodId).catch((error) => {
      console.warn("[Análisis IA] No se pudo actualizar el progreso.", error);
    });
  }, 1200);
}

function renderUploadProgress(fileStatuses) {
  const container = $("#uploadProgress");
  if (!container) return;
  if (!fileStatuses || !fileStatuses.length) {
    container.classList.remove("active");
    container.innerHTML = "";
    return;
  }

  container.classList.add("active");
  const done = fileStatuses.filter((f) => f.status === "done").length;
  const failed = fileStatuses.filter((f) => f.status === "error").length;
  const total = fileStatuses.length;
  const allFinished = fileStatuses.every((f) => f.status === "done" || f.status === "error");
  const pct = Math.round(((done + failed) / total) * 100);

  const headerText = allFinished
    ? failed > 0
      ? `${done} de ${total} tesis subidas (${failed} con error)`
      : `${done} tesis subidas correctamente`
    : `Subiendo tesis: ${done + failed} de ${total}`;

  const items = fileStatuses
    .map((f) => {
      const icon =
        f.status === "done"
          ? '<span class="upload-icon done">&#10003;</span>'
          : f.status === "error"
            ? '<span class="upload-icon error">&#10007;</span>'
            : f.status === "uploading"
              ? '<span class="mini-spinner" aria-hidden="true"></span>'
              : '<span class="upload-icon queued">&#8226;</span>';
      const label =
        f.status === "done"
          ? "Subida"
          : f.status === "error"
            ? `Error: ${f.error || "fallo desconocido"}`
            : f.status === "uploading"
              ? "Subiendo..."
              : "En cola";
      return `
        <div class="upload-file-row ${f.status}">
          ${icon}
          <span class="upload-file-name">${escapeHtml(f.name)}</span>
          <span class="upload-file-status">${label}</span>
        </div>
      `;
    })
    .join("");

  container.innerHTML = `
    <div class="upload-progress-header">
      <strong>${headerText}</strong>
    </div>
    <div class="progress-track" aria-hidden="true">
      <div class="progress-fill" style="width:${pct}%"></div>
    </div>
    <div class="upload-file-list">${items}</div>
  `;
}

async function addFiles(files) {
  const selectedFiles = acceptedThesisFiles(files);
  if (!selectedFiles.length) return;

  const period = currentPeriod();
  if (!period) return;

  if (!state.apiReady) {
    renderAll();
    return;
  }

  // Build file status tracker
  const fileStatuses = selectedFiles.map((file) => ({
    name: file.name,
    status: "queued",
    error: null,
    file
  }));

  // Disable the upload box while uploads are running
  const uploadBox = $("#uploadBox");
  const fileInput = $("#fileInput");
  if (uploadBox) uploadBox.classList.add("uploading");
  if (fileInput) fileInput.disabled = true;

  renderUploadProgress(fileStatuses);

  let successCount = 0;

  // Upload files one at a time
  for (let i = 0; i < fileStatuses.length; i++) {
    const entry = fileStatuses[i];
    entry.status = "uploading";
    renderUploadProgress(fileStatuses);

    try {
      const form = new FormData();
      form.set("period_id", period.id);
      form.set("title", entry.file.name.replace(/\.[^.]+$/i, "").replace(/[-_]/g, " "));
      form.set("file", entry.file);
      await apiRequest("/documents", {
        method: "POST",
        body: form
      });
      entry.status = "done";
      successCount++;
    } catch (error) {
      entry.status = "error";
      entry.error = error.message || "Error de conexion";
      console.error(`[Upload] Error subiendo ${entry.name}:`, error);
    }

    renderUploadProgress(fileStatuses);
  }

  // Re-enable the upload box
  if (uploadBox) uploadBox.classList.remove("uploading");
  if (fileInput) fileInput.disabled = false;

  // Refresh period data if any upload succeeded
  if (successCount > 0) {
    try {
      const apiPeriods = await apiRequest("/periods");
      periods = apiPeriods.map(normalizePeriodFromApi);
      await refreshApiAnalysis();
    } catch (error) {
      console.warn("[Upload] No se pudo refrescar los periodos:", error);
    }
  }

  renderAll();
  // Keep the progress visible after renderAll
  renderUploadProgress(fileStatuses);

  // Auto-hide after 8 seconds if all finished
  setTimeout(() => {
    const stillVisible = fileStatuses.every((f) => f.status === "done" || f.status === "error");
    if (stillVisible) {
      renderUploadProgress(null);
    }
  }, 8000);
}

async function createPeriod(name) {
  const clean = name.trim();
  if (!clean) return;

  if (state.apiReady) {
    try {
      const created = await apiRequest("/periods", {
        method: "POST",
        body: JSON.stringify({ name: clean })
      });
      const apiPeriods = await apiRequest("/periods");
      periods = apiPeriods.map(normalizePeriodFromApi);
      state.currentPeriodId = created.id;
      state.selectedCell = firstTributedCell();
      await refreshApiAnalysis();
      renderAll();
      return;
    } catch (error) {
      state.apiReady = false;
    }
  }

  renderAll();
}

async function simulateAnalysis() {
  if (state.running) return;
  const period = currentPeriod();
  if (!period) {
    renderAll();
    return;
  }
  if (state.apiReady) {
    try {
      state.running = true;
      state.activeStep = 0;
      period.status = "processing";
      $("#runAnalysis span").textContent = "Analizando";
      state.analysisProgress = {
        period_id: period.id,
        status: "running",
        step: "starting",
        ui_step: 0,
        progress: 0,
        device: state.computeDevice,
        current_document_id: null,
        current_document_title: "",
        current_index: 0,
        total_documents: period.thesis.length,
        message: `Iniciando analisis en ${deviceLabel(state.computeDevice)}.`
      };
      renderAll();
      await apiRequest(
        `/periods/${period.id}/analysis/run?background=true&device=${encodeURIComponent(state.computeDevice)}`,
        { method: "POST" }
      );
      startAnalysisProgressPolling(period.id);
      return;
    } catch (error) {
      state.running = false;
      state.activeStep = -1;
      state.analysisProgress = null;
      state.apiReady = false;
    }
  }
  renderAll();
}

document.addEventListener("DOMContentLoaded", () => {
  renderAll();
  hydrateFromApi();

  $("#periodSelect").addEventListener("change", (event) => setPeriod(event.target.value));
  $("#computeDevice").addEventListener("change", (event) => {
    state.computeDevice = event.target.value;
    renderRuntimeState();
  });

  $("#heatmap").addEventListener("click", (event) => {
    const button = event.target.closest(".heatmap-cell:not(.blank)");
    if (!button) return;
    state.selectedCell = {
      courseIndex: Number(button.dataset.row),
      criterionIndex: Number(button.dataset.col)
    };
    renderHeatmap();
    renderCellDetail();
  });

  $("#cellDetail").addEventListener("click", (event) => {
    const button = event.target.closest(".toggle-general-comment");
    if (!button) return;
    const key = button.dataset.detailKey;
    state.expandedComments[key] = !state.expandedComments[key];
    renderCellDetail();
  });

  $(".nav-list").addEventListener("click", (event) => {
    const button = event.target.closest(".nav-item");
    if (!button) return;
    setView(button.dataset.view);
  });

  $("#groupFilter").addEventListener("click", (event) => {
    const button = event.target.closest(".group-chip");
    if (!button) return;
    state.currentGroup = decodeURIComponent(button.dataset.group);
    state.selectedCell = firstTributedCell(state.currentGroup);
    renderAll();
  });

  $("#periodList").addEventListener("click", (event) => {
    const button = event.target.closest(".period-item");
    if (!button) return;
    setPeriod(button.dataset.period);
  });

  $("#fileInput").addEventListener("change", (event) => {
    addFiles(event.target.files);
    event.target.value = "";
  });

  const uploadBox = $("#uploadBox");
  ["dragenter", "dragover"].forEach((eventName) => {
    uploadBox.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      uploadBox.classList.add("drag-over");
    });
  });

  ["dragleave", "drop"].forEach((eventName) => {
    uploadBox.addEventListener(eventName, (event) => {
      event.preventDefault();
      event.stopPropagation();
      uploadBox.classList.remove("drag-over");
    });
  });

  uploadBox.addEventListener("drop", (event) => {
    addFiles(event.dataTransfer.files);
  });

  $("#newPeriodForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    await createPeriod($("#newPeriodName").value);
    $("#newPeriodName").value = "";
  });

  $("#thesisTable").addEventListener("click", async (event) => {
    const button = event.target.closest(".delete-thesis");
    if (!button) return;
    const period = currentPeriod();
    const documentId = button.dataset.documentId;
    if (state.apiReady && documentId) {
      try {
        await apiRequest(`/documents/${documentId}`, { method: "DELETE" });
        const apiPeriods = await apiRequest("/periods");
        periods = apiPeriods.map(normalizePeriodFromApi);
        await refreshApiAnalysis();
        renderAll();
        return;
      } catch (error) {
        state.apiReady = false;
      }
    }
    period.thesis.splice(Number(button.dataset.index), 1);
    markPeriodChanged(period);
    renderAll();
  });

  $("#criterionFilter").addEventListener("change", (event) => {
    state.criterionFilter = event.target.value;
    renderEvidence();
  });

  $("#runAnalysis").addEventListener("click", simulateAnalysis);

  $("#exportExcel")?.addEventListener("click", () => {
    const period = currentPeriod();
    if (!period) return;
    const url = `${API_BASE_URL}/reports/excel?period_id=${encodeURIComponent(period.id)}`;
    window.open(url, "_blank");
  });
});


