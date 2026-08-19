import html
import pandas as pd
from .dictionaries import PREPROCESSING_STEPS_META, STEP_ICONS

PIPELINE_SAMPLE_SIZE = 3
LIVE_SAMPLE_SIZE = 5
_MAX_DISPLAY_CHARS = 70import pandas as pd
from lib._configs.dictionaries import PREPROCESSING_STEPS_META, STEP_ICONS

PIPELINE_SAMPLE_SIZE = 3
LIVE_SAMPLE_SIZE = 5
_MAX_DISPLAY_CHARS = 70


def _format_sample_value(value) -> str:
    """Ubah nilai (termasuk list hasil tokenizing) jadi teks singkat untuk tabel."""
    if isinstance(value, list):
        text = ", ".join(str(v) for v in value)
    elif value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        text = ""
    else:
        text = str(value)

    text = text.strip()
    if len(text) > _MAX_DISPLAY_CHARS:
        text = text[: _MAX_DISPLAY_CHARS - 1] + "…"
    return text if text else "(kosong)"


def _esc(value) -> str:
    """Escape teks sebelum disisipkan ke HTML supaya aman & tidak merusak layout."""
    return html.escape(str(value), quote=True)


def _banner_html(icon: str, text: str, kind: str = "info", spin: bool = False) -> str:
    spin_cls = " spin" if spin else ""
    return (
        f"<div class='pp-banner {kind}'>"
        f"<span class='pp-banner-icon{spin_cls}'>{icon}</span>"
        f"<span>{_esc(text)}</span>"
        "</div>"
    )


def _render_stepper_html(step_index: int) -> str:
    parts = ["<div class='pp-stepper'>"]
    for i, (label, _, _) in enumerate(PREPROCESSING_STEPS_META, start=1):
        icon = STEP_ICONS[label]
        if i < step_index:
            state, check = "done", "<span class='pp-step-check'>✓</span>"
        elif i == step_index:
            state, check = "active", ""
        else:
            state, check = "pending", ""
        parts.append(
            f"<div class='pp-step {state}'>"
            f"<div class='pp-step-badge'>{icon}{check}</div>"
            f"<div class='pp-step-label'>{_esc(label)}</div>"
            "</div>"
        )
    parts.append("</div>")
    return "".join(parts)


def _render_progress_bar_html(percent: float, label_text: str) -> str:
    pct = max(0.0, min(100.0, percent))
    return (
        f"<div class='pp-progress-outer'><div class='pp-progress-inner' "
        f"style='width:{pct:.1f}%;'></div></div>"
        f"<div class='pp-progress-label'><span>{_esc(label_text)}</span>"
        f"<span>{pct:.1f}%</span></div>"
    )


def _render_pipeline_table_html(rows: list[dict]) -> str:
    if not rows:
        return ""
    columns = list(rows[0].keys())
    thead = "".join(f"<th>{_esc(c)}</th>" for c in columns)
    body = []
    for row in rows:
        cells = []
        for col in columns:
            val = row.get(col, "—")
            cls = "pp-pending-cell" if val == "—" else "pp-mono"
            cells.append(f"<td class='{cls}'>{_esc(val)}</td>")
        body.append(f"<tr>{''.join(cells)}</tr>")
    return (
        f"<table class='pp-table'><thead><tr>{thead}</tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table>"
    )


def _render_live_table_html(rows: list[dict], current_step: str) -> str:
    if not rows:
        return ""
    body = []
    for row in rows:
        before = _esc(row.get("before", ""))
        after = _esc(row.get("after", ""))
        body.append(
            f"<tr><td class='pp-mono'>{before}</td>"
            f"<td class='pp-arrow-cell'>→</td>"
            f"<td class='pp-mono'>{after}</td></tr>"
        )
    return (
        "<table class='pp-table'><thead><tr>"
        f"<th>Sebelum</th><th></th><th>Sesudah — {_esc(current_step)}</th>"
        f"</tr></thead><tbody>{''.join(body)}</tbody></table>"
    )


def _format_sample_value(value) -> str:
    """Ubah nilai (termasuk list hasil tokenizing) jadi teks singkat untuk tabel."""
    _MAX_DISPLAY_CHARS = 70
    if isinstance(value, list):
        text = ", ".join(str(v) for v in value)
    elif value is None or (not isinstance(value, (list, dict)) and pd.isna(value)):
        text = ""
    else:
        text = str(value)

    text = text.strip()
    if len(text) > _MAX_DISPLAY_CHARS:
        text = text[:_MAX_DISPLAY_CHARS - 1] + "…"
    return text if text else "(kosong)"

PIPELINE_SAMPLE_SIZE = 3
LIVE_SAMPLE_SIZE = 5
