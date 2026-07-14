# Benchmark Results

## A. Retrieve-verify loop value (n=1 cases)

| iterations | overall | factual_accuracy | depth | avg_hallucinations | avg_tokens |
|---|---|---|---|---|---|
| 0 | 4.3 | 3.0 | 4.0 | 1.0 | 21643 |
| 1 | 4.0 | 1.0 | 5.0 | 3.0 | 40063 |
| 2 | 3.25 | 1.0 | 4.0 | 5.0 | 64441 |

**结论**：迭代 0→2 轮，事实准确性 3.0→1.0，平均幻觉数 1.0→5.0。
