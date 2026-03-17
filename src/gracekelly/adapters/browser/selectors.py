from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PerplexitySelectors:
    prompt_input: str = 'div#ask-input[role="textbox"][contenteditable="true"]'
    model_button: str = 'button[aria-label="Model"]'
    submit_button: str = 'button[aria-label="Submit"]'
    add_files_button: str = 'button[aria-label="Add files or tools"]'
    dictation_button: str = 'button[aria-label="Dictation"]'
    response_candidates: tuple[str, ...] = (
        "main article",
        'main [data-message-author-role="assistant"]',
        "main div.prose",
        'main [class*="prose"]',
    )
    model_menu_candidates: tuple[str, ...] = (
        '[data-radix-popper-content-wrapper]',
        '[role="dialog"]',
        '[role="listbox"]',
    )
    ready_markers: tuple[str, ...] = (
        "Type @ for connectors and sources",
        "Type / for search modes",
        "Model",
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
            "Model",
            "Add files or tools",
            "Dictation",
            "Use voice mode",
            "Try Computer",
            "Necessary Cookies",
            "Accept All Cookies",
            "Sign in or create an account",
            "Continue with Google",
            "Continue with Apple",
            "Single sign-on (SSO)",
        )
    )
    cookie_button_names: tuple[str, ...] = ("Accept All Cookies", "Necessary Cookies")
