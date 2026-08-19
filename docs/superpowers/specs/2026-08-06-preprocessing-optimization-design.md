# Preprocessing Optimization Design

**Date:** 2026-08-06  
**Status:** Draft - Pending User Review

---

## Problem Statement

The preprocessing page in the Streamlit application suffers from severe performance issues due to:

1. **GIL Contention**: `threading.Thread` used for CPU-bound tasks (stemming, regex, loops) — only one thread executes Python bytecode at a time, blocking the main UI thread (`st.fragment(run_every=0.5)`).
2. **Non-Vectorized Loops**: 6 full-pass loops using `.at[]` scalar accessor (one per step: Case Folding, Cleaning, Normalisasi, Stopword, Stemming, Tokenizing) — massive pandas overhead.
3. **Ineffective Caching**: `@lru_cache` on instance method `_load_slang_dictionary` — cache misses on every Streamlit rerun because new `AppPage` instance created each time.
4. **Excessive DataFrame Slicing**: Preview rows sliced every `update_every=20` iterations → ~1260 DataFrame copies per run.
5. **Stemming Redundancy**: Per-row stemming with progressive cache warming instead of pre-computing unique word stems.

---

## Design Goals

- **Primary**: Eliminate UI lag during preprocessing by reducing GIL contention and pandas overhead.
- **Secondary**: Make caching effective across Streamlit reruns.
- **Tertiary**: Reduce memory allocations from preview slicing.

---

## Proposed Approach (Phased)

### Phase 1: Quick Wins (Vectorization) — _Current Focus_

- **Case Folding**: Replace `.at[]` loop → `df[input_col].str.lower()`
- **Cleaning**: Replace `.at[]` loop → chained `.str.replace()` vectorized regex
- **Impact**: Removes 2 of 6 full-pass loops immediately; regex operations are fully vectorizable.

### Phase 2: Cache Fix

- Move `_load_slang_dictionary` to module-level function (outside class) so `@lru_cache` persists across Streamlit reruns.

### Phase 3: Loop Optimization

- Replace remaining `.at[]` loops (Normalisasi, Stopword, Stemming, Tokenizing) with `.map()` — lower overhead than scalar access.

### Phase 4: Preview Throttling

- Increase `update_every` for fast steps (Case Folding, Cleaning, Tokenizing → 100); keep 20 only for Stemming.

### Phase 5: Stemming Pre-computation (If Needed)

- Collect all unique words → stem once per unique word → map back to rows. Eliminates `lru_cache` lookup overhead.

### Phase 6: Multiprocessing (Last Resort)

- Move Stemming to `multiprocessing.Process` with `Manager().dict()` for true parallelism. Only if Phases 1-5 insufficient.

---

## Architecture Impact

| Component                 | Change Type                    | Risk                      |
| ------------------------- | ------------------------------ | ------------------------- |
| `page.py` (preprocessing) | Method refactor                | Low — internal logic only |
| `_load_slang_dictionary`  | Move to module level           | Low — pure function       |
| Progress reporting        | Adjust `update_every` per step | Low — UI only             |

No changes to public APIs, data schemas, or other pages.

---

## Success Criteria

1. Preprocessing 4200 rows completes in < 10 seconds (currently ~60+ seconds).
2. UI remains responsive (no browser lag) during preprocessing.
3. Memory usage stable (no growing DataFrame copies).
4. Cache hit on slang dictionary across reruns.

---

## Testing Strategy

- **Unit**: Verify vectorized outputs match loop outputs for each step (Case Folding, Cleaning).
- **Integration**: Run full preprocessing pipeline on sample dataset; compare final output with baseline.
- **Performance**: Time full run before/after; monitor UI responsiveness via manual test.

---

## Open Questions

- [ ] Confirm dataset size typical range (4200 rows mentioned — is this max?)
- [ ] Any downstream consumers of intermediate columns that might break if column order changes?
- [ ] Should we add a config for `update_every` per step or hardcode?

---

## Next Steps

1. User reviews this spec → approve or request changes.
2. On approval: invoke implementation planning (writing-plans).
3. Implement Phase 1 first, validate, then proceed incrementally.
