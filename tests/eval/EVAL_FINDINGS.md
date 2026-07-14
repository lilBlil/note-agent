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

## 3. Fixing the loop so iteration actually improves quality

The design insight above was itself a diagnosis, not the end state: in the
eval rubric, iterating **must** raise the score. Two prompt-level defects (found
by reading the code, confirmed by dumping intermediate notes) were the cause:

- **The refine step could not see the note body.** `verify_and_refine_prompt`
  passed only the section *headings* (`_extract_headings`) yet asked the model to
  "output the full revised section". So it rewrote each section blind, from
  headings + (off-scope) references — destroying correct content. (A regression
  from merging the old two-stage verify/refine, where verify saw the full note.)
- **The prompt was "add-only" and treated citations as a KPI.** Every instruction
  said "supplement …", one demanded `[R]` tags. With weak/off-scope hits the model
  fabricated citations and injected advanced fault-tolerant-QC material into a
  *basics* note → hallucinations up, factual accuracy down.

### Fixes
1. Pass the **full note** to the refine prompt.
2. A **do-no-harm rule set**: keep correct content verbatim, never write the
   uncertain, output `### NO_CHANGES` freely.
3. A **scope guard** (refine + query generation): ignore references on narrower/
   off-topic subfields; don't pull the note out of its stated depth.
4. **Citation discipline**: tag `[R]` only when a reference concretely supports
   a claim; never fabricate.

### Result — three runs on case_01, same harness & judge

| iteration | ① original (bug) | ② bug fixed | ③ bug + prompt fixed |
|---|---|---|---|
| 0 | 4.75 / 1 halluc | 4.30 / 1 | 4.15 / 1 |
| 1 | 3.15 / 3 | 4.00 / 3 | **4.65 / 0** |
| 2 | **1.00** / 2 | 3.25 / 5 | **4.50 / 1** |

Iteration is now **net-positive**: iter0→1 rises 4.15 → 4.65 and hallucinations
fall 1 → 0. Evidence from the dumped intermediates confirms the mechanism is
fixed, not just the score:
- **Scope held**: off-scope ("容错") mention count is unchanged across the refine
  step (4→4, 6→6) — the loop no longer injects advanced material.
- **No fabricated citations**: the iter1 refine emitted **0** `[R]` tags when the
  references didn't cleanly support a claim (previously it invented them).
- **Do-no-harm**: the iter1 refine preserved **99% of the original note verbatim**
  (+9 chars net) — surgical edits, not a blind rewrite.

> Caveat: n=1, and the judge is non-deterministic (≈±0.3 noise on `overall`);
> the iter0 baseline drifts 4.75/4.30/4.15 across runs for this reason. The
> *direction* (③ >> ①, iteration now rising) is robust and backed by the
> non-LLM evidence above. Re-run larger for tighter estimates:
>
> ```bash
> python -m tests.eval.benchmark --study all --n 8 --iters 0,1,2
> ```

## Resume-ready framing

> Built an LLM-judge evaluation harness for an agentic note-generation pipeline.
> It exposed that the core retrieve-verify loop was *degrading* quality instead
> of improving it (judge score 4.75 → 1.0 across iterations). Root-caused two
> defects — a note-truncation bug in patch application and a refine prompt that
> wrote sections blind and fabricated citations — and fixed both with a
> regression test and prompt redesign (do-no-harm + scope guard + citation
> discipline). Iteration went from net-negative to net-positive (iter0→1 now
> 4.15 → 4.65, hallucinations 1 → 0), verified against the dumped intermediates
> (99% content preserved, zero fabricated citations, scope held).
