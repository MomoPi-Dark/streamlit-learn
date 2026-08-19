# Page Category Sidebar Design

## Goal

Group Streamlit sidebar pages by folder name under `src/pages`.

Example:

- `src/pages/Modeling/model.py` appears under category `Modeling`.
- `src/pages/test.py` appears under category `General`.

## Approach

Use the file path discovered by `PageLoader` as the source of truth. No page decorator changes are needed.

## Changes

- Make `PageLoader` scan `src/pages` recursively.
- Attach a `__page_category__` attribute to each page instance after loading.
- Keep flat page ordering so existing `ACTIVE_PAGE` index logic still works.
- In `app.py`, render sidebar buttons grouped by category, with `st.sidebar.markdown(category)` and `st.sidebar.markdown("---")` as separators.

## Scope

No new dependencies. No new routing system. No page metadata schema change.

## Validation

Run Python syntax compilation for `src/app.py` and `src/lib/loader.py`.
