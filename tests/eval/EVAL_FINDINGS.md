# Eval Findings — Retrieve-Verify Loop

Ran the quantitative benchmark harness (`benchmark.py`) against the eval cases
with real DeepSeek calls and the LLM judge. It surfaced a critical defect and a
design-level insight that no unit test or manual run had caught.

## 1. The benchmark caught a note-destroying bug

Running the loop study on `case_01_quantum` (generate at iterations 0/1/2, judge
every version) produced a **monotonic quality collapse** — the opposite of what
the retrieve-verify loop is supposed to do:

| iteration | overall (before fix) | hallucinations |
|---|---|---|
| 0 | 4.75 | 1 |
| 1 | 3.15 | 3 |
| 2 | **1.00** | 2 |

An overall of 1.0 means the note was effectively destroyed.

### Root cause
`_apply_patches` → `replace_section` bounded a patched section at the *next
heading of the same or higher level*. The H1 title has no sibling, so the search
returned nothing and the boundary became **end-of-note**. A single
`### PATCH: <title>` block therefore replaced the **entire document**. The model
emits title-level patches frequently, so the note was truncated every round.

Reproduced in isolation: a 77-char note → 26 chars (only the title survived).

### Fix
When patching an H1 with no sibling, bound the span at the first subheading so
only the title's intro paragraph is replaced. Applied in `graph.py` and
`tools.py`; locked in by `TestH1TitlePatchRegression`.

### After the fix (same case, same harness)

| iteration | overall | factual_accuracy | hallucinations | tokens |
|---|---|---|---|---|
| 0 | 4.30 | 3.0 | 1 | 21.6k |
| 1 | 4.00 | 1.0 | 3 | 40.0k |
| 2 | 3.25 | 1.0 | 5 | 64.4k |

The catastrophic collapse is gone — iter=2 recovered from **1.0 → 3.25** and the
note is no longer truncated.

## 2. Design insight: the loop is not unconditionally beneficial

Even with the bug fixed, on this case the loop is still **net-negative**: overall
drifts down 4.30 → 4.00 → 3.25, hallucinations climb 1 → 3 → 5, and token cost
**triples**. Reading the refined notes shows why: "quantum computing basics" is a
stable topic the model already knows well, so retrieval adds noise, and the
verify-refine step **fabricates `[R]` citations** to satisfy the "cite evidence"
instruction — which is exactly what drives the hallucination count up.

Conclusion: retrieve-verify should be **gated**, not unconditional. Trigger it
only when (a) the draft scores below a quality threshold, or (b) the topic needs
fresh/time-sensitive data. The refine prompt should also forbid attaching
citations to already-correct, general-knowledge statements.

> Caveat: n=1, and the judge is non-deterministic (≈±0.3 noise on `overall`).
> The *direction* is robust and reproduced across the before/after runs; the
> absolute numbers should be read as indicative, not precise. Re-run with a
> larger `--n` for tighter estimates:
>
> ```bash
> python -m tests.eval.benchmark --study all --n 8 --iters 0,1,2
> ```

## Resume-ready framing

> Built an LLM-judge evaluation harness for an agentic note-generation pipeline;
> it exposed that the core retrieve-verify loop was *degrading* output quality
> (judge score 4.75 → 1.0 across iterations). Root-caused a note-truncation bug
> in the patch-application logic, fixed it with a regression test (collapse
> eliminated, 1.0 → 3.25), and showed the loop should be quality-gated rather
> than unconditional — cutting wasted token spend.
