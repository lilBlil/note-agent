# Benchmark Results

## A. Retrieve-verify loop value (n=1 cases)

| iterations | overall | factual_accuracy | depth | avg_hallucinations | avg_tokens |
|---|---|---|---|---|---|
| 0 | 4.15 | 3.0 | 4.0 | 1.0 | 20445 |
| 1 | 4.65 | 4.0 | 5.0 | 0.0 | 33637 |
| 2 | 4.5 | 4.0 | 5.0 | 1.0 | 74625 |

**结论**：迭代 0→2 轮，事实准确性 3.0→4.0，平均幻觉数 1.0→1.0。
