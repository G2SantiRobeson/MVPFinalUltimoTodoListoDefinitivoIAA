let competencies = [];
let curriculumCourses = [];
let competencyGroupNames = [];
let curricula = [];
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
  selectedOverviewCompetencyIndex: null,
  currentGroup: "all",
  criterionFilter: "all",
  running: false,
  activeStep: -1,
  apiReady: false,
  analysisScores: {},
  analysisMetrics: {},
  apiEvidence: [],
  currentCurriculumId: null,
  newPeriodCurriculumId: null,
  cellDetails: {},
  expandedOverviewCourses: {},
  expandedComments: {},
  expandedFragments: {},
  loadingCellDetail: null,
  analysisProgress: null,
  progressTimer: null,
  lastProgressSignature: ""
};

const API_BASE_URL = "http://localhost:8000/api/v1";
const DEMO_TOKEN = "demo-academic-admin";
const ACCEPTED_FILE_EXTENSIONS = [".pdf", ".docx", ".txt"];
const ACCEPTED_MATRIX_EXTENSIONS = [".xlsx"];
const HIDDEN_GROUP_FILTERS = new Set(["Universidad", "UNIVERSIDAD"]);
const HIDDEN_HEATMAP_COMPETENCY_CODES = new Set(["U1", "U2", "U3", "U4"]);
const COMPETENCY_OVERVIEW_GROUP_ORDER = ["LIC", "TIC", "TCC"];
const HEATMAP_DRAG_THRESHOLD = 5;
const heatmapDrag = {
  active: false,
  moved: false,
  pointerId: null,
  startX: 0,
  startY: 0,
  scrollLeft: 0,
  scrollTop: 0,
  suppressClick: false
};

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

function normalizeCurriculumFromApi(curriculum) {
  return {
    ...curriculum,
    display_name: curriculum.display_name || curriculum.version || "Matriz sin nombre",
    program: curriculum.program || "Carrera no especificada"
  };
}

function acceptedThesisFiles(files) {
  return Array.from(files).filter((file) => {
    const name = file.name.toLowerCase();
    return ACCEPTED_FILE_EXTENSIONS.some((extension) => name.endsWith(extension));
  });
}

function acceptedMatrixFiles(files) {
  return Array.from(files).filter((file) => {
    const name = file.name.toLowerCase();
    return ACCEPTED_MATRIX_EXTENSIONS.some((extension) => name.endsWith(extension));
  });
}

function curriculumLabel(curriculum) {
  if (!curriculum) return "Sin matriz";
  const year = curriculum.year ? ` · ${curriculum.year}` : "";
  return `${curriculum.display_name}${year} · ${curriculum.program}`;
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

function openEvidenceCell(courseId, competencyCode) {
  const courseIndex = curriculumCourses.findIndex((course) => course.db_id === courseId);
  const criterionIndex = competencies.findIndex((competency) => competency.id === competencyCode);
  if (courseIndex < 0 || criterionIndex < 0 || !isTributed(courseIndex, criterionIndex)) return;

  state.currentGroup = "all";
  state.selectedCell = { courseIndex, criterionIndex };
  state.selectedOverviewCompetencyIndex = null;
  setView("dashboard");
  renderAll();
  requestAnimationFrame(() => {
    const selectedButton = $("#heatmap .heatmap-cell.selected");
    if (!selectedButton) return;
    selectedButton.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
    selectedButton.focus();
  });
}

async function hydrateFromApi() {
  try {
    await apiRequest("/health");
    const [apiCurricula, apiPeriods] = await Promise.all([
      apiRequest("/curricula"),
      apiRequest("/periods")
    ]);

    curricula = apiCurricula.map(normalizeCurriculumFromApi);
    periods = apiPeriods.map(normalizePeriodFromApi);
    state.apiReady = true;
    state.currentPeriodId = periods[0]?.id || null;
    await loadMatrixForCurrentPeriod();
    state.selectedOverviewCompetencyIndex = null;
    await refreshApiAnalysis();
    renderAll();
  } catch (error) {
    state.apiReady = false;
    state.currentPeriodId = null;
    state.currentCurriculumId = null;
    state.selectedCell = null;
    state.selectedOverviewCompetencyIndex = null;
    renderAll();
  }
}

async function loadMatrixForCurrentPeriod() {
  const period = currentPeriod();
  const curriculumId = period?.curriculum_id || curricula[0]?.id || null;
  if (!curriculumId) {
    competencies = [];
    curriculumCourses = [];
    competencyGroupNames = [];
    state.currentCurriculumId = null;
    state.selectedCell = null;
    return;
  }

  if (state.currentCurriculumId === curriculumId && competencies.length) {
    return;
  }

  const matrix = await apiRequest(`/curricula/${encodeURIComponent(curriculumId)}/matrix`);
  competencies = matrix.competencies;
  curriculumCourses = matrix.courses;
  competencyGroupNames = [...new Set(competencies.map((competency) => competency.group))];
  state.currentCurriculumId = matrix.curriculum_id;
  state.selectedCell = firstTributedCell();
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
    state.analysisMetrics[state.currentPeriodId] = analysis.metrics || {};
    await refreshApiEvidence();
    state.cellDetails = {};
    state.expandedComments = {};
    state.expandedFragments = {};
  } catch (error) {
    state.analysisScores[state.currentPeriodId] = {};
    state.analysisMetrics[state.currentPeriodId] = {};
    state.apiEvidence = [];
    state.cellDetails = {};
    state.expandedComments = {};
    state.expandedFragments = {};
  }
}

async function refreshApiEvidence() {
  if (!state.apiReady || !state.currentPeriodId) {
    state.apiEvidence = [];
    return;
  }

  const competencyCode = selectedCompetencyCode(state.criterionFilter);
  const competencyQuery = competencyCode ? `&competency_code=${encodeURIComponent(competencyCode)}` : "";
  try {
    state.apiEvidence = await apiRequest(
      `/evidence?period_id=${state.currentPeriodId}&limit=50${competencyQuery}`
    );
  } catch (_error) {
    state.apiEvidence = [];
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
    .filter(({ competency }) => !HIDDEN_HEATMAP_COMPETENCY_CODES.has(competency.id.toUpperCase()))
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

function competencyAverageItems(period = currentPeriod(), groupName = state.currentGroup) {
  const visibleIndexes = visibleCompetencyIndexesFor(groupName);

  return visibleIndexes.map((criterionIndex) => {
    const competency = competencies[criterionIndex];
    const scores = [];
    let totalTributed = 0;

    curriculumCourses.forEach((_course, courseIndex) => {
      if (!isTributed(courseIndex, criterionIndex)) return;
      totalTributed += 1;
      const score = scoreFor(courseIndex, criterionIndex, period);
      if (score !== null) scores.push(score);
    });

    const average = scores.length
      ? Math.round(scores.reduce((sum, value) => sum + value, 0) / scores.length)
      : null;

    return {
      criterionIndex,
      competency,
      average,
      evaluated: scores.length,
      totalTributed
    };
  });
}

function competencyCodePrefix(code) {
  const match = String(code || "").toUpperCase().match(/^[A-Z]+/);
  return match ? match[0] : "OTRAS";
}

function groupedCompetencyAverageItems(items) {
  const groups = new Map();
  items.forEach((item) => {
    const prefix = competencyCodePrefix(item.competency.id);
    if (!groups.has(prefix)) groups.set(prefix, []);
    groups.get(prefix).push(item);
  });

  return [...groups.entries()]
    .map(([prefix, groupItems]) => {
      const scoredItems = groupItems.filter((item) => item.average !== null);
      return {
        prefix,
        items: groupItems,
        average: scoredItems.length
          ? Math.round(scoredItems.reduce((sum, item) => sum + item.average, 0) / scoredItems.length)
          : null
      };
    })
    .sort((a, b) => {
      const indexA = COMPETENCY_OVERVIEW_GROUP_ORDER.indexOf(a.prefix);
      const indexB = COMPETENCY_OVERVIEW_GROUP_ORDER.indexOf(b.prefix);
      if (indexA >= 0 && indexB >= 0) return indexA - indexB;
      if (indexA >= 0) return -1;
      if (indexB >= 0) return 1;
      return a.prefix.localeCompare(b.prefix);
    });
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

function bindHeatmapDrag() {
  const wrap = $("#heatmapWrap");
  if (!wrap) return;

  wrap.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    heatmapDrag.active = true;
    heatmapDrag.moved = false;
    heatmapDrag.pointerId = event.pointerId;
    heatmapDrag.startX = event.clientX;
    heatmapDrag.startY = event.clientY;
    heatmapDrag.scrollLeft = wrap.scrollLeft;
    heatmapDrag.scrollTop = wrap.scrollTop;
  });

  wrap.addEventListener("pointermove", (event) => {
    if (!heatmapDrag.active || heatmapDrag.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - heatmapDrag.startX;
    const deltaY = event.clientY - heatmapDrag.startY;
    if (!heatmapDrag.moved && (Math.abs(deltaX) > HEATMAP_DRAG_THRESHOLD || Math.abs(deltaY) > HEATMAP_DRAG_THRESHOLD)) {
      heatmapDrag.moved = true;
      wrap.classList.add("dragging");
      wrap.setPointerCapture?.(event.pointerId);
    }
    if (!heatmapDrag.moved) return;
    event.preventDefault();
    wrap.scrollLeft = heatmapDrag.scrollLeft - deltaX;
    wrap.scrollTop = heatmapDrag.scrollTop - deltaY;
  });

  const finishDrag = (event) => {
    if (!heatmapDrag.active || heatmapDrag.pointerId !== event.pointerId) return;
    heatmapDrag.active = false;
    heatmapDrag.pointerId = null;
    wrap.classList.remove("dragging");
    if (wrap.hasPointerCapture?.(event.pointerId)) {
      wrap.releasePointerCapture(event.pointerId);
    }
    if (heatmapDrag.moved) {
      heatmapDrag.suppressClick = true;
      window.setTimeout(() => {
        heatmapDrag.suppressClick = false;
      }, 80);
    }
  };

  wrap.addEventListener("pointerup", finishDrag);
  wrap.addEventListener("pointercancel", finishDrag);
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
    .map((period) => {
      const suffix = period.program ? ` · ${period.program}` : "";
      return `<option value="${escapeHtml(period.id)}">${escapeHtml(period.name)}${escapeHtml(suffix)}</option>`;
    })
    .join("");
  select.value = state.currentPeriodId || periods[0].id;
}

function renderCurriculumControls() {
  const periodSelect = $("#periodCurriculumSelect");
  const list = $("#curriculumList");
  if (periodSelect) {
    periodSelect.innerHTML = curricula.length
      ? curricula
        .map((curriculum) => `
          <option value="${escapeHtml(curriculum.id)}">${escapeHtml(curriculumLabel(curriculum))}</option>
        `)
        .join("")
      : `<option value="">Sin matrices cargadas</option>`;
    periodSelect.disabled = !curricula.length;
    const selectedCurriculumId =
      state.newPeriodCurriculumId || currentPeriod()?.curriculum_id || curricula[0]?.id || "";
    if (selectedCurriculumId) {
      periodSelect.value = selectedCurriculumId;
    }
  }

  if (!list) return;
  list.innerHTML = curricula.length
    ? curricula
      .map((curriculum) => `
        <article class="curriculum-item ${curriculum.id === state.currentCurriculumId ? "active" : ""}">
          <div>
            <strong>${escapeHtml(curriculum.display_name)}</strong>
            <span>${escapeHtml(curriculum.program)}${curriculum.year ? ` · ${curriculum.year}` : ""}</span>
          </div>
          <small>${escapeHtml(curriculum.source_filename || curriculum.version)}</small>
        </article>
      `)
      .join("")
    : `<div class="detail-empty">No hay matrices cargadas.</div>`;
}

function renderSummary() {
  const period = currentPeriod();
  const currentGroupLabel = state.currentGroup === "all" ? "Toda la matriz" : state.currentGroup;
  const visibleCompetencies = visibleCompetencyIndexes();
  const visibleCourses = visibleCourseIndexes();
  const visibleTributated = groupTributatedCount(state.currentGroup);
  const metrics = state.apiReady ? (state.analysisMetrics[state.currentPeriodId] || {}) : {};
  const hasMetrics = metrics.evaluated_cells > 0;

  let cards;
  if (hasMetrics) {
    const coverageColor = metrics.coverage_rate >= 70 ? "var(--green)" : metrics.coverage_rate >= 40 ? "var(--amber)" : "var(--coral)";
    cards = [
      ["Cobertura del período", `${metrics.coverage_rate ?? 0}%`, "Celdas tributadas cuyo resultado alcanza el umbral de evidencia.", coverageColor],
      ["Evidencia alta", metrics.high ?? 0, "Celdas con score ≥ 75% (cumplimiento fuerte).", "var(--green)"],
      ["Brechas detectadas", metrics.gaps ?? 0, "Celdas con evidencia bajo el umbral esperado (< 55%).", "var(--coral)"]
    ];
  } else {
    cards = [
      ["Tesis analizadas", period?.metrics?.thesis ?? 0, period ? `${period.thesis.length} registradas` : "Sin periodo seleccionado", "var(--teal)"],
      ["Bloque visible", currentGroupLabel, `${visibleCompetencies.length} competencias en la vista`, "var(--blue)"],
      ["Ramos visibles", visibleCourses.length, `${visibleTributated} cruces ramo-competencia con X`, "var(--muted)"]
    ];
  }

  $("#summaryGrid").innerHTML = cards
    .map(
      ([label, value, detail, color]) => `
        <article class="metric-card" style="border-top: 3px solid ${color}">
          <span>${label}</span>
          <strong>${value}</strong>
          <p>${detail}</p>
        </article>
      `
    )
    .join("");
}

function renderCompetencyOverview() {
  const overview = $("#competencyOverview");
  if (!overview) return;

  const period = currentPeriod();
  const items = competencyAverageItems(period, "all");

  if (!period || !items.length) {
    overview.innerHTML = `<div class="compact-empty">No hay competencias visibles para resumir.</div>`;
    return;
  }

  const hasScores = items.some((item) => item.average !== null);
  if (!hasScores) {
    overview.innerHTML = `<div class="compact-empty">Ejecuta el analisis para ver promedios por competencia.</div>`;
    return;
  }

  overview.innerHTML = groupedCompetencyAverageItems(items)
    .map((group) => {
      const groupAverage = group.average !== null ? `${group.average}% promedio` : "Sin promedio";
      const cells = group.items.map((item) => {
        const average = item.average;
        const hasAverage = average !== null;
        const color = hasAverage ? cellColor(average) : "";
        const level = hasAverage ? scoreClass(average) : "pending";
        const label = hasAverage ? scoreLabel(average) : "Pendiente";
        const selected = state.selectedOverviewCompetencyIndex === item.criterionIndex;

        return `
          <button
            class="competency-average-cell ${level} ${selected ? "selected" : ""}"
            ${hasAverage ? `style="background:${color}"` : ""}
            data-col="${item.criterionIndex}"
            title="${escapeHtml(item.competency.name)} - ${label} - ${item.evaluated}/${item.totalTributed} celdas"
            type="button"
            role="gridcell"
            aria-pressed="${selected}"
            aria-label="${escapeHtml(item.competency.id)}, ${hasAverage ? `${average}%` : "pendiente"}"
          >
            <strong>${escapeHtml(item.competency.id)}</strong>
            <span>${hasAverage ? `${average}%` : "Pend."}</span>
            <small>${item.evaluated}/${item.totalTributed}</small>
          </button>
        `;
      }).join("");

      return `
        <section class="competency-average-row" aria-label="Competencias ${escapeHtml(group.prefix)}">
          <div class="competency-average-row-label">
            <strong>${escapeHtml(group.prefix)}</strong>
            <span>${groupAverage}</span>
            <small>${group.items.length} competencia${group.items.length !== 1 ? "s" : ""}</small>
          </div>
          <div class="competency-average-cells" role="grid">
            ${cells}
          </div>
        </section>
      `;
    })
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
    if (selected && selected.courseIndex === courseIndex && selected.criterionIndex === criterionIndex) {
      renderCellDetail();
    }
  }
}

function renderCompetencyOverviewDetail() {
  const detail = $("#competencyOverviewDetail");
  if (!detail) return;

  const criterionIndex = state.selectedOverviewCompetencyIndex;

  if (criterionIndex === null) {
    detail.className = "overview-detail-empty";
    detail.innerHTML = "Selecciona una competencia para ver su definici&oacute;n.";
    return;
  }

  const competency = competencies[criterionIndex];
  if (!competency) {
    detail.className = "overview-detail-empty";
    detail.innerHTML = "No hay definici&oacute;n disponible para esta competencia.";
    return;
  }

  const item = competencyAverageItems(currentPeriod(), "all")
    .find((candidate) => candidate.criterionIndex === criterionIndex);
  const average = item?.average ?? null;
  const levelClass = average === null ? "mid" : scoreClass(average);
  const label = average === null ? "Sin promedio" : scoreLabel(average);
  const linkedCourses = curriculumCourses.filter((_course, courseIndex) => isTributed(courseIndex, criterionIndex));
  const coursesExpanded = Boolean(state.expandedOverviewCourses[criterionIndex]);
  const visibleCourses = coursesExpanded ? linkedCourses : linkedCourses.slice(0, 8);
  const hiddenCourseCount = Math.max(linkedCourses.length - visibleCourses.length, 0);
  const summary = average === null
    ? "Todav&iacute;a no hay resultados evaluados para calcular el promedio de esta competencia."
    : `${label}: promedio calculado desde ${item.evaluated}/${item.totalTributed} celdas curso-competencia tributadas.`;

  detail.className = "overview-detail-content";
  detail.innerHTML = `
    <div class="score-line">
      <div>
        <span class="eyebrow">Definici&oacute;n de competencia</span>
        <h3>${escapeHtml(competency.id)} &middot; ${escapeHtml(competency.group)}</h3>
      </div>
      <span class="score-badge ${levelClass}">${average === null ? "Pend." : `${average}%`}</span>
    </div>

    <div class="quote-box">
      <strong>Definici&oacute;n</strong>
      <p>${escapeHtml(competency.name)}</p>
    </div>

    <div class="quote-box">
      <strong>Promedio agregado</strong>
      <p>${summary}</p>
    </div>

    <div class="quote-box">
      <strong>Ramos tributados</strong>
      <div class="definition-course-list">
        ${visibleCourses.map((course) => `
          <span title="${escapeHtml(course.title)}">
            ${escapeHtml(course.code || "S/C")} &middot; ${escapeHtml(course.title)}
          </span>
        `).join("")}
        ${linkedCourses.length > 8 ? `
          <button class="definition-course-toggle" type="button" aria-expanded="${coursesExpanded}">
            ${coursesExpanded ? "Ver menos" : `+${hiddenCourseCount} ramos m&aacute;s`}
          </button>
        ` : ""}
      </div>
    </div>
  `;
}

function renderCellDetail() {
  const detailTitle = $("#detailTitle");
  if (detailTitle) detailTitle.innerHTML = "Justificaci&oacute;n de celda";

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

  const fragments = aiDetail?.evidence_fragments || [];
  const fragmentsExpanded = Boolean(state.expandedFragments[detailKey]);
  const showAllFragments = fragmentsExpanded || fragments.length <= 1;
  const visibleFragments = showAllFragments ? fragments : fragments.slice(0, 1);

  const fragmentsHtml = fragments.length > 0
    ? `
      <div class="quote-box evidence-fragments-box">
        <strong>Evidencia textual (${fragments.length} fragmento${fragments.length > 1 ? "s" : ""} recuperado${fragments.length > 1 ? "s" : ""})</strong>
        ${visibleFragments.map((frag, i) => `
          <div class="evidence-fragment ${frag.verdict === 'supporting' ? 'supporting' : 'candidate'}">
            <div class="fragment-meta">
              <span class="fragment-origin">${escapeHtml(frag.origin)}${frag.page ? ` · Pág. ${frag.page}` : ""}</span>
              <span class="fragment-confidence ${frag.confidence >= 60 ? 'conf-high' : frag.confidence >= 35 ? 'conf-mid' : 'conf-low'}">${frag.confidence}% confianza</span>
            </div>
            <p class="fragment-text">${escapeHtml(frag.text)}</p>
          </div>
        `).join("")}
        ${fragments.length > 1 ? `
          <button class="text-toggle toggle-fragments" type="button" data-detail-key="${escapeHtml(detailKey)}">
            ${showAllFragments ? "Ver menos" : `Ver ${fragments.length - 1} fragmento${fragments.length - 1 > 1 ? "s" : ""} más`}
          </button>
        ` : ""}
      </div>
    `
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

          ${fragmentsHtml}

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
            ${period.program ? `<span>${escapeHtml(period.program)}</span>` : ""}
            ${period.curriculum_name ? `<span>${escapeHtml(period.curriculum_name)}</span>` : ""}
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
  const summary = $("#evidenceResultsSummary");
  const availableCompetencies = visibleEvidenceCompetencies();
  const validFilters = new Set(["all", ...availableCompetencies.map(competencyFilterValue)]);
  if (!validFilters.has(state.criterionFilter)) {
    state.criterionFilter = "all";
  }

  const filter = state.criterionFilter;
  const filterCode = selectedCompetencyCode(filter);
  const usefulCriterionOptions = [
    `<option value="all">Todas las competencias</option>`,
    ...availableCompetencies.map(
      (competency) => `<option value="${competencyFilterValue(competency)}">${competency.id} · ${competency.group}</option>`
    )
  ];
  $("#criterionFilter").innerHTML = usefulCriterionOptions.join("");
  $("#criterionFilter").value = filter;

  if (!state.apiReady || !currentPeriod()) {
    if (summary) summary.textContent = "";
    $("#evidenceList").innerHTML = `<article class="evidence-item"><p>No hay evidencia cargada desde el backend.</p></article>`;
    return;
  }

  if (state.apiReady) {
    const apiItems = state.apiEvidence.filter((item) => {
      if (isHiddenGroup(item.competency_group)) return false;
      if (!filterCode) return true;
      return item.competency_code === filterCode;
    });
    const displayedItems = apiItems.slice(0, 25);
    if (summary) {
      const scope = filterCode ? ` para ${filterCode}` : " destacadas del período";
      summary.textContent = displayedItems.length
        ? `Mostrando ${displayedItems.length} evidencias${scope}. Selecciona un cruce para ver su celda y justificación.`
        : `No se encontraron evidencias${scope}.`;
    }

    const confidenceClass = (conf) => {
      const pct = Math.round((conf || 0) * 100);
      if (pct >= 60) return "conf-high";
      if (pct >= 35) return "conf-mid";
      return "conf-low";
    };

    $("#evidenceList").innerHTML =
      displayedItems
        .map(
          (item) => {
            const confPct = Math.round((item.confidence || 0) * 100);
            const sourceTitle = item.source_document_title || item.document_title || "Documento sin título";
            const relatedCells = item.related_cells?.length
              ? item.related_cells
              : item.course_id
                ? [{
                    course_id: item.course_id,
                    course_code: item.course_code,
                    course_title: item.course_title
                  }]
                : [];
            const isGrouped = item.occurrence_count > 1;
            const hasManyCrossings = relatedCells.length > 6;
            const verdictLabel = item.verdict === "supporting" ? "Evidencia suficiente" : "Candidato para revisión";
            const reviewScore = item.manual_score ?? item.effective_score ?? confPct;
            const reviewedMeta = item.reviewed_at ? `<span>Revisada manualmente</span>` : "";
            return `
              <article class="evidence-item ${isGrouped ? "grouped" : ""}">
                <div class="evidence-header">
                  <div class="evidence-title">
                    <span class="evidence-tag">${escapeHtml(item.competency_code)}</span>
                    <h3>${escapeHtml(sourceTitle)}</h3>
                  </div>
                  <div class="evidence-status">
                    <span class="evidence-verdict ${item.verdict === "supporting" ? "supporting" : "candidate"}">${verdictLabel}</span>
                    <span class="evidence-badge ${confidenceClass(item.confidence)}">${confPct}% confianza</span>
                  </div>
                </div>
                <div class="evidence-meta">
                  <span>Documento de origen</span>
                  ${item.page ? `<span>Pág. ${escapeHtml(String(item.page))}</span>` : ""}
                  <span>${isGrouped ? `${item.occurrence_count} cruces asociados` : "1 cruce asociado"}</span>
                  ${reviewedMeta}
                </div>
                <p class="evidence-text">${escapeHtml(item.text)}</p>
                <form class="evidence-review-form" data-evidence-id="${escapeHtml(item.id)}">
                  <label>
                    <span>Puntaje</span>
                    <input name="manual_score" type="number" min="0" max="100" step="1" value="${escapeHtml(String(reviewScore))}" />
                  </label>
                  <label class="review-observation">
                    <span>Observaci&oacute;n</span>
                    <input name="manual_observation" type="text" maxlength="1000" value="${escapeHtml(item.manual_observation || "")}" placeholder="Comentario breve" />
                  </label>
                  <button class="secondary-button compact-action" type="submit">
                    <i data-lucide="save"></i>
                    <span>Guardar opini&oacute;n</span>
                  </button>
                </form>
                <div class="evidence-crossings">
                  <span class="evidence-crossings-label">${isGrouped ? "Cruces asociados" : "Cruce asociado"} · abrir en el mapa de calor</span>
                  <div class="evidence-crossing-actions ${hasManyCrossings ? "is-scrollable" : ""}">
                    ${relatedCells.map((cell) => `
                      <button
                        class="evidence-cell-link"
                        type="button"
                        data-course-id="${escapeHtml(cell.course_id)}"
                        data-competency-code="${escapeHtml(item.competency_code)}"
                        title="Abrir celda ${escapeHtml(cell.course_code)} - ${escapeHtml(item.competency_code)}"
                      >
                        <strong>${escapeHtml(cell.course_code || "S/C")}</strong>
                        <span>${escapeHtml(cell.course_title || "Ramo sin nombre")}</span>
                        <small>Ver celda</small>
                      </button>
                    `).join("")}
                  </div>
                </div>
              </article>
            `;
          }
        )
        .join("") || `<article class="evidence-item"><p>No hay evidencia real procesada para este filtro.</p></article>`;
    return;
  }
}

function renderKpis() {
  const period = currentPeriod();
  const metrics = state.apiReady ? (state.analysisMetrics[state.currentPeriodId] || {}) : {};
  const hasMetrics = (metrics.evaluated_cells || 0) > 0;

  // ── 4 KPI summary cards ──
  const kpiSummaryGrid = $("#kpiSummaryGrid");
  if (kpiSummaryGrid) {
    if (!period) {
      kpiSummaryGrid.innerHTML = `<article class="kpi-summary-card"><p>No hay período seleccionado.</p></article>`;
    } else {
      const summaryCards = [
        {
          icon: "shield-check",
          label: "Cobertura del período",
          value: hasMetrics ? `${metrics.coverage_rate ?? 0}%` : "Sin datos",
          desc: "Celdas tributadas cuyo resultado alcanza el umbral de evidencia.",
          color: hasMetrics ? (metrics.coverage_rate >= 70 ? "kpi-green" : metrics.coverage_rate >= 40 ? "kpi-amber" : "kpi-red") : "kpi-muted"
        },
        {
          icon: "alert-triangle",
          label: "Brechas detectadas",
          value: hasMetrics ? (metrics.gaps ?? 0) : "Sin datos",
          desc: "Celdas con score menor al 55%, que requieren atención curricular prioritaria.",
          color: hasMetrics ? (metrics.gaps === 0 ? "kpi-green" : metrics.gaps <= 3 ? "kpi-amber" : "kpi-red") : "kpi-muted"
        },
        {
          icon: "trending-up",
          label: "Celdas con evidencia alta",
          value: hasMetrics ? (metrics.high ?? 0) : "Sin datos",
          desc: "Celdas con score ≥ 75%: demuestran cumplimiento sólido del criterio.",
          color: hasMetrics ? (metrics.high > 0 ? "kpi-green" : "kpi-muted") : "kpi-muted"
        }
      ];
      kpiSummaryGrid.innerHTML = summaryCards.map(c => `
        <article class="kpi-summary-card ${c.color}">
          <div class="kpi-card-icon"><i data-lucide="${c.icon}"></i></div>
          <div>
            <span class="kpi-card-label">${c.label}</span>
            <strong class="kpi-card-value">${c.value}</strong>
            <p class="kpi-card-desc">${c.desc}</p>
          </div>
        </article>
      `).join("");
    }
  }

  // ── Distribution bars ──
  const kpiBarsEl = $("#kpiBars");
  if (kpiBarsEl) {
    if (!hasMetrics) {
      kpiBarsEl.innerHTML = `<p style="color:var(--muted);font-size:.9rem">Ejecuta el análisis para ver la distribución de evidencia.</p>`;
    } else {
      const total = metrics.evaluated_cells || 1;
      const bars = [
        { label: "Evidencia alta (≥ 75%)", value: metrics.high ?? 0, total, color: "var(--green)", icon: "✓" },
        { label: "Evidencia media (55–74%)", value: metrics.medium ?? 0, total, color: "var(--amber)", icon: "~" },
        { label: "Evidencia baja / brecha (< 55%)", value: metrics.low ?? 0, total, color: "var(--coral)", icon: "!" },
      ];
      kpiBarsEl.innerHTML = bars.map(b => {
        const pct = Math.round((b.value / total) * 100);
        return `
          <article class="kpi-bar">
            <div class="kpi-row">
              <span>${b.icon} ${b.label}</span>
              <strong>${b.value} <small style="font-weight:500;color:var(--muted)">(${pct}%)</small></strong>
            </div>
            <div class="bar-track" aria-hidden="true">
              <div class="bar-fill" style="width:${pct}%;background:${b.color}"></div>
            </div>
          </article>
        `;
      }).join("");
    }
  }

  // ── Top gaps table ──
  const topGapsEl = $("#topGapsTable");
  if (topGapsEl) {
    const gaps = metrics.top_gaps || [];
    if (!hasMetrics || !gaps.length) {
      topGapsEl.innerHTML = `<p style="color:var(--muted);font-size:.9rem">No hay brechas calculadas para este período.</p>`;
    } else {
      topGapsEl.innerHTML = `
        <div class="gaps-table">
          <div class="gaps-header">
            <span>Ramo</span><span>Competencia</span><span>Score</span><span>Fragmentos</span>
          </div>
          ${gaps.map(g => `
            <div class="gaps-row">
              <span class="gaps-course" title="${escapeHtml(g.course_title)}">
                <strong>${escapeHtml(g.course_code)}</strong>
                <small>${escapeHtml(g.course_title)}</small>
              </span>
              <span class="gaps-comp">
                <strong>${escapeHtml(g.competency_code)}</strong>
                <small>${escapeHtml(g.competency_group)}</small>
              </span>
              <span class="score-badge ${g.score >= 55 ? "mid" : "low"}">${g.score}%</span>
              <span style="color:var(--muted);font-size:.82rem">${g.evidence_count} fragmento${g.evidence_count !== 1 ? 's' : ''} con evidencia suficiente</span>
            </div>
          `).join("")}
        </div>
      `;
    }
  }

  // ── Competency coverage list ──
  const compCoverageEl = $("#competencyCoverageList");
  if (compCoverageEl) {
    const coverageList = metrics.competency_coverage || [];
    if (!hasMetrics || !coverageList.length) {
      compCoverageEl.innerHTML = `<p style="color:var(--muted);font-size:.9rem">No hay datos de cobertura calculados para este período.</p>`;
    } else {
      compCoverageEl.innerHTML = coverageList.map(c => {
        const color = c.coverage_pct >= 70 ? "var(--green)" : c.coverage_pct >= 40 ? "var(--amber)" : "var(--coral)";
        return `
          <div class="comp-coverage-row">
            <div class="comp-coverage-header">
              <div>
                <strong>${escapeHtml(c.code)}</strong>
                <small>${escapeHtml(c.group)}</small>
              </div>
              <span class="comp-coverage-pct" style="color:${color}">${c.coverage_pct}%</span>
            </div>
            <div class="bar-track" aria-hidden="true" style="height:7px">
              <div class="bar-fill" style="width:${c.coverage_pct}%;background:${color};transition:width .4s ease"></div>
            </div>
            <div class="comp-coverage-meta">
              <span>${c.cells_with_evidence}/${c.total_cells} cursos con evidencia suficiente</span>
              ${c.avg_score !== null ? `<span>Score promedio: ${c.avg_score}%</span>` : ""}
            </div>
          </div>
        `;
      }).join("");
    }
  }
}

function renderAll() {
  renderRuntimeState();
  renderPeriodOptions();
  renderCurriculumControls();
  renderSummary();
  renderCompetencyOverview();
  renderCompetencyOverviewDetail();
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
  await loadMatrixForCurrentPeriod();
  state.selectedOverviewCompetencyIndex = null;
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

async function uploadMatrix(files) {
  const selectedFiles = acceptedMatrixFiles(files);
  const file = selectedFiles[0];
  const displayName = $("#matrixDisplayName")?.value.trim() || "";
  const program = $("#matrixProgram")?.value.trim() || "";
  const yearValue = $("#matrixYear")?.value.trim() || "";
  if (!file || !displayName || !program || !state.apiReady) return;

  const form = new FormData();
  form.set("display_name", displayName);
  form.set("program", program);
  if (yearValue) form.set("year", yearValue);
  form.set("file", file);

  const created = await apiRequest("/curricula", {
    method: "POST",
    body: form
  });

  const apiCurricula = await apiRequest("/curricula");
  curricula = apiCurricula.map(normalizeCurriculumFromApi);
  const select = $("#periodCurriculumSelect");
  state.newPeriodCurriculumId = created.id;
  if (select) select.value = created.id;
  $("#matrixUploadForm")?.reset();
  renderAll();
}

async function createPeriod(name) {
  const clean = name.trim();
  if (!clean) return;
  const curriculumId = $("#periodCurriculumSelect")?.value || curricula[0]?.id || "";
  if (!curriculumId) return;

  if (state.apiReady) {
    try {
      const created = await apiRequest("/periods", {
        method: "POST",
        body: JSON.stringify({ name: clean, curriculum_id: curriculumId })
      });
      const apiPeriods = await apiRequest("/periods");
      periods = apiPeriods.map(normalizePeriodFromApi);
      state.currentPeriodId = created.id;
      state.newPeriodCurriculumId = curriculumId;
      await loadMatrixForCurrentPeriod();
      state.selectedOverviewCompetencyIndex = null;
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
        device: "cuda",
        current_document_id: null,
        current_document_title: "",
        current_index: 0,
        total_documents: period.thesis.length,
        message: "Iniciando analisis."
      };
      renderAll();
      await apiRequest(
        `/periods/${period.id}/analysis/run?background=true`,
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
  bindHeatmapDrag();

  $("#periodSelect").addEventListener("change", (event) => setPeriod(event.target.value));
  $("#heatmap").addEventListener("click", (event) => {
    if (heatmapDrag.suppressClick) {
      event.preventDefault();
      event.stopPropagation();
      heatmapDrag.suppressClick = false;
      return;
    }
    const button = event.target.closest(".heatmap-cell:not(.blank)");
    if (!button) return;
    state.selectedCell = {
      courseIndex: Number(button.dataset.row),
      criterionIndex: Number(button.dataset.col)
    };
    renderHeatmap();
    renderCellDetail();
  });

  $("#competencyOverview").addEventListener("click", (event) => {
    const button = event.target.closest(".competency-average-cell");
    if (!button) return;
    state.selectedOverviewCompetencyIndex = Number(button.dataset.col);
    renderCompetencyOverview();
    renderCompetencyOverviewDetail();
  });

  $("#competencyOverviewDetail").addEventListener("click", (event) => {
    const button = event.target.closest(".definition-course-toggle");
    if (!button || state.selectedOverviewCompetencyIndex === null) return;
    const key = state.selectedOverviewCompetencyIndex;
    state.expandedOverviewCourses[key] = !state.expandedOverviewCourses[key];
    renderCompetencyOverviewDetail();
  });

  $("#cellDetail").addEventListener("click", (event) => {
    const commentBtn = event.target.closest(".toggle-general-comment");
    if (commentBtn) {
      const key = commentBtn.dataset.detailKey;
      state.expandedComments[key] = !state.expandedComments[key];
      renderCellDetail();
      return;
    }
    const fragBtn = event.target.closest(".toggle-fragments");
    if (fragBtn) {
      const key = fragBtn.dataset.detailKey;
      state.expandedFragments[key] = !state.expandedFragments[key];
      renderCellDetail();
    }
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

  $("#periodCurriculumSelect")?.addEventListener("change", (event) => {
    state.newPeriodCurriculumId = event.target.value;
  });

  $("#matrixUploadForm")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await uploadMatrix($("#matrixFileInput").files);
    } catch (error) {
      console.error("[Matrices] No se pudo cargar la matriz:", error);
    }
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

  $("#criterionFilter").addEventListener("change", async (event) => {
    state.criterionFilter = event.target.value;
    await refreshApiEvidence();
    renderEvidence();
  });

  $("#evidenceList").addEventListener("click", (event) => {
    const button = event.target.closest(".evidence-cell-link");
    if (!button) return;
    openEvidenceCell(button.dataset.courseId, button.dataset.competencyCode);
  });

  $("#evidenceList").addEventListener("submit", async (event) => {
    const form = event.target.closest(".evidence-review-form");
    if (!form) return;
    event.preventDefault();
    const evidenceId = form.dataset.evidenceId;
    const formData = new FormData(form);
    const manualScore = Number(formData.get("manual_score"));
    if (!evidenceId || Number.isNaN(manualScore)) return;
    try {
      await apiRequest(`/evidence/${encodeURIComponent(evidenceId)}`, {
        method: "PATCH",
        body: JSON.stringify({
          manual_score: manualScore,
          manual_observation: String(formData.get("manual_observation") || "")
        })
      });
      await refreshApiAnalysis();
      renderAll();
    } catch (error) {
      console.error("[Evidencia] No se pudo guardar la revision:", error);
    }
  });

  $("#runAnalysis").addEventListener("click", simulateAnalysis);

  $("#exportExcel")?.addEventListener("click", () => {
    const period = currentPeriod();
    if (!period) return;
    const url = `${API_BASE_URL}/reports/excel?period_id=${encodeURIComponent(period.id)}`;
    window.open(url, "_blank");
  });
});


