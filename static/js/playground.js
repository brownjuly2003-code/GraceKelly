const pgPatternSel = document.getElementById("pg-pattern");
const pgModelSel = document.getElementById("pg-model-select");
const pgCompareModels = document.getElementById("pg-compare-models");
const pgPrompt = document.getElementById("pg-prompt");
const pgSubmitBtn = document.getElementById("pg-submit-btn");
const pgResult = document.getElementById("pg-result-area");
const pgDryRun = document.getElementById("pg-dry-run");
const pgReasoning = document.getElementById("pg-reasoning");

function clearPlaygroundResult(preWrap = true) {
  pgResult.replaceChildren();
  pgResult.style.whiteSpace = preWrap ? "pre-wrap" : "normal";
}

function setPlaygroundText(text) {
  clearPlaygroundResult(true);
  pgResult.textContent = text;
}

function populatePlaygroundModels(models) {
  const entries = (Array.isArray(models) ? models : Object.values(models || {}))
    .map((model) => ({
      value: typeof model === "string" ? model : model.model_id || model.id || "",
      label: typeof model === "string" ? model : model.display_name || model.model_id || model.id || "",
    }))
    .filter((model) => model.value);

  const currentModel = pgModelSel.value;
  const currentCompare = Array.from(pgCompareModels.selectedOptions).map((option) => option.value);

  if (!entries.length) {
    pgModelSel.innerHTML = "<option>No models</option>";
    pgCompareModels.innerHTML = "";
    return;
  }

  pgModelSel.innerHTML = "";
  pgCompareModels.innerHTML = "";

  entries.forEach((model) => {
    const option = document.createElement("option");
    option.value = model.value;
    option.textContent = model.label;
    if (model.value === currentModel) {
      option.selected = true;
    }
    pgModelSel.appendChild(option);

    const compareOption = document.createElement("option");
    compareOption.value = model.value;
    compareOption.textContent = model.label;
    if (currentCompare.includes(model.value)) {
      compareOption.selected = true;
    }
    pgCompareModels.appendChild(compareOption);
  });
}

window.populatePlaygroundModels = populatePlaygroundModels;

function syncPlaygroundModelsFromShell() {
  const shellSelect = document.getElementById("model-select");
  if (!shellSelect || !shellSelect.options.length) {
    return;
  }

  const entries = Array.from(shellSelect.options)
    .map((option) => ({
      model_id: option.value,
      display_name: option.textContent || option.value,
    }))
    .filter((option) => option.model_id && option.model_id !== "Loading...");

  if (entries.length) {
    populatePlaygroundModels(entries);
  }
}

function togglePlaygroundOptions() {
  const pattern = pgPatternSel.value;
  document.getElementById("pg-consensus-opts").style.display = pattern === "consensus" ? "block" : "none";
  document.getElementById("pg-compare-opts").style.display = pattern === "compare" ? "block" : "none";
  pgDryRun.disabled = pattern !== "single";
  pgReasoning.disabled = pattern !== "single";
}

function appendOutputBlock(title, text) {
  const wrapper = document.createElement("section");
  const heading = document.createElement("strong");
  const body = document.createElement("div");

  heading.className = "history-detail-title";
  heading.textContent = title;
  body.className = "pg-output-block";
  body.textContent = text || "[empty]";

  wrapper.appendChild(heading);
  wrapper.appendChild(body);
  pgResult.appendChild(wrapper);
}

function renderConsensusResult(data) {
  clearPlaygroundResult();

  const meta = document.createElement("div");
  const lines = [`Consensus score: ${Number(data.consensus_score || 0).toFixed(3)}`];
  if (typeof data.weighted_score === "number") {
    lines.push(`Weighted score: ${data.weighted_score.toFixed(3)}`);
  }
  if (typeof data.total_rounds === "number") {
    lines.push(`Rounds: ${data.total_rounds}`);
  }
  meta.className = "pg-output-meta";
  meta.textContent = lines.join(" · ");
  pgResult.appendChild(meta);

  appendOutputBlock("Best Response", data.best_response || "");
}

function renderDebateResult(data) {
  clearPlaygroundResult();
  appendOutputBlock("Improved Response", data.improved_response || "");
  appendOutputBlock("Initial Position", data.initial_position || "");
  appendOutputBlock("Challenge", data.challenge || "");
  appendOutputBlock("Defense", data.defense || "");
}

function renderCompareResult(data) {
  clearPlaygroundResult(false);

  const meta = document.createElement("div");
  meta.className = "pg-output-meta";
  meta.textContent = `Models: ${data.total_models || 0} · Succeeded: ${data.succeeded || 0} · Failed: ${data.failed || 0}`;
  pgResult.appendChild(meta);

  const table = document.createElement("table");
  table.className = "pg-output-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  ["Model", "Status", "Answer"].forEach((label) => {
    const cell = document.createElement("th");
    cell.textContent = label;
    headRow.appendChild(cell);
  });
  thead.appendChild(headRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  (Array.isArray(data.answers) ? data.answers : []).forEach((answer) => {
    const row = document.createElement("tr");

    const modelCell = document.createElement("td");
    modelCell.textContent = answer.model_id || "";
    row.appendChild(modelCell);

    const statusCell = document.createElement("td");
    statusCell.textContent = answer.status || "unknown";
    row.appendChild(statusCell);

    const answerCell = document.createElement("td");
    answerCell.className = "pg-output-answer";
    answerCell.textContent = answer.answer || "[empty]";
    row.appendChild(answerCell);

    tbody.appendChild(row);
  });
  table.appendChild(tbody);
  pgResult.appendChild(table);

  if (data.analysis) {
    appendOutputBlock("Analysis", data.analysis);
  }
}

async function streamPlayground(body, onChunk) {
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
      if (eventName === "delta") {
        onChunk(payload.text || "");
      } else if (eventName === "complete") {
        finalEvent = payload;
      } else if (eventName === "error") {
        throw new Error(payload.text || payload.detail || "Stream error");
      }
    }
  }

  return finalEvent;
}

document.getElementById("pg-rounds").addEventListener("input", (event) => {
  document.getElementById("pg-rounds-val").textContent = event.target.value;
});

pgPatternSel.addEventListener("change", togglePlaygroundOptions);

pgSubmitBtn.addEventListener("click", async () => {
  const prompt = pgPrompt.value.trim();
  if (!prompt || pgSubmitBtn.disabled) {
    return;
  }

  const pattern = pgPatternSel.value;
  const model = pgModelSel.value;
  const reasoning = pgReasoning.checked;
  const dryRun = pgDryRun.checked;

  pgSubmitBtn.disabled = true;
  setPlaygroundText("Running...");

  try {
    if (pattern === "single") {
      let streamedText = "";
      setPlaygroundText("");
      const finalEvent = await streamPlayground(
        {
          prompt,
          model,
          dry_run: dryRun,
          reasoning,
        },
        (chunk) => {
          streamedText += chunk;
          pgResult.textContent = streamedText;
        },
      );

      if (!streamedText && finalEvent?.text) {
        pgResult.textContent = finalEvent.text;
      }
      return;
    }

    if (pattern === "consensus") {
      const rounds = Number.parseInt(document.getElementById("pg-rounds").value, 10) || 3;
      const data = await window.api.post("/api/v1/consensus", {
        prompt,
        model,
        max_rounds: rounds,
      });
      renderConsensusResult(data);
      return;
    }

    if (pattern === "debate") {
      const data = await window.api.post("/api/v1/debate", {
        topic: prompt,
        model,
      });
      renderDebateResult(data);
      return;
    }

    const models = Array.from(pgCompareModels.selectedOptions).map((option) => option.value);
    const data = await window.api.post("/api/v1/compare", {
      prompt,
      models: models.length ? models : [model],
      analyze: document.getElementById("pg-analyze").checked,
    });
    renderCompareResult(data);
  } catch (error) {
    setPlaygroundText(`Error: ${error instanceof Error ? error.message : String(error)}`);
  } finally {
    pgSubmitBtn.disabled = false;
  }
});

syncPlaygroundModelsFromShell();
togglePlaygroundOptions();
