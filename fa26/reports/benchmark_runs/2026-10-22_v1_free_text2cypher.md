# Benchmark comparison

These are structured-answer checks on one pinned dataset. They do not establish real-world accuracy or evaluate prose.

| Run | Correctness % | Evidence F1 % | Abstention/clarification % | Overall % | Latency samples | Mean ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| anthropic_claude-opus-4-6__langgraph_plan-guard-execute__2026-10-22_0935 | 100.0 | 88.3 | 100.0 | 97.19 | 20 | 5034.21 |
| anthropic_claude-sonnet-4-6__langgraph_plan-guard-execute__2026-10-22_0935 | 95.0 | 82.51 | 100.0 | 92.3 | 20 | 3098.03 |
| zai_glm-5.3__langgraph_plan-guard-execute__2026-10-22_1521 | 100.0 | 92.83 | 100.0 | 98.28 | 20 | 41319.79 |
| zai_glm-4.7-flash__langgraph_plan-guard-execute__2026-10-22_1521 | 5.0 | 6.25 | 0.0 | 5.0 | 20 | 12872.605 |
| sqlite_baseline_not_an_LLM | 100.0 | 100.0 | 100.0 | 100.0 | 20 | 3.337 |
