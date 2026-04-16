const THREADS_KEY = "gk_threads";
const CURRENT_THREAD_KEY = "gk_current_thread";
const DEFAULT_THREAD_TITLE = "Новый диалог";

function getThreadListContainer() {
  return document.getElementById("thread-list") || document.getElementById("history-list");
}

function formatThreadDate(value) {
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

function makeThreadTitle(content) {
  const normalized = String(content || "").trim().replace(/\s+/g, " ");
  if (!normalized) {
    return DEFAULT_THREAD_TITLE;
  }

  return normalized.length > 50 ? `${normalized.slice(0, 50)}...` : normalized;
}

class ThreadManager {
  constructor() {
    this._threads = this._load();
    this._currentId = localStorage.getItem(CURRENT_THREAD_KEY) || null;

    if (!this._threads.length || !this._findById(this._currentId)) {
      const thread = this._create();
      this._currentId = thread.id;
      this._saveCurrentId();
    }

    this.render();
    this._emitChange();
  }

  _load() {
    try {
      const parsed = JSON.parse(localStorage.getItem(THREADS_KEY) || "[]");
      return Array.isArray(parsed) ? parsed : [];
    } catch (_error) {
      return [];
    }
  }

  _save() {
    localStorage.setItem(THREADS_KEY, JSON.stringify(this._threads));
  }

  _saveCurrentId() {
    localStorage.setItem(CURRENT_THREAD_KEY, this._currentId || "");
  }

  _findById(id) {
    if (!id) {
      return null;
    }

    return this._threads.find((thread) => thread.id === id) || null;
  }

  _create(title = DEFAULT_THREAD_TITLE) {
    const now = new Date().toISOString();
    const thread = {
      id: crypto.randomUUID(),
      title,
      created_at: now,
      updated_at: now,
      messages: [],
    };

    this._threads.unshift(thread);
    this._save();
    return thread;
  }

  _touch(thread) {
    thread.updated_at = new Date().toISOString();
    this._threads = [thread, ...this._threads.filter((item) => item.id !== thread.id)];
  }

  _emitChange() {
    window.dispatchEvent(
      new CustomEvent("threads:changed", {
        detail: {
          currentId: this._currentId,
          current: this.current,
          threads: this.list(),
        },
      }),
    );
  }

  list() {
    return this._threads.slice();
  }

  get current() {
    return this._findById(this._currentId);
  }

  get currentId() {
    return this._currentId;
  }

  getMessages() {
    const messages = this.current?.messages;
    return Array.isArray(messages) ? messages.slice() : [];
  }

  newThread() {
    const thread = this._create();
    this._currentId = thread.id;
    this._saveCurrentId();
    this.render();
    this.renderCurrent();
    this._emitChange();
    return thread;
  }

  switchTo(id) {
    const thread = this._findById(id);
    if (!thread) {
      return null;
    }

    this._currentId = thread.id;
    this._saveCurrentId();
    this.render();
    this.renderCurrent();
    this._emitChange();
    return thread;
  }

  addMessage(role, content, meta = null) {
    const thread = this.current || this.newThread();
    if (!thread) {
      return null;
    }

    thread.messages.push({ role, content, meta });

    if (
      role === "user"
      && thread.title === DEFAULT_THREAD_TITLE
      && thread.messages.filter((message) => message.role === "user").length === 1
    ) {
      thread.title = makeThreadTitle(content);
    }

    this._touch(thread);
    this._save();
    this.render();
    this._emitChange();
    return thread;
  }

  renderCurrent() {
    if (typeof window.renderThreadMessages === "function") {
      window.renderThreadMessages(this.getMessages());
    }
  }

  render() {
    const container = getThreadListContainer();
    if (!container) {
      return;
    }

    container.replaceChildren();

    if (!this._threads.length) {
      const empty = document.createElement("div");
      empty.className = "thread-empty";
      empty.textContent = "История появится после первого запроса.";
      container.appendChild(empty);
      return;
    }

    this._threads.forEach((thread) => {
      const item = document.createElement("button");
      const title = document.createElement("span");
      const meta = document.createElement("span");

      item.type = "button";
      item.className = "thread-item";
      item.dataset.threadId = thread.id;
      item.classList.toggle("active", thread.id === this._currentId);

      title.className = "thread-title";
      title.textContent = thread.title || DEFAULT_THREAD_TITLE;

      meta.className = "thread-meta";
      meta.textContent = formatThreadDate(thread.updated_at || thread.created_at);

      item.appendChild(title);
      item.appendChild(meta);
      item.addEventListener("click", () => {
        this.switchTo(thread.id);
      });

      container.appendChild(item);
    });
  }
}

window.threadManager = new ThreadManager();
