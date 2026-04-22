const MENU_GROUPS = [
  {
    title: "",
    items: [
      {
        id: "sonar",
        pattern: "sonar",
        label: "Sonar",
        desc: "быстрый поиск без reasoning",
        icon: "search",
        model: "sonar",
        match: "sonar",
      },
      {
        id: "best",
        pattern: "single",
        label: "Best",
        desc: "оркестрация Perplexity",
        icon: "search",
        model: "best",
        match: "best",
      },
    ],
  },
  {
    title: "1 модель",
    items: [
      {
        id: "claude",
        pattern: "single",
        label: "Claude 4.6",
        desc: "reasoning",
        icon: "flash",
        model: "claude-sonnet-4-6",
        match: "claude",
      },
      {
        id: "gpt",
        pattern: "single",
        label: "GPT-5.4",
        desc: "reasoning",
        icon: "flash",
        model: "gpt-5-4",
        match: "gpt",
      },
      {
        id: "gemini",
        pattern: "single",
        label: "Gemini 3.1",
        desc: "reasoning",
        icon: "flash",
        model: "gemini-3-1-pro",
        match: "gemini",
      },
      {
        id: "kimi",
        pattern: "single",
        label: "Kimi K2.5",
        desc: "reasoning",
        icon: "flash",
        model: "kimi-k2-5",
        match: "kimi",
      },
    ],
  },
  {
    title: "Авто",
    items: [
      {
        id: "debate",
        pattern: "debate",
        label: "Дебаты",
        desc: "Devil's Advocate",
        icon: "merge",
        pinned_model: "claude-sonnet-4-6",
      },
      {
        id: "smart",
        pattern: "smart",
        label: "Умный выбор",
        desc: "авто-декомпозиция",
        icon: "target",
        pinned_model: "claude-sonnet-4-6",
      },
    ],
  },
  {
    title: "2 модели",
    items: [
      {
        id: "claude+gpt",
        pattern: "dual",
        label: "Claude + GPT",
        desc: "параллельно",
        icon: "merge",
        matches: ["claude", "gpt"],
        models: ["claude-sonnet-4-6", "gpt-5-4"],
        recommended: true,
      },
      {
        id: "claude+gemini",
        pattern: "dual",
        label: "Claude + Gemini",
        desc: "параллельно",
        icon: "merge",
        matches: ["claude", "gemini"],
        models: ["claude-sonnet-4-6", "gemini-3-1-pro"],
      },
      {
        id: "claude+best",
        pattern: "dual",
        label: "Claude + Best",
        desc: "параллельно",
        icon: "merge",
        matches: ["claude", "best"],
        models: ["claude-sonnet-4-6", "best"],
      },
      {
        id: "gpt+best",
        pattern: "dual",
        label: "GPT + Best",
        desc: "параллельно",
        icon: "merge",
        matches: ["gpt", "best"],
        models: ["gpt-5-4", "best"],
      },
    ],
  },
  {
    title: "5 моделей",
    items: [
      {
        id: "five_models",
        pattern: "five_models",
        label: "5М.Все мнения",
        desc: "без анализа",
        icon: "cpu",
        analyze: false,
        strategy: "all",
      },
      {
        id: "five_models_compare",
        pattern: "five_models_compare",
        label: "5М.Сравнение",
        desc: "5 + Analyzer",
        icon: "cpu",
        analyze: true,
        strategy: "all",
        recommended: true,
      },
      {
        id: "maximum",
        pattern: "maximum",
        label: "5М.Консенсус",
        desc: "5 × 3 параллельно",
        icon: "target",
        analyze: true,
        strategy: "all",
      },
    ],
  },
];

const MODEL_PRIORITY = [
  { match: "best", fallback: "best" },
  { match: "claude", fallback: "claude-sonnet-4-6" },
  { match: "gpt", fallback: "gpt-5-4" },
  { match: "gemini", fallback: "gemini-3-1-pro" },
  { match: "kimi", fallback: "kimi-k2-5" },
  { match: "max", fallback: "max" },
  { match: "nemotron", fallback: "nemotron-3-super" },
  { match: "opus", fallback: "claude-opus-4-7" },
];

const ICONS = {
  chip: `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="6" y="6" width="12" height="12" rx="2"></rect>
    <line x1="7" y1="4" x2="7" y2="6"></line>
    <line x1="10" y1="4" x2="10" y2="6"></line>
    <line x1="14" y1="4" x2="14" y2="6"></line>
    <line x1="17" y1="4" x2="17" y2="6"></line>
    <line x1="7" y1="18" x2="7" y2="20"></line>
    <line x1="10" y1="18" x2="10" y2="20"></line>
    <line x1="14" y1="18" x2="14" y2="20"></line>
    <line x1="17" y1="18" x2="17" y2="20"></line>
    <line x1="4" y1="7" x2="6" y2="7"></line>
    <line x1="4" y1="10" x2="6" y2="10"></line>
    <line x1="4" y1="14" x2="6" y2="14"></line>
    <line x1="4" y1="17" x2="6" y2="17"></line>
    <line x1="18" y1="7" x2="20" y2="7"></line>
    <line x1="18" y1="10" x2="20" y2="10"></line>
    <line x1="18" y1="14" x2="20" y2="14"></line>
    <line x1="18" y1="17" x2="20" y2="17"></line>
  </svg>`,
  search: `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="11" cy="11" r="8"></circle>
    <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
  </svg>`,
  flash: `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
  </svg>`,
  merge: `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="6" cy="4" r="3"></circle>
    <circle cx="18" cy="4" r="3"></circle>
    <circle cx="12" cy="20" r="3"></circle>
    <path d="M6 7C6 13 10 16 12 17"></path>
    <path d="M18 7C18 13 14 16 12 17"></path>
  </svg>`,
  target: `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <circle cx="12" cy="12" r="10"></circle>
    <circle cx="12" cy="12" r="6"></circle>
    <circle cx="12" cy="12" r="2"></circle>
  </svg>`,
  cpu: `<svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
    <rect x="4" y="4" width="16" height="16" rx="2"></rect>
    <rect x="9" y="9" width="6" height="6"></rect>
    <line x1="9" y1="1" x2="9" y2="4"></line>
    <line x1="15" y1="1" x2="15" y2="4"></line>
    <line x1="9" y1="20" x2="9" y2="23"></line>
    <line x1="15" y1="20" x2="15" y2="23"></line>
    <line x1="20" y1="9" x2="23" y2="9"></line>
    <line x1="20" y1="14" x2="23" y2="14"></line>
    <line x1="1" y1="9" x2="4" y2="9"></line>
    <line x1="1" y1="14" x2="4" y2="14"></line>
  </svg>`,
};

function normalizeModelEntry(model) {
  if (typeof model === "string") {
    return {
      id: model,
      label: model,
      haystack: model.toLowerCase(),
      aliases: [],
    };
  }

  const aliases = Array.isArray(model?.aliases) ? model.aliases.map((item) => String(item)) : [];
  const id = String(model?.model_id || model?.id || "");
  const label = String(model?.display_name || id);
  return {
    id,
    label,
    haystack: `${id} ${label} ${aliases.join(" ")}`.toLowerCase(),
    aliases,
  };
}

class ModelChipMenu {
  constructor() {
    this.container = document.getElementById("model-selector");
    this.availableModels = [];
    this.visibleItems = [];
    this.currentItemId = "claude+gpt";

    if (!this.container) {
      return;
    }

    this._ensureShell();
    this.trigger = document.getElementById("model-trigger");
    this.popup = document.getElementById("model-popup");
    this.select = document.getElementById("model-select");

    this._bind();
    this._build();
  }

  _ensureShell() {
    this.container.innerHTML = `
      <button class="model-trigger" id="model-trigger" type="button" title="Выбрать модель">
        ${ICONS.chip}
      </button>
      <div class="model-popup hidden" id="model-popup"></div>
      <select id="model-select" class="hidden" aria-hidden="true" tabindex="-1"></select>
    `;
  }

  _bind() {
    this.trigger?.addEventListener("click", (event) => {
      event.stopPropagation();
      this.popup?.classList.toggle("hidden");
    });

    document.addEventListener("click", (event) => {
      if (!this.container.contains(event.target)) {
        this.popup?.classList.add("hidden");
      }
    });
  }

  _resolveModel(match, fallback) {
    if (!this.availableModels.length) {
      return fallback || null;
    }

    const exactNeedle = String(fallback || "").toLowerCase();
    const fuzzyNeedle = String(match || "").toLowerCase();
    const entries = this.availableModels.map((model) => normalizeModelEntry(model)).filter((model) => model.id);

    const exact = entries.find((entry) => entry.id.toLowerCase() === exactNeedle);
    if (exact) {
      return exact.id;
    }

    const fuzzy = entries.find((entry) => entry.haystack.includes(fuzzyNeedle));
    return fuzzy ? fuzzy.id : null;
  }

  _resolveAllModels() {
    const resolved = [];
    for (const item of MODEL_PRIORITY) {
      const modelId = this._resolveModel(item.match, item.fallback);
      if (modelId && !resolved.includes(modelId)) {
        resolved.push(modelId);
        if (resolved.length >= 5) {
          break;
        }
      }
    }
    return resolved;
  }

  _resolveItem(item) {
    if (!item.match && !item.model && !item.strategy && !Array.isArray(item.matches)) {
      const pinnedModel = item.pinned_model
        ? this._resolveModel(item.pinned_model, item.pinned_model) || item.pinned_model
        : null;
      return {
        ...item,
        available: true,
        resolvedModel: pinnedModel,
        resolvedModels: null,
      };
    }

    if (item.strategy === "all") {
      const models = this._resolveAllModels();
      const available = this.availableModels.length === 0 || models.length >= 5;
      return {
        ...item,
        available,
        resolvedModel: null,
        resolvedModels: models,
      };
    }

    if (Array.isArray(item.matches)) {
      const models = item.matches
        .map((match, index) => this._resolveModel(match, item.models?.[index] || null))
        .filter(Boolean);
      const available = this.availableModels.length === 0 || models.length === item.matches.length;
      return {
        ...item,
        available,
        resolvedModel: null,
        resolvedModels: models,
      };
    }

    const modelId = this._resolveModel(item.match, item.model);
    const available = this.availableModels.length === 0 || Boolean(modelId);
    return {
      ...item,
      available,
      resolvedModel: modelId,
      resolvedModels: null,
    };
  }

  _resolveGroups() {
    return MENU_GROUPS.map((group) => {
      const items = group.items.map((item) => this._resolveItem(item)).filter((item) => item.available);
      return { title: group.title, items };
    }).filter((group) => group.items.length > 0);
  }

  _currentItem() {
    return this.visibleItems.find((item) => item.id === this.currentItemId) || this.visibleItems[0] || null;
  }

  _syncLegacySelect() {
    if (!this.select) {
      return;
    }

    const current = this._currentItem();
    const preferredModels = current?.resolvedModels || (current?.resolvedModel ? [current.resolvedModel] : []);
    const options = this._resolveAllModels();

    this.select.innerHTML = "";
    options.forEach((modelId) => {
      const option = document.createElement("option");
      option.value = modelId;
      option.textContent = modelId;
      this.select.appendChild(option);
    });

    if (preferredModels.length) {
      this.select.value = preferredModels[0];
    }
  }

  _build() {
    if (!this.popup) {
      return;
    }

    const groups = this._resolveGroups();
    this.visibleItems = groups.flatMap((group) => group.items);
    if (!this._currentItem()) {
      this.currentItemId = this.visibleItems[0]?.id || "";
    }

    this.popup.innerHTML = "";
    groups.forEach((group) => {
      const section = document.createElement("div");
      section.className = "model-section";

      if (group.title) {
        const title = document.createElement("div");
        title.className = "model-section-title";
        title.textContent = group.title;
        section.appendChild(title);
      }

      group.items.forEach((item) => {
        const element = document.createElement("div");
        const icon = document.createElement("div");
        const content = document.createElement("div");
        const label = document.createElement("div");
        const desc = document.createElement("div");

        element.className = "model-item";
        element.classList.toggle("selected", item.id === this.currentItemId);
        icon.className = "model-item-icon chip-icon";
        icon.innerHTML = ICONS[item.icon] || ICONS.chip;
        content.className = "model-item-content";
        label.className = "model-item-label";
        label.textContent = item.label;
        desc.className = "model-item-desc";
        desc.textContent = item.desc || "";

        content.appendChild(label);
        content.appendChild(desc);
        element.appendChild(icon);
        element.appendChild(content);

        if (item.recommended) {
          const badge = document.createElement("span");
          badge.className = "model-badge";
          badge.textContent = "HOT";
          element.appendChild(badge);
        }

        element.addEventListener("click", () => {
          this.currentItemId = item.id;
          this.popup.classList.add("hidden");
          this._build();
          this._emitSelection();
        });

        section.appendChild(element);
      });

      this.popup.appendChild(section);
    });

    const current = this._currentItem();
    if (this.trigger && current) {
      this.trigger.title = current.label;
    }
    this._syncLegacySelect();
  }

  _emitSelection() {
    window.dispatchEvent(
      new CustomEvent("modelmenu:change", {
        detail: this.getSelection(),
      }),
    );
  }

  setAvailableModels(models) {
    this.availableModels = Array.isArray(models) ? models : [];
    this._build();
    this._emitSelection();
  }

  getSelection() {
    const current = this._currentItem();
    if (!current) {
      return {
        id: "",
        label: "",
        icon: "chip",
        pattern: "single",
        model: null,
        models: null,
        analyze: true,
      };
    }

    return {
      id: current.id,
      label: current.label,
      icon: current.icon,
      pattern: current.pattern,
      model: current.resolvedModel || null,
      models: current.resolvedModels || null,
      analyze: current.analyze !== false,
    };
  }
}

window.modelMenu = new ModelChipMenu();
