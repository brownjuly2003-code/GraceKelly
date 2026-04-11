from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from typing import Any

import requests  # type: ignore[import-untyped]
import streamlit as st
from requests import Response

from gracekelly.core.models import estimate_cost_usd

API_PREFIX = "/api/v1"
PATTERNS = ("single", "consensus", "debate", "compare")


def normalize_base_url(value: str) -> str:
    return value.rstrip("/")


def format_duration(duration_ms: Any) -> str:
    try:
        return f"{float(duration_ms) / 1000:.1f}s"
    except (TypeError, ValueError):
        return "n/a"


def format_task_label(task: dict[str, Any]) -> str:
    task_id = str(task.get("task_id", "unknown"))
    status = str(task.get("status", "unknown")).lower()
    mode = str(task.get("execution_mode", "task"))
    return f"{task_id[:8]} | {status} | {mode}"


def extract_error(response: Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return response.text.strip() or str(response.reason)
    detail = payload.get("detail") if isinstance(payload, dict) else payload
    if isinstance(detail, (dict, list)):
        return json.dumps(detail, ensure_ascii=False)
    return str(detail)


def request_json(method: str, base_url: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    url = f"{normalize_base_url(base_url)}{API_PREFIX}{path}"
    try:
        response = requests.request(method, url, json=payload, timeout=20)
    except requests.RequestException as exc:
        raise RuntimeError(f"Backend unreachable: {exc}") from exc
    if response.status_code >= 400:
        raise RuntimeError(f"API {response.status_code}: {extract_error(response)}")
    try:
        return response.json()
    except ValueError as exc:
        raise RuntimeError("API returned non-JSON response.") from exc


def stream_from_sse(base_url: str, path: str, payload: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    url = f"{normalize_base_url(base_url)}{API_PREFIX}{path}"
    try:
        with requests.post(url, json=payload, stream=True, timeout=120) as response:
            if response.status_code >= 400:
                raise RuntimeError(f"API {response.status_code}: {extract_error(response)}")
            event_type = ""
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith("event: "):
                    event_type = line[7:]
                elif line.startswith("data: "):
                    try:
                        data = json.loads(line[6:])
                    except (json.JSONDecodeError, ValueError):
                        continue
                    if isinstance(data, dict):
                        yield event_type, data
                        event_type = ""
    except requests.RequestException as exc:
        raise RuntimeError(f"Backend unreachable: {exc}") from exc


@st.cache_data(ttl=60, show_spinner=False)  # type: ignore[untyped-decorator]
def load_models(base_url: str) -> list[dict[str, Any]]:
    payload = request_json("GET", base_url, "/models")
    return payload if isinstance(payload, list) else []


@st.cache_data(ttl=30, show_spinner=False)  # type: ignore[untyped-decorator]
def load_tasks(base_url: str, limit: int = 20) -> list[dict[str, Any]]:
    payload = request_json("GET", base_url, f"/tasks?limit={limit}")
    return payload if isinstance(payload, list) else []


def remember_view(view_type: str, payload: Any) -> None:
    st.session_state["view_type"] = view_type
    st.session_state["view_payload"] = payload


def render_result_header(title: str, payload: dict[str, Any]) -> None:
    st.subheader(title)
    metrics = st.columns(4)
    metrics[0].metric("Status", str(payload.get("status", "n/a")))
    metrics[1].metric("Duration", format_duration(payload.get("duration_ms")))
    metrics[2].metric("Mode", str(payload.get("execution_mode", payload.get("pattern", "n/a"))))
    metrics[3].metric("Model", str(payload.get("model", "n/a")))


def render_single_result(payload: dict[str, Any]) -> None:
    render_result_header("Result", payload)
    requested_models = payload.get("requested_models") or []
    if requested_models:
        st.caption("Requested models: " + ", ".join(str(item) for item in requested_models))
    with st.container(border=True):
        st.markdown(payload.get("output_text") or "_No output returned._")
        tokens_text = ""
        if payload.get("input_tokens") or payload.get("output_tokens"):
            inp = payload.get("input_tokens", 0) or 0
            out = payload.get("output_tokens", 0) or 0
            tokens_text = f"Tokens: {inp:,} in / {out:,} out"
            cost = payload.get("cost_usd")
            if cost is not None:
                tokens_text += f" | ${cost:.4f}"
            st.caption(tokens_text)
    with st.expander("Copy output"):
        st.code(payload.get("output_text") or "", language="")


def render_consensus_result(payload: dict[str, Any]) -> None:
    st.subheader("Consensus")
    metrics = st.columns(4)
    metrics[0].metric("Score", f"{float(payload.get('consensus_score', 0)):.2f}")
    metrics[1].metric("Clusters", str(payload.get("num_clusters", "n/a")))
    metrics[2].metric("Weighted", f"{float(payload.get('weighted_score', 0)):.2f}")
    metrics[3].metric("Model", str(payload.get("model", "n/a")))
    with st.container(border=True):
        st.markdown(payload.get("best_response") or "_No response returned._")


def render_debate_result(payload: dict[str, Any]) -> None:
    st.subheader("Debate")
    metrics = st.columns(2)
    metrics[0].metric("Model", str(payload.get("model", "n/a")))
    metrics[1].metric("LLM calls", str(payload.get("total_llm_calls", "n/a")))
    sections = (
        ("Initial Position", payload.get("initial_position")),
        ("Challenge", payload.get("challenge")),
        ("Defense", payload.get("defense")),
        ("Improved Response", payload.get("improved_response")),
    )
    for title, body in sections:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.markdown(body or "_No content returned._")


def render_compare_result(payload: dict[str, Any]) -> None:
    st.subheader("Compare")
    metrics = st.columns(3)
    metrics[0].metric("Models", str(payload.get("total_models", "n/a")))
    metrics[1].metric("Succeeded", str(payload.get("succeeded", "n/a")))
    metrics[2].metric("Failed", str(payload.get("failed", "n/a")))
    answers = payload.get("answers") or []
    if answers:
        columns = st.columns(len(answers))
        for column, answer in zip(columns, answers):
            with column:
                with st.container(border=True):
                    st.markdown(f"**{answer.get('model_id', 'unknown')}**")
                    st.caption(str(answer.get("status", "n/a")))
                    st.markdown(answer.get("answer") or "_No answer returned._")
    if payload.get("analysis"):
        with st.container(border=True):
            st.markdown("**Analysis**")
            st.markdown(str(payload["analysis"]))


def render_task_view(payload: dict[str, Any]) -> None:
    render_result_header("Task View", payload)
    if payload.get("prompt"):
        with st.container(border=True):
            st.markdown("**Prompt**")
            st.markdown(str(payload["prompt"]))
    if payload.get("output_text"):
        with st.container(border=True):
            st.markdown("**Output**")
            st.markdown(str(payload["output_text"]))
    with st.expander("Copy output"):
        st.code(payload.get("output_text") or "", language="")
    steps = payload.get("steps") or []
    if steps:
        st.markdown("#### Steps")
        st.dataframe(
            [
                {
                    "model_id": step.get("model_id", "unknown"),
                    "status": step.get("status", "n/a"),
                    "duration": format_duration(step.get("duration_ms")),
                    "tokens": f"{step.get('input_tokens', 0) or 0}+{step.get('output_tokens', 0) or 0}",
                    "cost": f"${step.get('cost_usd', 0) or 0:.4f}",
                }
                for step in steps
            ],
            use_container_width=True,
            hide_index=True,
        )
        for index, step in enumerate(steps, start=1):
            with st.expander(f"Step {index}: {step.get('model_id', 'unknown')}"):
                st.markdown(step.get("output_text") or "_No output returned._")
    events = payload.get("events") or []
    if events:
        st.markdown("#### Events")
        st.json(events)


def _render_chat_export(messages: list[dict[str, Any]]) -> str:
    lines = ["# GraceKelly Chat Export", ""]
    for msg in messages:
        role = "**You**" if msg["role"] == "user" else "**GraceKelly**"
        lines.append(f"### {role}")
        lines.append("")
        lines.append(msg.get("content") or "")
        if msg["role"] == "assistant" and msg.get("meta"):
            meta = msg["meta"]
            parts = []
            if meta.get("model_id"):
                parts.append(str(meta["model_id"]))
            if meta.get("duration_ms"):
                parts.append(f"{meta['duration_ms']}ms")
            if parts:
                lines.append("")
                lines.append(f"_{' · '.join(parts)}_")
        lines.append("")
    return "\n".join(lines)


st.set_page_config(page_title="GraceKelly Playground", layout="wide")
st.markdown(
    """
    <style>
    :root {
        --ink: #1e1a17;
        --paper: #fff8ef;
        --wash: #f4eadf;
        --accent: #a0622f;
        --line: rgba(30, 26, 23, 0.14);
    }
    .stApp {
        color: var(--ink);
        background:
            radial-gradient(circle at top right, rgba(160, 98, 47, 0.18), transparent 32%),
            linear-gradient(180deg, var(--paper) 0%, var(--wash) 100%);
    }
    [data-testid="stSidebar"] {
        background: rgba(255, 250, 243, 0.94);
        border-right: 1px solid var(--line);
    }
    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }
    h1, h2, h3 {
        font-family: Georgia, "Times New Roman", serif;
        letter-spacing: -0.03em;
    }
    div[data-testid="stForm"] {
        background: rgba(255, 255, 255, 0.76);
        border: 1px solid var(--line);
        border-radius: 24px;
        padding: 1.25rem 1.25rem 0.5rem;
        box-shadow: 0 18px 45px rgba(30, 26, 23, 0.08);
    }
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 0.4rem 0.75rem;
    }
    button[kind="primary"] {
        border-radius: 999px;
        border: none;
        background: linear-gradient(135deg, #9a5828 0%, #c48a58 100%);
    }
    button[kind="secondary"] {
        border-radius: 999px;
    }
    [data-testid="stChatMessage"] {
        border-radius: 16px;
        margin-bottom: 0.5rem;
    }
    [data-testid="stVerticalBlock"] > div:has(> [data-testid="stContainer"]) {
        margin-top: 2rem;
    }
    .status-dot {
        font-size: 0.7rem;
        vertical-align: middle;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.session_state.setdefault("view_type", "empty")
st.session_state.setdefault("view_payload", {})
st.session_state.setdefault("backend_url", "http://localhost:8011")
st.session_state.setdefault("chat_messages", [])
st.session_state.setdefault("chat_retry_message", None)
st.session_state.setdefault("chat_last_failed_message", None)
st.session_state.setdefault("chat_session_id", str(uuid.uuid4()))
st.session_state.setdefault("last_models_date", "")

with st.sidebar:
    backend_url = st.session_state["backend_url"]
    _backend_ok = False
    try:
        _ping = requests.get(f"{backend_url}/health", timeout=2)
        _backend_ok = _ping.status_code == 200
    except Exception:
        _backend_ok = False
    _status_dot = "🟢" if _backend_ok else "🔴"
    st.markdown(f"## GraceKelly &nbsp; {_status_dot}", unsafe_allow_html=True)
    import datetime as _dt

    _today = _dt.date.today().isoformat()
    if st.session_state["last_models_date"] != _today:
        load_models.clear()
        load_tasks.clear()
        try:
            requests.post(f"{backend_url}/api/v1/models/refresh", timeout=5)
        except Exception:
            pass
        st.session_state["last_models_date"] = _today
    backend_url = st.text_input("Backend URL", value=st.session_state["backend_url"])
    st.session_state["backend_url"] = backend_url
    if st.button("Refresh data", use_container_width=True):
        load_models.clear()
        load_tasks.clear()

model_error = ""
model_items: list[dict[str, Any]] = []
model_options: list[str] = []
api_model_options: list[str] = []
model_labels: dict[str, str] = {}

try:
    model_items = load_models(backend_url)
except RuntimeError as exc:
    model_error = str(exc)
else:
    model_options = [str(item.get("id")) for item in model_items if item.get("id")]
    api_model_options = [
        str(item.get("id"))
        for item in model_items
        if item.get("id") and str(item.get("adapter_kind", "")) == "api"
    ]
    def _avail_badge(item: dict[str, Any]) -> str:
        status = str(item.get("availability_status") or "")
        if status == "observed_available":
            return " ✓"
        if status == "observed_unavailable":
            return " ✗"
        if item.get("adapter_kind") == "browser":
            return " ?"
        return ""

    model_labels = {
        str(item["id"]): (
            str(item.get("display_name") or item["id"])
            + _avail_badge(item)
            + "  ·  "
            + str(item.get("provider") or "")
        )
        for item in model_items
        if item.get("id")
    }

with st.sidebar:
    if model_error:
        st.error(model_error)
        st.caption("Models are unavailable, manual entry is enabled.")
    pattern = st.selectbox("Pattern", PATTERNS, index=0)
    selectable_model_options = model_options if pattern == "single" else api_model_options
    selected_model = ""
    selected_models: list[str] = []
    if pattern == "compare":
        if selectable_model_options:
            selected_models = st.multiselect(
                "Models",
                options=selectable_model_options,
                default=selectable_model_options[:2],
                format_func=lambda value: model_labels.get(value, value),
            )
        else:
            manual_models = st.text_input("Models", placeholder="model-a, model-b")
            selected_models = [item.strip() for item in manual_models.split(",") if item.strip()]
    else:
        if selectable_model_options:
            selected_model = st.selectbox(
                "Model",
                options=selectable_model_options,
                index=0,
                format_func=lambda value: model_labels.get(value, value),
            )
        else:
            selected_model = st.text_input("Model ID")
    search_query = st.text_input("", placeholder="filter history...", label_visibility="collapsed")
    st.markdown("### History")
    try:
        history_items = load_tasks(backend_url)
    except RuntimeError as exc:
        st.error(str(exc))
        history_items = []
    filtered_items = history_items
    if search_query:
        q = search_query.casefold()
        filtered_items = [item for item in history_items if q in format_task_label(item).casefold()]
    for item in filtered_items:
        task_id = str(item.get("task_id", ""))
        if st.button(format_task_label(item), key=f"history-{task_id}", use_container_width=True):
            try:
                remember_view("task", request_json("GET", backend_url, f"/tasks/{task_id}"))
            except RuntimeError as exc:
                st.error(str(exc))
    with st.expander("Session", expanded=False):
        st.caption(f"ID: `{st.session_state.get('chat_session_id', '—')[:8]}…`")
        if st.button("Reset session", key="sidebar_reset_session"):
            st.session_state["chat_session_id"] = str(uuid.uuid4())
            st.session_state.chat_messages = []
            st.rerun()

tab_chat, tab_playground = st.tabs(["\U0001f4ac Chat", "\U0001f9ea Playground"])

with tab_chat:
    hcol_model, hcol_btn = st.columns([4, 1])
    with hcol_model:
        chat_model_options = model_options if model_options else []
        if chat_model_options:
            chat_model = st.selectbox(
                "Model",
                options=chat_model_options,
                key="chat_selected_model",
                format_func=lambda value: model_labels.get(value, value),
                label_visibility="collapsed",
            )
        else:
            chat_model = st.text_input("Model ID", key="chat_manual_model", label_visibility="collapsed")
    with hcol_btn:
        if st.button("New chat", use_container_width=True, type="secondary"):
            st.session_state.chat_messages = []
            st.session_state["chat_session_id"] = str(uuid.uuid4())
            st.rerun()
    _dry_run_chat = st.checkbox("Dry run", value=False, key="chat_dry_run")

    for _msg in st.session_state.chat_messages:
        with st.chat_message(_msg["role"]):
            st.markdown(str(_msg["content"]))
            if _msg["role"] == "assistant" and _msg.get("meta"):
                _meta = _msg["meta"]
                _parts: list[str] = []
                if _meta.get("model_id"):
                    _parts.append(str(_meta["model_id"]))
                _in = int(_meta.get("input_tokens") or 0)
                _out = int(_meta.get("output_tokens") or 0)
                if _in or _out:
                    _parts.append(f"{_in}\u2191 {_out}\u2193 tok")
                _cost = estimate_cost_usd(str(_meta.get("model_id", "")), _in, _out)
                if _cost:
                    _parts.append(f"${_cost:.4f}")
                if _meta.get("duration_ms"):
                    _parts.append(f"{_meta['duration_ms']}ms")
                if _parts:
                    st.caption(" \u00b7 ".join(_parts))
                if _meta.get("was_decomposed"):
                    _n = int(_meta.get("subtask_count") or 0)
                    st.caption(f"🔀 Decomposed into {_n} subtasks")

    if not st.session_state.chat_messages:
        with st.container(border=True):
            st.markdown("#### 👋 What would you like to explore?")
            st.caption("Choose a model in the selector above, then ask anything.")
            _suggestions = [
                "Summarize the latest AI research papers from this week",
                "What are the key differences between GPT-5 and Claude 4?",
                "Explain quantum entanglement in simple terms",
            ]
            for _s in _suggestions:
                if st.button(_s, use_container_width=True, type="secondary"):
                    st.session_state["_prefill_prompt"] = _s
                    st.rerun()

    if st.session_state.chat_messages:
        _chat_md = _render_chat_export(st.session_state.chat_messages)
        st.download_button(
            "⬇ Export chat",
            data=_chat_md,
            file_name="gracekelly-chat.md",
            mime="text/markdown",
            use_container_width=False,
        )

    _retry_input = st.session_state.pop("chat_retry_message", None)
    if st.session_state.get("chat_last_failed_message"):
        _failed_msg = st.session_state["chat_last_failed_message"]
        st.warning(f"Last message failed. Retry: _{_failed_msg[:80]}{'…' if len(_failed_msg) > 80 else ''}_")
        if st.button("↩ Retry", key="chat_retry_btn"):
            st.session_state["chat_retry_message"] = st.session_state.pop("chat_last_failed_message")
            st.rerun()
    _uploaded_files = st.file_uploader(
        "Attach files",
        accept_multiple_files=True,
        type=["txt", "md", "csv", "json", "py", "pdf", "jpg", "jpeg", "png", "gif", "webp"],
        key="chat_file_uploader",
        label_visibility="collapsed",
    )
    if st.session_state.get("_prefill_prompt"):
        _user_input = st.session_state.pop("_prefill_prompt")
    else:
        _user_input = st.chat_input("Ask GraceKelly...", key="chat_input_box")
    if _retry_input is not None:
        _user_input = _retry_input

    if _user_input:
        _resolved_model = chat_model if chat_model_options else st.session_state.get("chat_manual_model", "")

        st.session_state.chat_messages.append(
            {"role": "user", "content": _user_input, "task_id": None, "meta": None}
        )
        with st.chat_message("user"):
            st.markdown(_user_input)

        _received_task_id: str | None = None
        _collected = ""
        _final_meta: dict[str, Any] | None = None
        _stream_error: str | None = None
        _payload: dict[str, Any] = {
            "prompt": _user_input,
            "model": _resolved_model,
            "dry_run": _dry_run_chat,
            "session_id": st.session_state["chat_session_id"],
        }

        with st.chat_message("assistant"):
            _placeholder = st.empty()
            try:
                if _uploaded_files:
                    _upload_resp = requests.post(
                        f"{backend_url}/api/v1/orchestrate/upload",
                        data={
                            "prompt": _user_input,
                            "model": _resolved_model,
                            "dry_run": str(_dry_run_chat).lower(),
                            "session_id": st.session_state["chat_session_id"],
                        },
                        files=[
                            ("files", (f.name, f.getvalue(), f.type or "application/octet-stream"))
                            for f in _uploaded_files
                        ],
                        timeout=120,
                    )
                    if _upload_resp.ok:
                        _body = _upload_resp.json()
                        _collected = str(_body.get("output_text") or "(no output)")
                        _received_task_id = str(_body.get("task_id") or "") or None
                        _model_payload = _body.get("model") if isinstance(_body.get("model"), dict) else {}
                        _final_meta = {
                            "model_id": _model_payload.get("id") or _resolved_model,
                            "duration_ms": _body.get("duration_ms"),
                            "was_decomposed": bool(_body.get("was_decomposed", False)),
                            "subtask_count": int(_body.get("subtask_count") or 0),
                        }
                        _placeholder.markdown(_collected)
                    else:
                        _stream_error = f"Upload failed: {_upload_resp.status_code}"
                        st.session_state["chat_last_failed_message"] = _user_input
                        _placeholder.error(f"{_stream_error}\n\n{extract_error(_upload_resp)}")
                else:
                    for _etype, _edata in stream_from_sse(backend_url, "/orchestrate/stream", _payload):
                        if _etype == "accepted":
                            _received_task_id = str(_edata.get("task_id") or "")
                        elif _etype == "delta":
                            _collected += str(_edata.get("text", ""))
                            _placeholder.markdown(_collected + "\u258c")
                        elif _etype == "complete":
                            _collected = str(_edata.get("text", _collected))
                            _final_meta = _edata
                            _placeholder.markdown(_collected)
                        elif _etype == "error":
                            _stream_error = str(_edata.get("text", "Unknown error"))
                            st.session_state["chat_last_failed_message"] = _user_input
                            _placeholder.error(_stream_error)
                            break
            except requests.RequestException as _exc:
                _stream_error = f"Backend unreachable: {_exc}"
                st.session_state["chat_last_failed_message"] = _user_input
                _backend_error = _stream_error.removeprefix("Backend unreachable: ").strip()
                _placeholder.error(
                    f"Backend unreachable: {_backend_error}\n\n"
                    f"Is the GraceKelly server running at `{backend_url}`?"
                )
            except RuntimeError as _exc:
                _stream_error = str(_exc)
                st.session_state["chat_last_failed_message"] = _user_input
                if _stream_error.startswith("Backend unreachable:"):
                    _backend_error = _stream_error.removeprefix("Backend unreachable: ").strip()
                    _placeholder.error(
                        f"Backend unreachable: {_backend_error}\n\n"
                        f"Is the GraceKelly server running at `{backend_url}`?"
                    )
                else:
                    _placeholder.error(_stream_error)

            if _final_meta is not None:
                _final_meta["was_decomposed"] = bool(_final_meta.get("was_decomposed", False))
                _final_meta["subtask_count"] = int(_final_meta.get("subtask_count") or 0)
                _cap: list[str] = []
                if _final_meta.get("model_id"):
                    _cap.append(str(_final_meta["model_id"]))
                _in2 = int(_final_meta.get("input_tokens") or 0)
                _out2 = int(_final_meta.get("output_tokens") or 0)
                if _in2 or _out2:
                    _cap.append(f"{_in2}\u2191 {_out2}\u2193 tok")
                _cost2 = estimate_cost_usd(str(_final_meta.get("model_id", "")), _in2, _out2)
                if _cost2:
                    _cap.append(f"${_cost2:.4f}")
                if _final_meta.get("duration_ms"):
                    _cap.append(f"{_final_meta['duration_ms']}ms")
                if _cap:
                    st.caption(" \u00b7 ".join(_cap))
                if _final_meta.get("was_decomposed"):
                    _n = _final_meta.get("subtask_count", 0)
                    st.caption(f"🔀 Decomposed into {_n} subtasks")


        if _stream_error is None and _final_meta is not None:
            st.session_state["chat_last_failed_message"] = None
            st.session_state.chat_messages.append(
                {
                    "role": "assistant",
                    "content": _collected,
                    "task_id": _received_task_id or None,
                    "meta": _final_meta or None,
                }
            )
            load_tasks.clear()

with tab_playground:
    st.markdown("##### GraceKelly Control Room")
    st.title("Streamlit Playground")
    st.caption("Run prompts, switch execution patterns, and inspect recent task history from the local backend.")

    with st.form("playground-form"):
        prompt = st.text_area(
            "Prompt",
            height=220,
            placeholder="Ask GraceKelly to orchestrate a prompt, compare models, or run a debate.",
        )
        left, right = st.columns(2)
        with left:
            dry_run = st.checkbox("Dry run", value=True, disabled=pattern != "single")
            reasoning = st.checkbox("Reasoning", value=False, disabled=pattern != "single")
        with right:
            analyze = st.checkbox("Analyze compare output", value=True, disabled=pattern != "compare")
            max_rounds = st.slider("Consensus rounds", 1, 5, 3, disabled=pattern != "consensus")
            variations = st.slider("Variations per round", 1, 5, 3, disabled=pattern != "consensus")
        submitted = st.form_submit_button("Run")

    if submitted:
        if not prompt.strip():
            st.error("Prompt is required.")
        elif pattern == "compare" and len(selected_models) < 2:
            st.error("Compare requires at least two models.")
        elif pattern != "compare" and not selected_model.strip():
            st.error("Select a model or enter a model ID.")
        else:
            try:
                if pattern == "single":
                    output_placeholder = st.empty()
                    collected = ""
                    final_result: dict[str, Any] = {}
                    for event_type, data in stream_from_sse(
                        backend_url,
                        "/orchestrate/stream",
                        {
                            "prompt": prompt,
                            "model": selected_model,
                            "dry_run": dry_run,
                            "reasoning": reasoning,
                        },
                    ):
                        if event_type == "delta":
                            collected += str(data.get("text", ""))
                            output_placeholder.markdown(collected + "\u258c")
                        elif event_type == "complete":
                            collected = str(data.get("text", collected))
                            final_result = data
                            output_placeholder.markdown(collected)
                        elif event_type == "error":
                            st.error(str(data.get("text", "Unknown error")))
                    if final_result:
                        remember_view(
                            "single",
                            {
                                "status": "completed",
                                "output_text": collected,
                                "duration_ms": final_result.get("duration_ms"),
                                "execution_mode": "dry-run" if dry_run else "live",
                                "model": final_result.get("model_id"),
                                "input_tokens": final_result.get("input_tokens"),
                                "output_tokens": final_result.get("output_tokens"),
                                "cost_usd": estimate_cost_usd(
                                    str(final_result.get("model_id", "")),
                                    final_result.get("input_tokens"),
                                    final_result.get("output_tokens"),
                                ),
                            },
                        )
                        load_tasks.clear()
                else:
                    with st.spinner("Contacting GraceKelly backend..."):
                        if pattern == "consensus":
                            result = request_json(
                                "POST",
                                backend_url,
                                "/consensus",
                                {
                                    "prompt": prompt,
                                    "model": selected_model,
                                    "max_rounds": max_rounds,
                                    "variations_per_round": variations,
                                },
                            )
                            result["model"] = selected_model
                        elif pattern == "debate":
                            result = request_json(
                                "POST",
                                backend_url,
                                "/debate",
                                {
                                    "topic": prompt,
                                    "model": selected_model,
                                },
                            )
                            result["model"] = selected_model
                        else:
                            result = request_json(
                                "POST",
                                backend_url,
                                "/compare",
                                {
                                    "prompt": prompt,
                                    "models": selected_models,
                                    "analyze": analyze,
                                },
                            )
                        remember_view(pattern, result)
                        load_tasks.clear()
            except RuntimeError as exc:
                st.error(str(exc))

    payload = st.session_state["view_payload"]
    view_type = st.session_state["view_type"]

    if view_type == "single" and isinstance(payload, dict):
        render_single_result(payload)
    elif view_type == "consensus" and isinstance(payload, dict):
        render_consensus_result(payload)
    elif view_type == "debate" and isinstance(payload, dict):
        render_debate_result(payload)
    elif view_type == "compare" and isinstance(payload, dict):
        render_compare_result(payload)
    elif view_type == "task" and isinstance(payload, dict):
        render_task_view(payload)
    else:
        with st.container(border=True):
            st.markdown(
                "Choose a pattern, submit a prompt, or open a task from the sidebar to inspect the latest run."
            )
