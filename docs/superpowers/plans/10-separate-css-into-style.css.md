# [Separate CSS into style.css] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Goal
Move the inline `<style>` block from `page.py` into a dedicated `style.css` file, then have `page.py` read and inject it. This separates presentation logic from Python code.

## Architecture
- `style.css` — plain CSS file containing all custom styles.
- `page.py` — reads `style.css` at runtime and injects it via `st.markdown(..., unsafe_allow_html=True)`.
- No changes to `app.py` or other pages.

## Tech Stack
- Streamlit, Python, `pathlib`, `st.markdown`.

## Global Constraints
- Keep `_CUSTOM_CSS` variable removed (no longer needed).
- `inject_css()` must return a string (the CSS content).
- `st.markdown` must use `unsafe_allow_html=True` to render the `<style>` block.

---

## Tasks

### Task 1: Create `style.css`
- **Files:** `src/app_pages/app/preprocessing/style.css`
- **Content:** The CSS rules currently in `_CUSTOM_CSS` (the `<style>…</style>` block).
- **Steps:**
  - Extract the CSS block from `page.py` (lines 246–279).
  - Write it to `style.css`.

### Task 2: Modify `inject_css()` in `page.py`
- **Files:** `src/app_pages/app/preprocessing/page.py`
- **Changes:**
  - Remove `_CUSTOM_CSS` constant.
  - Replace `inject_css()` to read `style.css` via `Path(__file__).parent / "style.css"`.
  - Return the file contents as a string.

### Task 3: Verify
- Run `python -m pytest tests/` (if tests exist) or at least check that the page loads without errors.
- Verify `inject_css()` returns a non-empty string containing `<style>` and `</style>`.

---

## Execution

**Which approach?**
- **Subagent-Driven:** Dispatch fresh sub-agents per task, review between tasks.
- **Inline Execution:** Execute tasks in this session with checkpoints.

**Choose one.**
