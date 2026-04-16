window.chatState = window.chatState || { messages: [], pendingFiles: [] };
window.chatState.messages = Array.isArray(window.chatState.messages) ? window.chatState.messages : [];
window.chatState.pendingFiles = Array.isArray(window.chatState.pendingFiles) ? window.chatState.pendingFiles : [];

const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const sendBtn = document.getElementById("send-btn");
const attachBtn = document.getElementById("attach-btn");
const fileInput = document.getElementById("file-input");
const filePreviewBar = document.getElementById("file-preview-bar");
const filePreviewName = document.getElementById("file-preview-name");
const fileClearBtn = document.getElementById("file-clear-btn");
const exportBar = document.getElementById("export-bar");
const exportBtn = document.getElementById("export-btn");
const dryRunCheck = document.getElementById("dry-run-check");
const modelSelect = document.getElementById("model-select");

let isSending = false;

function scrollMessages() {
  if (chatMessages) {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }
}

function syncExportState() {
  const messages = window.threadManager?.getMessages() || window.chatState.messages;
  const hasMessages = Array.isArray(messages) && messages.length > 0;
  if (exportBar) {
    exportBar.style.display = "none";
  }
  if (exportBtn) {
    exportBtn.disabled = !hasMessages;
    exportBtn.style.opacity = hasMessages ? "1" : "0.45";
  }
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function formatMarkdown(text) {
  return escapeHtml(text || "")
    .replace(/```([\s\S]*?)```/g, "<pre><code>$1</code></pre>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>")
    .replace(/^#{3}\s(.+)$/gm, "<h3>$1</h3>")
    .replace(/^#{2}\s(.+)$/gm, "<h2>$1</h2>")
    .replace(/^#{1}\s(.+)$/gm, "<h1>$1</h1>")
    .replace(/\n/g, "<br>");
}

function mapErrorToUserMessage(err) {
  const msg = String(err?.message || err || "");
  const normalized = msg.toLowerCase();
  if (msg.includes("503") || normalized.includes("service unavailable")) {
    return "Сервис временно недоступен. Возможно, модель загружается.";
  }
  if (msg.includes("429") || normalized.includes("too many")) {
    return "Слишком много запросов. Подождите немного.";
  }
  if (msg.includes("401") || normalized.includes("unauthorized")) {
    return "Ошибка авторизации. Проверьте API ключ.";
  }
  if (normalized.includes("timeout") || normalized.includes("timed out")) {
    return "Запрос превысил время ожидания. Попробуйте снова.";
  }
  if (normalized.includes("circuit")) {
    return "Browser-адаптер временно отключён. Используется API fallback.";
  }
  if (normalized.includes("embeddings")) {
    return "Embeddings клиент не настроен. Для консенсуса нужен GRACEKELLY_MISTRAL_API_KEY.";
  }
  if (
    normalized.includes("fetch")
    || normalized.includes("network")
    || normalized.includes("failed to fetch")
  ) {
    return "Не удалось подключиться к серверу. Проверьте, что backend запущен.";
  }
  return `Произошла ошибка: ${(msg || "Неизвестная ошибка").slice(0, 100)}`;
}

function executionModeLabel(mode) {
  switch (String(mode || "").toLowerCase()) {
    case "browser":
      return "🌐 Browser";
    case "api":
      return "⚡ API";
    case "dry-run":
      return "🧪 DryRun";
    case "mixed":
      return "🔀 Mixed";
    default:
      return mode || "";
  }
}

function getModelSelection() {
  if (window.modelMenu && typeof window.modelMenu.getSelection === "function") {
    return window.modelMenu.getSelection();
  }

  return {
    pattern: document.getElementById("pattern-select")?.value || "single",
    model: modelSelect?.value || "",
    models: null,
  };
}

function formatMeta(meta) {
  if (!meta) {
    return "";
  }

  const parts = [];
  if (meta.execution_mode) {
    parts.push(executionModeLabel(meta.execution_mode));
  }
  if (meta.model_id) {
    parts.push(meta.model_id);
  }
  if (typeof meta.input_tokens === "number" || typeof meta.output_tokens === "number") {
    parts.push(`${(meta.input_tokens || 0) + (meta.output_tokens || 0)} tokens`);
  }
  if (typeof meta.cost_usd === "number" && Number.isFinite(meta.cost_usd)) {
    parts.push(`$${meta.cost_usd.toFixed(4)}`);
  }
  if (typeof meta.duration_ms === "number") {
    parts.push(`${meta.duration_ms}ms`);
  }
  return parts.join(" · ");
}

function syncComposerState() {
  sendBtn.disabled = isSending || chatInput.value.trim().length === 0;
}

window.syncChatComposerState = syncComposerState;

function updateFilePreview() {
  if (filePreviewBar) {
    filePreviewBar.style.display = "none";
  }
  if (filePreviewName) {
    filePreviewName.textContent = "";
  }
  if (typeof window.syncAttachedFiles === "function") {
    window.syncAttachedFiles();
  }
}

function clearPendingFiles() {
  window.chatState.pendingFiles = [];
  fileInput.value = "";
  updateFilePreview();
}

async function hydrateTaskData(taskId, fallbackMeta, fallbackText) {
  const meta = { ...fallbackMeta };
  let text = fallbackText;

  if (!taskId) {
    return { meta, text };
  }

  try {
    const task = await window.api.get(`/api/v1/tasks/${taskId}`);
    const completedStep = Array.isArray(task.steps)
      ? task.steps.find((step) => step.status === "completed") || task.steps[0]
      : null;

    if (!text && typeof task.output_text === "string") {
      text = task.output_text;
    }
    if (!meta.model_id) {
      meta.model_id = task.model?.id || completedStep?.model_id || meta.model_id;
    }
    if (!meta.execution_mode && task.execution_mode) {
      meta.execution_mode = task.execution_mode;
    }
    if (typeof meta.duration_ms !== "number" && typeof task.duration_ms === "number") {
      meta.duration_ms = task.duration_ms;
    }
    if (typeof task.was_decomposed === "boolean") {
      meta.was_decomposed = task.was_decomposed;
    }
    if (typeof task.subtask_count === "number") {
      meta.subtask_count = task.subtask_count;
    }
    if (completedStep) {
      if (typeof completedStep.input_tokens === "number") {
        meta.input_tokens = completedStep.input_tokens;
      }
      if (typeof completedStep.output_tokens === "number") {
        meta.output_tokens = completedStep.output_tokens;
      }
      if (typeof completedStep.cost_usd === "number") {
        meta.cost_usd = completedStep.cost_usd;
      }
      if (typeof completedStep.duration_ms === "number" && typeof meta.duration_ms !== "number") {
        meta.duration_ms = completedStep.duration_ms;
      }
      if (!meta.model_id && completedStep.model_id) {
        meta.model_id = completedStep.model_id;
      }
    }
  } catch (_error) {
  }

  return { meta, text };
}

function appendMetaBelow(container, meta) {
  const metaText = formatMeta(meta);
  if (metaText) {
    const metaEl = document.createElement("div");
    metaEl.className = "msg-meta";
    metaEl.textContent = metaText;
    container.appendChild(metaEl);
  }

  if (meta?.was_decomposed) {
    const badge = document.createElement("div");
    badge.className = "decomp-badge";
    badge.textContent = `Decomposed into ${meta.subtask_count || "?"} subtasks`;
    container.appendChild(badge);
  }
}

function appendMultiModelDisplay(meta, container) {
  const responses = Array.isArray(meta?.model_responses) ? meta.model_responses : [];
  const hasAgreement = typeof meta?.agreement_rate === "number";
  if (!hasAgreement && !responses.length) {
    return;
  }

  const wrapper = document.createElement("div");
  wrapper.className = "model-responses";

  if (hasAgreement) {
    const badge = document.createElement("div");
    badge.className = "agreement-badge";
    badge.textContent = `✓ Согласие: ${meta.agreement_rate}%`;
    wrapper.appendChild(badge);
  }

  if (responses.length) {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.textContent = `${responses.length} models`;
    details.appendChild(summary);

    responses.forEach((response) => {
      const card = document.createElement("div");
      const name = document.createElement("div");
      const status = document.createElement("div");
      const body = document.createElement("div");
      const preview = (response.text || "").trim();

      card.className = "model-response-card";
      name.className = "model-name";
      name.textContent = response.model_id || "?";
      body.innerHTML = formatMarkdown(preview || `[${response.status || "empty"}]`);

      card.appendChild(name);
      if (response.status && response.status !== "completed") {
        status.className = "msg-meta";
        status.textContent = response.status;
        card.appendChild(status);
      }
      card.appendChild(body);
      details.appendChild(card);
    });

    wrapper.appendChild(details);
  }

  container.appendChild(wrapper);
}

function appendUserBubble(text) {
  const article = document.createElement("article");
  article.className = "chat-msg user";
  article.innerHTML = `<div class="chat-bubble">${escapeHtml(text)}</div>`;
  chatMessages.appendChild(article);
  scrollMessages();
  return article;
}

function createStreamingBubble() {
  const article = document.createElement("article");
  article.className = "chat-msg assistant";

  const bubble = document.createElement("div");
  bubble.className = "chat-bubble streaming";
  bubble.style.whiteSpace = "pre-wrap";
  article.appendChild(bubble);

  chatMessages.appendChild(article);
  scrollMessages();
  return { container: article, el: bubble };
}

function finalizeAssistantBubble(bubble, text, meta, isError = false) {
  bubble.el.classList.remove("streaming");
  bubble.el.innerHTML = formatMarkdown(text);

  if (isError) {
    bubble.container.style.borderLeft = "2px solid #f44336";
  }
  if (meta) {
    appendMetaBelow(bubble.container, meta);
    appendMultiModelDisplay(meta, bubble.container);
  }

  scrollMessages();
}

function appendAssistantBubble(text, meta, isError = false) {
  const bubble = createStreamingBubble();
  finalizeAssistantBubble(bubble, text, meta, isError);
  return bubble.container;
}

function appendErrorBubble(text, retryFn) {
  const article = document.createElement("article");
  const bubble = document.createElement("div");
  const icon = document.createElement("div");
  const errorText = document.createElement("div");
  const retryBtn = document.createElement("button");

  article.className = "chat-msg assistant";
  bubble.className = "chat-bubble error-bubble";
  icon.className = "error-icon";
  icon.textContent = "⚠";
  errorText.className = "error-text";
  errorText.textContent = text;
  retryBtn.className = "retry-btn";
  retryBtn.type = "button";
  retryBtn.textContent = "Повторить";
  retryBtn.addEventListener("click", () => {
    article.remove();
    retryFn();
  });

  bubble.appendChild(icon);
  bubble.appendChild(errorText);
  bubble.appendChild(retryBtn);
  article.appendChild(bubble);
  chatMessages.appendChild(article);
  scrollMessages();
  return article;
}

function normalizeModelResponses(raw) {
  const source = Array.isArray(raw?.model_responses)
    ? raw.model_responses
    : Array.isArray(raw?.answers)
      ? raw.answers
      : Array.isArray(raw?.results)
        ? raw.results
        : Array.isArray(raw?.responses)
          ? raw.responses
          : [];

  return source.map((response) => ({
    model_id: response.model_id || response.model || response.adapter_name || response.name || "",
    status: response.status || "",
    text: response.answer || response.output_text || response.text || response.response || "",
  }));
}

function normalizeMeta(raw, fallbackModelId) {
  const details = raw?.details && typeof raw.details === "object" ? raw.details : {};
  const decomposition = raw?.decomposition && typeof raw.decomposition === "object"
    ? raw.decomposition
    : details.decomposition && typeof details.decomposition === "object"
      ? details.decomposition
      : {};

  return {
    model_id: raw?.model_id || raw?.model?.id || fallbackModelId || "",
    execution_mode:
      raw?.execution_mode || raw?.task?.execution_mode || details.execution_mode || (raw?.dry_run ? "dry-run" : null),
    input_tokens: typeof raw?.input_tokens === "number" ? raw.input_tokens : details.input_tokens,
    output_tokens: typeof raw?.output_tokens === "number" ? raw.output_tokens : details.output_tokens,
    duration_ms: typeof raw?.duration_ms === "number" ? raw.duration_ms : details.duration_ms,
    cost_usd: typeof raw?.cost_usd === "number" ? raw.cost_usd : details.cost_usd,
    agreement_rate: typeof raw?.agreement_rate === "number"
      ? raw.agreement_rate
      : typeof raw?.consensus_score === "number"
        ? Math.round(raw.consensus_score * 100)
        : null,
    model_responses: normalizeModelResponses(raw),
    was_decomposed: typeof raw?.was_decomposed === "boolean"
      ? raw.was_decomposed
      : typeof decomposition.was_decomposed === "boolean"
        ? decomposition.was_decomposed
        : false,
    subtask_count: typeof raw?.subtask_count === "number"
      ? raw.subtask_count
      : typeof decomposition.subtask_count === "number"
        ? decomposition.subtask_count
        : 0,
  };
}

function persistMessage(role, content, meta = null) {
  if (window.threadManager && typeof window.threadManager.addMessage === "function") {
    window.threadManager.addMessage(role, content, meta);
    window.chatState.messages = window.threadManager.getMessages();
  } else {
    window.chatState.messages.push({ role, content, meta });
  }

  syncExportState();
}

function renderThreadMessages(messages) {
  chatMessages.replaceChildren();
  window.chatState.messages = Array.isArray(messages)
    ? messages.map((message) => ({ ...message, meta: message.meta || null }))
    : [];

  window.chatState.messages.forEach((message) => {
    if (message.role === "user") {
      appendUserBubble(message.content || "");
      return;
    }

    appendAssistantBubble(message.content || "", message.meta || null);
  });

  syncExportState();
  scrollMessages();
}

function buildCompareFallback(answers) {
  const items = Array.isArray(answers) ? answers : [];
  return items
    .filter((item) => item.answer)
    .map((item) => `${item.model_id}:\n${item.answer}`)
    .join("\n\n");
}

function showLoading(message = "Processing...", pct = 0) {
  document.getElementById("loading-state")?.classList.remove("hidden");
  updateLoading(message, pct);
}

function updateLoading(message, pct) {
  const status = document.getElementById("loading-status");
  const fill = document.getElementById("progress-fill");
  if (status) {
    status.textContent = message;
  }
  if (fill) {
    fill.style.width = `${pct}%`;
  }
}

function hideLoading() {
  document.getElementById("loading-state")?.classList.add("hidden");
  const fill = document.getElementById("progress-fill");
  if (fill) {
    fill.style.width = "0%";
  }
}

window.appendUserBubble = appendUserBubble;
window.appendAssistantBubble = appendAssistantBubble;
window.renderThreadMessages = renderThreadMessages;

async function streamChat(body, onChunk) {
  const response = await fetch("/api/v1/orchestrate/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    throw new Error(`${response.status}: ${await response.text()}`);
  }
  if (!response.body) {
    throw new Error("Streaming response body is unavailable.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let acceptedEvent = null;
  let finalEvent = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }

    buffer += decoder.decode(value, { stream: true });
    const blocks = buffer.split(/\r?\n\r?\n/);
    buffer = blocks.pop() || "";

    for (const block of blocks) {
      const lines = block.split(/\r?\n/);
      let eventName = "";
      let dataLine = "";

      for (const line of lines) {
        if (line.startsWith("event:")) {
          eventName = line.slice(6).trim();
        } else if (line.startsWith("data:")) {
          dataLine += line.slice(5).trimStart();
        }
      }

      if (!dataLine) {
        continue;
      }

      const payload = JSON.parse(dataLine);
      if (eventName === "accepted") {
        acceptedEvent = payload;
      } else if (eventName === "delta") {
        onChunk(payload.text || "");
      } else if (eventName === "complete") {
        finalEvent = payload;
      } else if (eventName === "error") {
        throw new Error(payload.text || payload.detail || "Stream error");
      }
    }
  }

  return { acceptedEvent, finalEvent };
}

async function sendMessage(rawText) {
  const text = rawText.trim();
  if (!text || isSending) {
    return;
  }

  const sessionId = window.threadManager?.currentId || getSessionId();
  const selection = getModelSelection();
  const pattern = selection.pattern || "single";
  const modelId = selection.model || "";
  const modelIds = Array.isArray(selection.models) ? selection.models.filter(Boolean) : [];
  const dryRun = Boolean(dryRunCheck?.checked);
  const files = [...window.chatState.pendingFiles];

  appendUserBubble(text);
  persistMessage("user", text);

  chatInput.value = "";
  clearPendingFiles();

  isSending = true;
  attachBtn.disabled = true;
  fileInput.disabled = true;
  if (dryRunCheck) {
    dryRunCheck.disabled = true;
  }
  syncComposerState();
  let acceptedMessage = "Запрос принят...";
  let processingMessage = "Обработка запроса...";
  let renderingMessage = "Рендеринг ответа...";

  if (files.length) {
    processingMessage = "Загрузка файлов и обработка...";
  } else if (pattern === "single" || pattern === "sonar") {
    acceptedMessage = "Подключение к модели...";
    processingMessage = "Генерация ответа...";
  } else if (pattern === "consensus") {
    acceptedMessage = "Запуск консенсуса...";
    processingMessage = "Обработка результатов...";
    renderingMessage = "Рендеринг сводки...";
  } else if (pattern === "compare") {
    acceptedMessage = "Параллельный запрос к моделям...";
    processingMessage = "Сравнение ответов...";
    renderingMessage = "Рендеринг сравнения...";
  } else if (pattern === "debate") {
    acceptedMessage = "Раунд 1: формирование позиции...";
    processingMessage = "Раунд 2: критика...";
    renderingMessage = "Раунд 3: улучшение...";
  } else if (pattern === "smart") {
    acceptedMessage = "Определение маршрута...";
  }

  showLoading(acceptedMessage, 10);
  await new Promise((resolve) => window.requestAnimationFrame(resolve));

  const bubble = createStreamingBubble();

  try {
    let responseText = "";
    let meta = {};
    let taskId = null;

    if (files.length) {
      updateLoading(processingMessage, 40);
      const formData = new FormData();
      formData.append("prompt", text);
      if (modelIds.length > 1) {
        formData.append("models", JSON.stringify(modelIds));
      } else if (modelId) {
        formData.append("model", modelId);
      }
      formData.append("dry_run", String(dryRun));
      formData.append("session_id", sessionId);
      files.forEach((file) => formData.append("files", file, file.name));

      bubble.el.textContent = "...";
      const result = await window.api.postForm("/api/v1/orchestrate/upload", formData);
      updateLoading(renderingMessage, 90);
      responseText = result.output_text || "";
      taskId = result.task_id || null;
      const taskData = await hydrateTaskData(taskId, normalizeMeta(result, modelId), responseText);
      responseText = taskData.text || responseText;
      meta = taskData.meta;
    } else if (pattern === "single" || pattern === "sonar") {
      updateLoading(processingMessage, 40);
      await new Promise((resolve) => window.requestAnimationFrame(resolve));
      const body = {
        prompt: text,
        dry_run: dryRun,
        session_id: sessionId,
        decompose: true,
      };

      if (modelId) {
        body.model = modelId;
      } else if (modelIds.length === 1) {
        body.model = modelIds[0];
      }

      const streamResult = await streamChat(body, (chunk) => {
        responseText += chunk;
        bubble.el.innerHTML = formatMarkdown(responseText);
        scrollMessages();
      });

      updateLoading(renderingMessage, 90);
      const finalEvent = streamResult.finalEvent || {};
      taskId = finalEvent.task_id || streamResult.acceptedEvent?.task_id || null;
      const taskData = await hydrateTaskData(taskId, normalizeMeta(finalEvent, modelId), responseText);
      responseText = taskData.text || responseText;
      meta = taskData.meta;
    } else if (pattern === "consensus") {
      updateLoading(processingMessage, 40);
      bubble.el.textContent = "...";
      const body = { prompt: text };
      if (modelId) {
        body.model = modelId;
      }

      const result = await window.api.post("/api/v1/consensus", body);
      updateLoading(renderingMessage, 90);
      responseText = result.best_response || result.output_text || "";
      meta = normalizeMeta(result, modelId);
    } else if (pattern === "compare") {
      updateLoading(processingMessage, 40);
      bubble.el.textContent = "...";
      const compareModels = modelIds.length ? modelIds : modelId ? [modelId] : [];
      if (!compareModels.length) {
        throw new Error("No models selected for compare.");
      }

      const result = await window.api.post("/api/v1/compare", {
        prompt: text,
        models: compareModels,
        analyze: true,
      });
      updateLoading(renderingMessage, 90);
      responseText = result.analysis || buildCompareFallback(result.answers);
      meta = normalizeMeta(result, compareModels[0] || modelId);
    } else if (pattern === "debate") {
      updateLoading(processingMessage, 40);
      bubble.el.textContent = "...";
      const body = { topic: text };
      if (modelId) {
        body.model = modelId;
      }

      const result = await window.api.post("/api/v1/debate", body);
      updateLoading(renderingMessage, 90);
      responseText = result.improved_response || result.output_text || "";
      meta = normalizeMeta(result, result.model_id || modelId);
    } else if (pattern === "smart") {
      updateLoading(processingMessage, 40);
      bubble.el.textContent = "...";
      const body = { prompt: text };
      if (modelId) {
        body.model = modelId;
      }

      const result = await window.api.post("/api/v1/smart", body);
      updateLoading(renderingMessage, 90);
      responseText = result.answer || result.output_text || result.best_response || "";
      meta = normalizeMeta(result, result.model_id || modelId);
    } else {
      throw new Error(`Unsupported pattern: ${pattern}`);
    }

    if (dryRun && !responseText.trim()) {
      responseText = "[dry-run] Запрос обработан без реального вызова модели.";
    }
    finalizeAssistantBubble(bubble, responseText, meta);
    persistMessage("assistant", responseText, meta);
    updateLoading("Готово", 100);
    await new Promise((resolve) => window.setTimeout(resolve, 120));
  } catch (error) {
    updateLoading("Ошибка", 100);
    bubble.container.remove();
    appendErrorBubble(mapErrorToUserMessage(error), () => {
      void sendMessage(text);
    });
    await new Promise((resolve) => window.setTimeout(resolve, 120));
  } finally {
    hideLoading();
    isSending = false;
    attachBtn.disabled = false;
    fileInput.disabled = false;
    if (dryRunCheck) {
      dryRunCheck.disabled = false;
    }
    syncComposerState();
    chatInput.focus();
  }
}
function resetChatUi() {
  chatMessages.replaceChildren();
  chatInput.value = "";
  clearPendingFiles();
  window.chatState.messages = [];
  syncExportState();
  syncComposerState();
}

attachBtn.addEventListener("click", () => {
  if (!attachBtn.disabled) {
    fileInput.click();
  }
});

fileInput.addEventListener("change", (event) => {
  const files = Array.from(event.target.files || []);
  if (!files.length) {
    return;
  }
  window.chatState.pendingFiles = files;
  updateFilePreview();
  syncComposerState();
});

fileClearBtn.addEventListener("click", () => {
  clearPendingFiles();
  syncComposerState();
});

sendBtn.addEventListener("click", () => {
  void sendMessage(chatInput.value);
});

chatInput.addEventListener("input", syncComposerState);
chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    void sendMessage(chatInput.value);
  }
});

document.addEventListener("chat:reset", resetChatUi);

if (window.threadManager && typeof window.threadManager.renderCurrent === "function") {
  window.threadManager.renderCurrent();
} else {
  resetChatUi();
}
