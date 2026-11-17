# Benchmark comparison

These are structured-answer checks on one pinned dataset. They do not establish real-world accuracy or evaluate prose.

| Run | Correctness % | Evidence F1 % | Abstention/clarification % | Overall % | Latency samples | Mean ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| sqlite_baseline_not_an_LLM | 100.0 | 100.0 | 100.0 | 100.0 | 20 | 3.337 |
| deliberately_wrong_control | 0.0 | 0.0 | 0.0 | 0.0 | 0 | not supplied |
| correct_values_without_evidence_control | 100.0 | 0.0 | 100.0 | 76.0 | 0 | not supplied |
