const API_BASE = "";
const AUTH_REQUIRED_CODE = "model_auth_required";
const AUTH_REQUIRED_MESSAGE = "Perplexity session expired — open perplexity.ai and sign in, then retry";

async function readResponseBody(response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text);
  } catch (_error) {
    return text;
  }
}

function getAuthRequiredDetail(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    return null;
  }

  const detail = payload.detail && typeof payload.detail === "object" ? payload.detail : null;
  const error = payload.error && typeof payload.error === "object" ? payload.error : null;
  const code = payload.code || detail?.code || error?.code;
  const failureCode = payload.failure_code || error?.failure_code;

  if (code !== AUTH_REQUIRED_CODE && failureCode !== "auth_failed") {
    return null;
  }

  return {
    message: payload.message || payload.failure_message || detail?.message || error?.message || AUTH_REQUIRED_MESSAGE,
    trace_id: payload.trace_id || detail?.trace_id || error?.trace_id || payload.metadata?.trace_id || null,
    retry: null,
  };
}

function emitAuthRequired(payload) {
  const detail = getAuthRequiredDetail(payload);
  if (!detail) {
    return null;
  }
  window.dispatchEvent(new CustomEvent("auth:required", { detail }));
  return detail;
}

window.api = {
  async get(path) {
    const response = await fetch(API_BASE + path);
    const payload = await readResponseBody(response);
    if (!response.ok) {
      const authDetail = emitAuthRequired(payload);
      const error = new Error(`${response.status}: ${typeof payload === "string" ? payload : JSON.stringify(payload)}`);
      if (authDetail) {
        error.authRequired = true;
      }
      throw error;
    }
    emitAuthRequired(payload);
    return payload;
  },

  async post(path, body) {
    const response = await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const payload = await readResponseBody(response);
    if (!response.ok) {
      const authDetail = emitAuthRequired(payload);
      const error = new Error(`${response.status}: ${typeof payload === "string" ? payload : JSON.stringify(payload)}`);
      if (authDetail) {
        error.authRequired = true;
      }
      throw error;
    }
    emitAuthRequired(payload);
    return payload;
  },

  async postForm(path, formData) {
    const response = await fetch(API_BASE + path, {
      method: "POST",
      body: formData,
    });
    const payload = await readResponseBody(response);
    if (!response.ok) {
      const authDetail = emitAuthRequired(payload);
      const error = new Error(`${response.status}: ${typeof payload === "string" ? payload : JSON.stringify(payload)}`);
      if (authDetail) {
        error.authRequired = true;
      }
      throw error;
    }
    emitAuthRequired(payload);
    return payload;
  },

  async stream(path, body, onChunk) {
    const response = await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error(`${response.status}: ${await response.text()}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let finalResult = null;

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data: ")) {
          continue;
        }
        const event = JSON.parse(line.slice(6));
        if (event.type === "delta" && event.text) {
          onChunk(event.text);
        }
        if (event.type === "complete") {
          finalResult = event;
        }
        if (event.type === "error") {
          throw new Error(event.detail || "Stream error");
        }
      }
    }

    return finalResult;
  },

  async health() {
    const candidates = ["/api/v1/health", "/health"];
    for (const path of candidates) {
      try {
        return await this.get(path);
      } catch (_error) {
      }
    }
    return null;
  },

  async models() {
    const data = await this.get("/api/v1/models");
    return data.models || data;
  },

  async tasks(limit = 20) {
    const data = await this.get(`/api/v1/tasks?limit=${limit}`);
    return data.items || data;
  },
  authRequiredMessage: AUTH_REQUIRED_MESSAGE,
};
