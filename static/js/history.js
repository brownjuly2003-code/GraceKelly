const historyTable = null;
const taskDetail = null;
const refreshHistoryBtn = document.getElementById("refresh-history-btn");
const historyTabBtn = document.querySelector('.tab-btn[data-tab="history"]');

let activeHistoryTaskId = "";

function historyStatusClass(status) {
  return `history-status status-${(status || "unknown").toLowerCase()}`;
}

function formatHistoryTimestamp(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString();
}

function formatHistoryDuration(value) {
  return typeof value === "number" ? `${value}ms` : "";
}

function setHistoryMessage(message, isError = false) {
  historyTable.innerHTML = `<div style="color:${isError ? "#f44" : "#555"}; padding:8px;">${message}</div>`;
}

function updateActiveHistoryRow(taskId) {
  historyTable.querySelectorAll(".history-row").forEach((row) => {
    row.classList.toggle("active", row.dataset.taskId === taskId);
  });
}

async function loadHistoryTable() {
  if (window.threadManager && typeof window.threadManager.render === "function") {
    window.threadManager.render();
    return;
  }

  setHistoryMessage("Loading...");

  try {
    const data = await window.api.tasks(50);
    const tasks = Array.isArray(data) ? data : data?.items || [];

    historyTable.replaceChildren();

    if (!tasks.length) {
      setHistoryMessage("No tasks yet");
      return;
    }

    tasks.forEach((task) => {
      const taskId = task.task_id || task.id || "";
      const row = document.createElement("button");
      const status = task.status || "unknown";
      const prompt = typeof task.prompt === "string" && task.prompt.trim() ? task.prompt.trim() : "Task";
      const metaParts = [];
      const mode = task.execution_mode || (task.dry_run ? "dry-run" : "");
      const acceptedAt = formatHistoryTimestamp(task.accepted_at || task.created_at || task.completed_at);

      if (task.model_count) {
        metaParts.push(`${task.model_count} model${task.model_count === 1 ? "" : "s"}`);
      }
      if (mode) {
        metaParts.push(mode);
      }
      if (acceptedAt) {
        metaParts.push(acceptedAt);
      }

      row.type = "button";
      row.className = "history-row";
      row.dataset.taskId = taskId;

      const statusEl = document.createElement("span");
      statusEl.className = historyStatusClass(status);
      statusEl.textContent = status;
      row.appendChild(statusEl);

      const promptEl = document.createElement("span");
      promptEl.className = "history-prompt";
      promptEl.textContent = prompt.slice(0, 120);
      row.appendChild(promptEl);

      const metaEl = document.createElement("span");
      metaEl.className = "history-meta";
      metaEl.textContent = metaParts.join(" · ");
      row.appendChild(metaEl);

      row.addEventListener("click", () => {
        void showTaskDetail(taskId);
      });

      historyTable.appendChild(row);
    });

    if (activeHistoryTaskId) {
      updateActiveHistoryRow(activeHistoryTaskId);
    }
  } catch (error) {
    setHistoryMessage(`Error: ${error instanceof Error ? error.message : String(error)}`, true);
  }
}

async function showTaskDetail(taskId) {
  if (window.threadManager && typeof window.threadManager.render === "function") {
    return;
  }

  if (!taskId) {
    return;
  }

  activeHistoryTaskId = taskId;
  updateActiveHistoryRow(taskId);
  taskDetail.style.display = "block";
  taskDetail.textContent = "Loading...";

  try {
    const task = await window.api.get(`/api/v1/tasks/${taskId}`);
    const steps = Array.isArray(task.steps) ? task.steps : [];
    const metaParts = [task.status || "unknown"];
    const acceptedAt = formatHistoryTimestamp(task.accepted_at || task.created_at || task.completed_at);
    const duration = formatHistoryDuration(task.duration_ms);
    const mode = task.execution_mode || (task.dry_run ? "dry-run" : "");

    if (mode) {
      metaParts.push(mode);
    }
    if (duration) {
      metaParts.push(duration);
    }
    if (acceptedAt) {
      metaParts.push(acceptedAt);
    }

    taskDetail.replaceChildren();

    const header = document.createElement("div");
    header.style.display = "flex";
    header.style.justifyContent = "space-between";
    header.style.gap = "12px";
    header.style.marginBottom = "8px";

    const title = document.createElement("strong");
    title.style.color = "#ccc";
    title.textContent = task.prompt || "Task";
    header.appendChild(title);

    const idText = document.createElement("span");
    idText.style.fontSize = "12px";
    idText.style.color = "#555";
    idText.textContent = task.task_id || taskId;
    header.appendChild(idText);

    taskDetail.appendChild(header);

    const meta = document.createElement("div");
    meta.className = "history-detail-meta";
    meta.textContent = metaParts.join(" · ");
    taskDetail.appendChild(meta);

    const promptSectionTitle = document.createElement("span");
    promptSectionTitle.className = "history-detail-title";
    promptSectionTitle.textContent = "Prompt";
    taskDetail.appendChild(promptSectionTitle);

    const promptBlock = document.createElement("pre");
    promptBlock.className = "pg-output-block";
    promptBlock.textContent = task.prompt || "[empty]";
    taskDetail.appendChild(promptBlock);

    const outputSectionTitle = document.createElement("span");
    outputSectionTitle.className = "history-detail-title";
    outputSectionTitle.style.marginTop = "12px";
    outputSectionTitle.textContent = "Output";
    taskDetail.appendChild(outputSectionTitle);

    const outputBlock = document.createElement("pre");
    outputBlock.className = "pg-output-block";
    outputBlock.textContent = task.output_text || "[empty]";
    taskDetail.appendChild(outputBlock);

    if (steps.length) {
      const stepsTitle = document.createElement("span");
      stepsTitle.className = "history-detail-title";
      stepsTitle.style.marginTop = "12px";
      stepsTitle.textContent = "Steps";
      taskDetail.appendChild(stepsTitle);

      steps.forEach((step) => {
        const stepEl = document.createElement("div");
        stepEl.className = "history-step";
        const parts = [
          `#${typeof step.step_index === "number" ? step.step_index : "?"}`,
          step.model_id || step.model_display_name || "unknown-model",
          step.status || "unknown",
        ];
        const stepDuration = formatHistoryDuration(step.duration_ms);
        if (stepDuration) {
          parts.push(stepDuration);
        }
        stepEl.textContent = parts.join(" · ");
        taskDetail.appendChild(stepEl);
      });
    }
  } catch (error) {
    taskDetail.textContent = `Error: ${error instanceof Error ? error.message : String(error)}`;
  }
}

refreshHistoryBtn?.addEventListener("click", () => {
  void loadHistoryTable();
});

historyTabBtn?.addEventListener("click", () => {
  void loadHistoryTable();
});
