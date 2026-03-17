from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class PopupPolicy:
    dismissible_titles: tuple[str, ...] = ("Cookie Policy", "Sign in", "Upgrade")
    escape_key_retries: int = 2


@dataclass(frozen=True, slots=True)
class AuthRecoveryPolicy:
    allow_relogin: bool = False
    max_session_retries: int = 1
    treat_unknown_login_state_as_logged_out: bool = True


@dataclass(frozen=True, slots=True)
class ModelVerificationPolicy:
    allow_alias_match: bool = True
    wait_attempts: int = 5
    verify_button_label: bool = True


@dataclass(frozen=True, slots=True)
class SubmitPolicy:
    click_attempts: int = 3
    allow_js_fallback: bool = True
    blocked_overlay_markers: tuple[str, ...] = field(
        default_factory=lambda: ("animate-in", "fixed", "intercepts pointer events")
    )
