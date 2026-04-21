const PATTERNS = [
  {
    category: "Поиск",
    items: [
      { id: "sonar", label: "Sonar", icon: "search", pattern: "sonar", model: null, meta: "Поиск с быстрым ответом" },
      { id: "best", label: "Best", icon: "star", pattern: "sonar", model: "best", meta: "Поиск с приоритетом качества" },
    ],
  },
  {
    category: "1 модель",
    items: [
      { id: "single-claude", label: "Claude", icon: "flash", pattern: "single", model: "claude-sonnet-4-6", match: "claude", meta: "Один сильный ответ" },
      { id: "single-gpt", label: "GPT", icon: "chip", pattern: "single", model: "gpt-4o", match: "gpt", meta: "Быстрая универсальная модель" },
      { id: "single-gemini", label: "Gemini", icon: "spark", pattern: "single", model: "gemini-2-5-pro", match: "gemini", meta: "Длинный контекст" },
      { id: "single-kimi", label: "Kimi", icon: "moon", pattern: "single", model: "kimi-k2", match: "kimi", meta: "Альтернативный single route" },
    ],
  },
  {
    category: "2 модели",
    items: [
      { id: "dual-cg", label: "Claude + GPT", icon: "merge", pattern: "compare", models: ["claude-sonnet-4-6", "gpt-4o"], match: ["claude", "gpt"], meta: "Сравнить два ответа" },
      { id: "dual-cgm", label: "Claude + Gemini", icon: "merge", pattern: "compare", models: ["claude-sonnet-4-6", "gemini-2-5-pro"], match: ["claude", "gemini"], meta: "Два сильных мнения" },
    ],
  },
  {
    category: "Мульти",
    items: [
      { id: "consensus", label: "Consensus", icon: "target", pattern: "consensus", model: null, meta: "Свести ответы к консенсусу" },
      { id: "debate", label: "Debate", icon: "swords", pattern: "debate", model: null, meta: "Столкнуть позиции" },
      { id: "smart", label: "Smart", icon: "brain", pattern: "smart", model: null, meta: "Автовыбор маршрута" },
    ],
  },
];

const ICONS = {
  search: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"></circle><path d="m20 20-3.5-3.5"></path></svg>',
  star: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.4 6.4 20.2l1.1-6.2L3 9.6l6.2-.9L12 3z"></path></svg>',
  flash: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M13 2 4 13h6l-1 9 9-11h-6l1-9z"></path></svg>',
  chip: '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="7" width="10" height="10" rx="2"></rect><path d="M9 1v3M15 1v3M9 20v3M15 20v3M1 9h3M1 15h3M20 9h3M20 15h3"></path></svg>',
  spark: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2v4M12 18v4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M2 12h4M18 12h4M4.9 19.1l2.8-2.8M16.3 7.7l2.8-2.8"></path><circle cx="12" cy="12" r="3"></circle></svg>',
  moon: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"></path></svg>',
  merge: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="5" r="2"></circle><circle cx="18" cy="5" r="2"></circle><circle cx="12" cy="19" r="2"></circle><path d="M6 7c0 5 3.2 8.3 6 10M18 7c0 5-3.2 8.3-6 10"></path></svg>',
  target: '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><circle cx="12" cy="12" r="5"></circle><circle cx="12" cy="12" r="1.5"></circle></svg>',
  swords: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m6 4 5 5M13 11l7-7M8 14l-4 4M10 16l3 3M5 19l4-4M14 10l5 5"></path></svg>',
  brain: '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 4a3 3 0 0 0-3 3v1a2.5 2.5 0 0 0 0 5v1a3 3 0 0 0 3 3h1v-4H8m7-9a3 3 0 0 1 3 3v1a2.5 2.5 0 0 1 0 5v1a3 3 0 0 1-3 3h-1v-4h2M12 4v16"></path></svg>',
};

class ModelChipMenu {
  constructor() {
    this.container = document.getElementById("model-selector");
    this.currentItem = PATTERNS[1].items[0];
    this.availableModels = [];
    if (!this.container) {
      return;
    }

    this._ensureShell();
    this._ensureSupportNodes();
    this.popup = document.getElementById("model-popup");
    this.trigger = document.getElementById("model-trigger");
    this.label = document.getElementById("model-trigger-label");

    this._build();
    this._bind();
    this._updateTrigger();
  }

  _ensureShell() {
    if (this.container.querySelector("#model-trigger") && this.container.querySelector("#model-popup")) {
      return;
    }

    this.container.innerHTML = `
      <button class="model-trigger" id="model-trigger" type="button" title="Выбрать модель">
        <span class="model-trigger-label" id="model-trigger-label"></span>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M7 10l5 5 5-5"></path>
        </svg>
      </button>
      <div class="model-popup hidden" id="model-popup"></div>
    `;
  }

  _ensureSupportNodes() {
    if (!document.getElementById("model-select")) {
      const select = document.createElement("select");
      select.id = "model-select";
      select.className = "hidden";
      select.setAttribute("aria-hidden", "true");
      select.tabIndex = -1;
      this.container.appendChild(select);
    }

    if (!document.getElementById("model-banner")) {
      const banner = document.createElement("div");
      const chatArea = document.getElementById("chat-area") || document.getElementById("chat-messages");
      const parent = chatArea?.parentElement;

      banner.id = "model-banner";
      banner.className = "model-banner hidden";
      if (parent && chatArea) {
        parent.insertBefore(banner, chatArea);
      }
    }
  }

  _build() {
    this.popup.innerHTML = "";

    PATTERNS.forEach((group) => {
      const category = document.createElement("div");
      category.className = "popup-category";
      category.textContent = group.category;
      this.popup.appendChild(category);

      group.items.forEach((item) => {
        const element = document.createElement("div");
        const icon = document.createElement("span");
        const copy = document.createElement("div");
        const label = document.createElement("span");
        const meta = document.createElement("span");

        element.className = "popup-item";
        element.dataset.id = item.id;
        icon.className = "popup-icon";
        icon.innerHTML = ICONS[item.icon] || ICONS.chip;

        copy.className = "popup-copy";
        label.className = "popup-label";
        label.textContent = item.label;
        meta.className = "popup-meta";
        meta.textContent = item.meta || "";

        copy.appendChild(label);
        copy.appendChild(meta);
        element.appendChild(icon);
        element.appendChild(copy);
        element.addEventListener("click", () => this.select(item));
        this.popup.appendChild(element);
      });
    });
  }

  _bind() {
    this.trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      this.popup.classList.toggle("hidden");
    });

    this.popup.addEventListener("click", (event) => {
      event.stopPropagation();
    });

    document.addEventListener("click", () => {
      this.popup.classList.add("hidden");
    });
  }

  _normalizeModelEntry(model) {
    if (typeof model === "string") {
      return {
        id: model,
        label: model,
        haystack: model.toLowerCase(),
      };
    }

    const id = model?.model_id || model?.id || "";
    const label = model?.display_name || id;
    return {
      id,
      label,
      haystack: `${id} ${label}`.toLowerCase(),
    };
  }

  _catalogTokens(model) {
    if (typeof model === "string") {
      return [model];
    }

    const aliases = Array.isArray(model?.aliases) ? model.aliases : [];
    return [
      model?.id,
      model?.model_id,
      model?.display_name,
      ...aliases,
    ].filter(Boolean);
  }

  _syncWindowModelCatalog() {
    const currentCatalog = window.modelCatalog;
    if (!currentCatalog || currentCatalog.unavailable) {
      return;
    }

    const ids = new Set(currentCatalog.ids instanceof Set ? Array.from(currentCatalog.ids) : []);
    this.availableModels.forEach((model) => {
      this._catalogTokens(model).forEach((token) => ids.add(String(token).trim()));
    });

    window.modelCatalog = {
      ...currentCatalog,
      items: this.availableModels,
      ids,
    };
  }

  _resolveSingleMatch(match, fallback) {
    if (!Array.isArray(this.availableModels) || !this.availableModels.length) {
      return fallback || null;
    }

    const entries = this.availableModels
      .map((model) => this._normalizeModelEntry(model))
      .filter((model) => model.id);

    const exactNeedle = String(fallback || "").toLowerCase();
    const matchNeedle = String(match || "").toLowerCase();

    const exact = entries.find((model) => model.id.toLowerCase() === exactNeedle);
    if (exact) {
      return exact.id;
    }

    const fuzzy = entries.find((model) => model.haystack.includes(matchNeedle));
    return fuzzy ? fuzzy.id : fallback || null;
  }

  _resolveItem(item) {
    if (Array.isArray(item.models)) {
      return {
        ...item,
        resolvedModels: item.models.map((model, index) => this._resolveSingleMatch(item.match?.[index], model)),
      };
    }

    return {
      ...item,
      resolvedModel: this._resolveSingleMatch(item.match, item.model),
    };
  }

  _resolvedCurrentItem() {
    return this._resolveItem(this.currentItem);
  }

  _updateTrigger() {
    const current = this._resolvedCurrentItem();
    this.label.innerHTML = `${ICONS[current.icon] || ICONS.chip}<span>${current.label}</span>`;

    this.popup.querySelectorAll(".popup-item").forEach((element) => {
      element.classList.toggle("active", element.dataset.id === this.currentItem.id);
    });
  }

  _emitSelection() {
    window.dispatchEvent(
      new CustomEvent("modelmenu:change", {
        detail: this.getSelection(),
      }),
    );
  }

  select(item) {
    this.currentItem = item;
    this._updateTrigger();
    this.popup.classList.add("hidden");
    this._emitSelection();
  }

  setAvailableModels(models) {
    this.availableModels = Array.isArray(models) ? models : [];
    this._syncWindowModelCatalog();
    this._updateTrigger();
    this._emitSelection();
  }

  getSelection() {
    const current = this._resolvedCurrentItem();
    return {
      id: current.id,
      label: current.label,
      icon: current.icon,
      pattern: current.pattern,
      model: current.resolvedModel || null,
      models: current.resolvedModels || null,
    };
  }
}

window.modelMenu = new ModelChipMenu();
