window.chatState = window.chatState || { messages: [], pendingFiles: [] };
window.modelCatalog = window.modelCatalog || { items: [], ids: new Set(), lastChecked: null, unavailable: false };

let activeSidebarPanel = "";
let healthFailureNotified = false;

function showToast(text, type = "info") {
  const el = document.createElement("div");

  el.className = `toast toast-${type}`;
  el.textContent = text;
  document.body.appendChild(el);
  window.setTimeout(() => {
    el.classList.add("fade-out");
  }, 3000);
  window.setTimeout(() => {
    el.remove();
  }, 3500);
}

function getSessionId() {
  if (window.threadManager && window.threadManager.currentId) {
    return window.threadManager.currentId;
  }

  let sessionId = sessionStorage.getItem("gk_session_id");
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    sessionStorage.setItem("gk_session_id", sessionId);
  }
  return sessionId;
}

function resetChatShell() {
  const messages = document.getElementById("chat-area") || document.getElementById("chat-messages");
  if (messages) {
    messages.replaceChildren();
  }
}

function setSessionShortId() {
  const session = document.getElementById("session-id-short");
  if (session) {
    const sessionId = getSessionId();
    session.textContent = sessionId ? sessionId.slice(0, 8) : "";
  }
}

function resizeComposer() {
  const input = document.getElementById("query-input") || document.getElementById("chat-input");
  if (!input) {
    return;
  }

  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, 180)}px`;
}

function scheduleFileChipSync() {
  window.requestAnimationFrame(syncAttachedFiles);
}

function syncComposerState() {
  if (typeof window.syncChatComposerState === "function") {
    window.syncChatComposerState();
  }
}

function syncAttachedFiles() {
  const container = document.getElementById("attached-files");
  if (!container) {
    return;
  }

  container.replaceChildren();

  const files = Array.isArray(window.chatState.pendingFiles) ? window.chatState.pendingFiles : [];
  files.forEach((file, index) => {
    const chip = document.createElement("span");
    const remove = document.createElement("button");

    chip.className = "attached-file-chip";
    chip.textContent = file.name;

    remove.type = "button";
    remove.textContent = "x";
    remove.title = "Remove file";
    remove.addEventListener("click", () => {
      window.chatState.pendingFiles.splice(index, 1);
      if (!window.chatState.pendingFiles.length) {
        const input = document.getElementById("file-input");
        if (input) {
          input.value = "";
        }
      }
      syncAttachedFiles();
      syncComposerState();
    });

    chip.appendChild(remove);
    container.appendChild(chip);
  });
}

window.syncAttachedFiles = syncAttachedFiles;

function syncSelectionToLegacy(selection) {
  if (!selection) {
    return;
  }

  const patternSelect = document.getElementById("pattern-select");
  if (patternSelect && selection.pattern) {
    patternSelect.value = selection.pattern;
  }

  const modelSelect = document.getElementById("model-select");
  if (!modelSelect) {
    return;
  }

  const preferredModel = selection.model || (Array.isArray(selection.models) ? selection.models[0] : "");
  if (!preferredModel) {
    return;
  }

  let option = Array.from(modelSelect.options).find((item) => item.value === preferredModel);
  if (!option) {
    option = document.createElement("option");
    option.value = preferredModel;
    option.textContent = preferredModel;
    modelSelect.appendChild(option);
  }

  modelSelect.value = preferredModel;
}

function setModelBanner(message = "", type = "info") {
  const banner = document.getElementById("model-banner");
  if (!banner) {
    return;
  }

  if (!message) {
    banner.textContent = "";
    banner.classList.add("hidden");
    banner.classList.remove("warning");
    return;
  }

  banner.textContent = message;
  banner.classList.remove("hidden");
  banner.classList.toggle("warning", type === "warning");
}

function applyTheme(theme) {
  const isDark = theme === "dark";
  const toggle = document.getElementById("dark-mode-toggle");

  document.body.classList.toggle("dark", isDark);
  document.body.classList.toggle("light", !isDark);
  localStorage.setItem("gk_theme", isDark ? "dark" : "light");

  if (toggle) {
    toggle.textContent = isDark ? "◑" : "◐";
  }
}

function restoreTheme() {
  const savedTheme = localStorage.getItem("gk_theme");
  applyTheme(savedTheme === "dark" ? "dark" : "light");
}

function closeSidebar() {
  const sidebar = document.getElementById("sidebar");
  activeSidebarPanel = "";
  sidebar?.classList.remove("hidden");
  sidebar?.setAttribute("aria-hidden", "false");
  document.getElementById("panel-threads")?.classList.remove("hidden");
  document.getElementById("panel-stats")?.classList.remove("hidden");
  document.getElementById("nav-history")?.classList.remove("active");
  document.getElementById("nav-stats")?.classList.remove("active");
}

function showSidebarPanel(panelName) {
  const sidebar = document.getElementById("sidebar");
  const threadsPanel = document.getElementById("panel-threads");
  const statsPanel = document.getElementById("panel-stats");
  const historyBtn = document.getElementById("nav-history");
  const statsBtn = document.getElementById("nav-stats");

  if (!sidebar || !threadsPanel || !statsPanel || !historyBtn || !statsBtn) {
    return;
  }

  if (activeSidebarPanel === panelName) {
    closeSidebar();
    return;
  }

  activeSidebarPanel = panelName;
  sidebar.classList.remove("hidden");
  sidebar.setAttribute("aria-hidden", "false");
  threadsPanel.classList.remove("hidden");
  statsPanel.classList.remove("hidden");
  historyBtn.classList.toggle("active", panelName === "threads");
  statsBtn.classList.toggle("active", panelName === "stats");

  if (panelName === "threads") {
    threadsPanel.scrollIntoView({ block: "nearest" });
    void loadSidebarHistory();
  }

  if (panelName === "stats") {
    statsPanel.scrollIntoView({ block: "nearest" });
    void loadStats();
  }
}

function newSession() {
  if (window.threadManager && typeof window.threadManager.newThread === "function") {
    window.threadManager.newThread();
  } else {
    const sessionId = crypto.randomUUID();
    sessionStorage.setItem("gk_session_id", sessionId);
  }

  window.chatState.messages = [];
  window.chatState.pendingFiles = [];
  setSessionShortId();
  resetChatShell();
  document.dispatchEvent(new CustomEvent("chat:reset"));
  syncAttachedFiles();
  closeSidebar();
}

async function updateHealth() {
  const dot = document.getElementById("health-dot");
  const text = document.getElementById("health-text");

  if (!dot || !text) {
    return;
  }

  try {
    const data = await window.api.health();
    if (data && (data.status === "ok" || data.status === "healthy")) {
      healthFailureNotified = false;
      dot.className = "health-dot ok";
      text.textContent = "Сервис доступен";
      return;
    }
  } catch (_error) {
  }

  if (!healthFailureNotified) {
    showToast("Backend недоступен", "error");
    healthFailureNotified = true;
  }
  dot.className = "health-dot err";
  text.textContent = "Сервис недоступен";
}

async function loadModels() {
  const select = document.getElementById("model-select");
  if (!select) {
    return;
  }

  try {
    const response = await fetch("/api/v1/models");
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const detail = data?.detail;
      const message = typeof detail?.message === "string"
        ? detail.message
        : "Model catalog is unavailable.";
      throw new Error(message);
    }

    const entries = Array.isArray(data?.models) ? data.models : Array.isArray(data) ? data : [];
    select.innerHTML = "";
    window.modelCatalog = {
      items: entries,
      ids: new Set(
        entries.flatMap((model) => [model.id, model.model_id, model.display_name]).filter(Boolean),
      ),
      lastChecked: data?.last_checked || null,
      unavailable: false,
    };
    setModelBanner(
      data?.last_checked
        ? `Каталог моделей обновлён: ${new Date(data.last_checked).toLocaleString()}.`
        : "",
    );

    if (!entries.length) {
      const emptyOption = document.createElement("option");
      emptyOption.value = "";
      emptyOption.textContent = "No models";
      select.appendChild(emptyOption);
      return;
    }

    entries.forEach((model) => {
      const option = document.createElement("option");
      option.value = model.model_id || model.id || model;
      option.textContent = model.display_name || model.model_id || model.id || model;
      select.appendChild(option);
    });

    if (window.modelMenu && typeof window.modelMenu.setAvailableModels === "function") {
      window.modelMenu.setAvailableModels(entries);
      syncSelectionToLegacy(window.modelMenu.getSelection());
    }
  } catch (_error) {
    window.modelCatalog = {
      items: [],
      ids: new Set(),
      lastChecked: null,
      unavailable: true,
    };
    select.innerHTML = "<option value=\"\">Failed to load</option>";
    setModelBanner("Каталог моделей недоступен. Интерфейс работает без свежего snapshot.", "warning");
    return;
  }
}

function formatHistoryDate(value) {
  if (!value) {
    return "Недавно";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "Недавно";
  }

  return date.toLocaleString([], {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function loadSidebarHistory() {
  if (window.threadManager && typeof window.threadManager.render === "function") {
    window.threadManager.render();
    return;
  }

  const list = document.getElementById("thread-list") || document.getElementById("history-list");
  if (!list) {
    return;
  }

  list.replaceChildren();

  const empty = document.createElement("div");
  empty.className = "thread-empty";
  empty.textContent = "История появится после первого запроса.";
  list.appendChild(empty);
}

async function loadStats() {
  const totalEl = document.getElementById("stat-total");
  const successEl = document.getElementById("stat-success");
  const avgTimeEl = document.getElementById("stat-time") || document.getElementById("stat-avg-time");
  const modelsEl = document.getElementById("stat-accounts") || document.getElementById("stat-models");

  if (!totalEl || !successEl || !avgTimeEl || !modelsEl) {
    return;
  }

  try {
    const data = await window.api.get("/api/v1/analytics");
    const stats = Array.isArray(data?.models) ? data.models : Array.isArray(data) ? data : [];
    const total = stats.reduce((sum, item) => sum + (item.total_requests || 0), 0);
    const successful = stats.reduce((sum, item) => sum + (item.successful_requests || 0), 0);
    const avgDuration = stats.length
      ? Math.round(stats.reduce((sum, item) => sum + (item.avg_duration_ms || 0), 0) / stats.length)
      : 0;

    totalEl.textContent = total ? String(total) : "—";
    successEl.textContent = total ? `${Math.round((successful / total) * 100)}%` : "—";
    avgTimeEl.textContent = avgDuration ? `${avgDuration}ms` : "—";
    modelsEl.textContent = stats.length ? String(stats.length) : "—";
  } catch (_error) {
    totalEl.textContent = "—";
    successEl.textContent = "—";
    avgTimeEl.textContent = "—";
    modelsEl.textContent = "—";
  }
}

function bindSidebarControls() {
  document.getElementById("nav-new-thread")?.addEventListener("click", newSession);
  document.getElementById("btn-new-thread")?.addEventListener("click", newSession);
  document.getElementById("nav-history")?.addEventListener("click", () => {
    showSidebarPanel("threads");
  });
  document.getElementById("nav-stats")?.addEventListener("click", () => {
    showSidebarPanel("stats");
  });
  document.getElementById("close-sidebar")?.addEventListener("click", closeSidebar);
  document.getElementById("close-sidebar-stats")?.addEventListener("click", closeSidebar);
}

function bindThemeControls() {
  document.getElementById("dark-mode-toggle")?.addEventListener("click", () => {
    applyTheme(document.body.classList.contains("dark") ? "light" : "dark");
  });
}

function setupKeyboardShortcuts() {
  document.addEventListener("keydown", (event) => {
    const key = event.key.toLowerCase();

    if (event.ctrlKey && key === "enter") {
      event.preventDefault();
      (document.getElementById("btn-submit") || document.getElementById("send-btn"))?.click();
    }

    if (event.ctrlKey && key === "n") {
      event.preventDefault();
      document.getElementById("nav-new-thread")?.click();
    }

    if (key === "escape") {
      document.activeElement?.blur();
      document.getElementById("model-popup")?.classList.add("hidden");
    }

    if (event.ctrlKey && event.shiftKey && key === "c") {
      event.preventDefault();
      const bubbles = document.querySelectorAll(".chat-msg.assistant .chat-bubble");
      const lastBubble = bubbles[bubbles.length - 1];
      if (lastBubble?.innerText) {
        void navigator.clipboard?.writeText(lastBubble.innerText);
      }
    }
  });
}

function bindComposerControls() {
  const input = document.getElementById("query-input") || document.getElementById("chat-input");
  const fileInput = document.getElementById("file-input");
  const fileClearBtn = document.getElementById("file-clear-btn");

  if (input) {
    input.addEventListener("input", () => {
      resizeComposer();
      syncComposerState();
    });
  }

  fileInput?.addEventListener("change", scheduleFileChipSync);
  fileClearBtn?.addEventListener("click", scheduleFileChipSync);
  document.addEventListener("chat:reset", () => {
    resizeComposer();
    syncComposerState();
    syncAttachedFiles();
  });
}

function bindModelMenu() {
  window.addEventListener("modelmenu:change", (event) => {
    syncSelectionToLegacy(event.detail);
  });

  if (window.modelMenu && typeof window.modelMenu.getSelection === "function") {
    syncSelectionToLegacy(window.modelMenu.getSelection());
  }
}

async function init() {
  restoreTheme();
  setSessionShortId();
  window.addEventListener("threads:changed", () => {
    setSessionShortId();
  });
  const mainHeader = document.querySelector(".main-header");
  const headerStatus = document.querySelector(".header-status");
  const exportBtn = document.getElementById("export-btn");
  if (mainHeader && headerStatus && exportBtn) {
    exportBtn.className = "icon-btn";
    exportBtn.type = "button";
    exportBtn.title = "Export current thread";
    exportBtn.textContent = "⬇";
    exportBtn.style.marginLeft = "auto";
    exportBtn.style.marginRight = "8px";
    mainHeader.insertBefore(exportBtn, headerStatus);
  }
  const actionBtns = document.querySelector(".action-btns");
  const dryRunCheck = document.getElementById("dry-run-check");
  const dryRunLabel = dryRunCheck?.parentElement;
  if (actionBtns && dryRunCheck && dryRunLabel instanceof HTMLLabelElement) {
    const labelText = dryRunLabel.querySelector("span");
    dryRunLabel.title = "Dry run";
    dryRunLabel.style.display = "flex";
    dryRunLabel.style.alignItems = "center";
    dryRunLabel.style.gap = "3px";
    dryRunLabel.style.fontSize = "11px";
    dryRunLabel.style.color = "var(--text-muted)";
    dryRunLabel.style.cursor = "pointer";
    dryRunLabel.style.whiteSpace = "nowrap";
    dryRunCheck.style.width = "12px";
    dryRunCheck.style.height = "12px";
    dryRunCheck.style.accentColor = "var(--accent)";
    if (labelText) {
      labelText.textContent = "dry";
    }
    actionBtns.insertBefore(dryRunLabel, actionBtns.firstChild);
  }
  document.getElementById("file-preview-bar")?.style.setProperty("display", "none");
  bindSidebarControls();
  bindThemeControls();
  setupKeyboardShortcuts();
  bindComposerControls();
  bindModelMenu();
  resizeComposer();
  syncAttachedFiles();
  syncComposerState();
  await updateHealth();
  await loadModels();
  const currentThread = window.threadManager?.current;
  if (currentThread?.messages?.length && typeof window.renderThreadMessages === "function") {
    window.renderThreadMessages(currentThread.messages);
  }
  window.threadManager?.render();
  window.setInterval(updateHealth, 30000);
  window.setInterval(loadSidebarHistory, 60000);
}

void init();
