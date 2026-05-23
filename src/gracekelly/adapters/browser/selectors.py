from __future__ import annotations

from dataclasses import dataclass, field

_KNOWN_MODEL_LABELS: tuple[str, ...] = (
    "Best",
    "Claude Sonnet 4.6",
    "GPT-5.4",
    "Gemini 3.1 Pro",
    "Kimi K2.6",
    "Nemotron 3 Super",
    "Sonar 2",
)
_MODEL_BUTTON_SELECTOR = ", ".join(
    ", ".join(
        (
            f'div[data-ask-input-container="true"] button[aria-label="{label}"]',
            f'div[data-ask-input-container="true"] button[aria-label^="{label} "]',
        )
    )
    for label in _KNOWN_MODEL_LABELS
)


# 2026-05-18 Perplexity regression: the model picker button aria-label can be the
# current model label, while the Mode picker is also an aria-haspopup menu button.
@dataclass(frozen=True, slots=True)
class PerplexitySelectors:
    known_model_labels: tuple[str, ...] = _KNOWN_MODEL_LABELS
    prompt_input: str = 'div#ask-input[role="textbox"][contenteditable="true"]'
    model_button: str = _MODEL_BUTTON_SELECTOR
    composer_model_button: str = (
        'div[data-ask-input-container="true"] button[aria-haspopup="menu"]'
        ':not([aria-label="Add files or tools"])'
        ':not([aria-label="More"])'
        ':not([aria-label*="Search" i])'
        ':not([aria-label="Mode" i])'
        ':not([aria-label="Search"])'
        ':not(:has-text("Search"))'
    )
    more_button: str = 'button[aria-label="More"]'
    submit_button: str = 'button[aria-label="Submit"]'
    stop_response_button: str = 'button[aria-label^="Stop response"]'
    add_files_button: str = 'button[aria-label="Add files or tools"]'
    dictation_button: str = 'button[aria-label="Dictation"]'
    response_candidates: tuple[str, ...] = (
        'main [data-message-author-role="assistant"]',
        "main article",
        "main div.prose",
        'main [class*="prose"]',
    )
    model_menu_candidates: tuple[str, ...] = (
        '[data-radix-popper-content-wrapper]',
        '[role="dialog"]',
        '[role="listbox"]',
        '[role="menu"]',
    )
    model_menu_item_selector: str = '[role="menuitemradio"], [role="menuitem"], [role="option"], button'
    ready_markers: tuple[str, ...] = (
        "Type @ for connectors and sources",
        "Type / for search modes",
    )
    signed_out_markers: tuple[str, ...] = (
        "Sign in or create an account",
        "Continue with Google",
        "Continue with Apple",
        "Single sign-on (SSO)",
    )
    shell_noise_lines: tuple[str, ...] = field(
        default_factory=lambda: (
            "Search",
            "Pro Search",
            "Deep Research",
            "Labs",
            "Computer",
            "New Thread",
            "Ctrl I",
            "History",
            "Discover",
            "Spaces",
            "Finance",
            "More",
            "Recent",
            "Type @ for connectors and sources",
            "Type / for search modes",
            "Add files or tools",
            "Dictation",
            "Use voice mode",
            "Try Computer",
            "Set up Computer",
            "Computer can run LLM evals, compare APIs, and write up what changed",
            "Connect your apps",
            "Create your first task",
            "Turn on notifications",
            "Necessary Cookies",
            "Accept All Cookies",
            "Sign in or create an account",
            "Continue with Google",
            "Continue with Apple",
            "Single sign-on (SSO)",
            "Thinking",
            "Ask a follow-up",
            "Stop response",
            "Regenerate",
            "Sources",
            "Answer",
        )
    )
    cookie_button_names: tuple[str, ...] = ("Accept All Cookies", "Necessary Cookies")
    new_thread_button_names: tuple[str, ...] = ("New Thread",)
