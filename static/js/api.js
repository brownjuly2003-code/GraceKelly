const API_BASE = "";

window.api = {
  async get(path) {
    const response = await fetch(API_BASE + path);
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return response.json();
  },

  async post(path, body) {
    const response = await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      throw new Error(`${response.status}: ${await response.text()}`);
    }
    return response.json();
  },

  async postForm(path, formData) {
    const response = await fetch(API_BASE + path, {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      throw new Error(`${response.status}: ${await response.text()}`);
    }
    return response.json();
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
};
