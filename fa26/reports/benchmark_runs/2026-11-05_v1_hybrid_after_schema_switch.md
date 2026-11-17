# Benchmark comparison

These are structured-answer checks on one pinned dataset. They do not establish real-world accuracy or evaluate prose.

| Run | Correctness % | Evidence F1 % | Abstention/clarification % | Overall % | Latency samples | Mean ms |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| templates_manual__neo4j_templates__2026-11-05_165106_002035 | 100.0 | 100.0 | 100.0 | 100.0 | 20 | 100.18 |
| hybrid_llm_router__anthropic_claude-opus-4-6__2026-11-05_165106_002035 | 100.0 | 100.0 | 100.0 | 100.0 | 20 | 3524.395 |
| hybrid_llm_router__anthropic_claude-sonnet-4-6__2026-11-05_165106_002035 | 100.0 | 100.0 | 100.0 | 100.0 | 20 | 2363.17 |
| hybrid_llm_router__zai_glm-5.3__2026-11-05_165106_002035 | 100.0 | 100.0 | 100.0 | 100.0 | 20 | 5852.19 |
| sqlite_baseline_not_an_LLM | 100.0 | 100.0 | 100.0 | 100.0 | 20 | 3.337 |
