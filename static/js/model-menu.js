const PATTERNS = [
  {
    category: "Поиск",
    items: [
      { id: "sonar", label: "Sonar", icon: "🔍", pattern: "sonar", model: null, meta: "Поиск с быстрым ответом" },
      { id: "best", label: "Best", icon: "⭐", pattern: "sonar", model: "best", meta: "Поиск с приоритетом качества" },
    ],
  },
  {
    category: "1 модель",
    items: [
      { id: "single-claude", label: "Claude", icon: "🟣", pattern: "single", model: "claude-sonnet-4-6", match: "claude", meta: "Один сильный ответ" },
      { id: "single-gpt", label: "GPT", icon: "🟢", pattern: "single", model: "gpt-4o", match: "gpt", meta: "Быстрая универсальная модель" },
      { id: "single-gemini", label: "Gemini", icon: "🔵", pattern: "single", model: "gemini-2-5-pro", match: "gemini", meta: "Длинный контекст" },
      { id: "single-kimi", label: "Kimi", icon: "🟡", pattern: "single", model: "kimi-k2", match: "kimi", meta: "Альтернативный single route" },
    ],
  },
  {
    category: "2 модели",
    items: [
      { id: "dual-cg", label: "Claude + GPT", icon: "⚡", pattern: "compare", models: ["claude-sonnet-4-6", "gpt-4o"], match: ["claude", "gpt"], meta: "Сравнить два ответа" },
      { id: "dual-cgm", label: "Claude + Gemini", icon: "⚡", pattern: "compare", models: ["claude-sonnet-4-6", "gemini-2-5-pro"], match: ["claude", "gemini"], meta: "Два сильных мнения" },
    ],
  },
  {
    category: "Мульти",
    items: [
      { id: "consensus", label: "Consensus", icon: "🤝", pattern: "consensus", model: null, meta: "Свести ответы к консенсусу" },
      { id: "debate", label: "Debate", icon: "⚔️", pattern: "debate", model: null, meta: "Столкнуть позиции" },
      { id: "smart", label: "Smart", icon: "🧠", pattern: "smart", model: null, meta: "Автовыбор маршрута" },
    ],
  },
];

class ModelChipMenu {
  constructor() {
    this.currentItem = PATTERNS[1].items[0];
    this.availableModels = [];
    this.popup = document.getElementById("model-popup");
    this.trigger = document.getElementById("model-trigger");
    this.label = document.getElementById("model-trigger-label");

    if (!this.popup || !this.trigger || !this.label) {
      return;
    }

    this._build();
    this._bind();
    this._updateTrigger();
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
        const copy = document.createElement("div");
        const label = document.createElement("span");
        const meta = document.createElement("span");

        element.className = "popup-item";
        element.dataset.id = item.id;

        const icon = document.createElement("span");
        icon.className = "popup-icon";
        icon.textContent = item.icon;

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
    this.label.textContent = `${current.icon} ${current.label}`;

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
