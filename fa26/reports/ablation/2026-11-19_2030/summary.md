# Ablation 2026-11-19_2030

Source: log.jsonl and scores/ in this folder.

| config | model | repeat | split | n | overall_pct | correctness_pct | evidence_f1_pct | latency_mean_ms | latency_p95_ms | model_calls | tokens_in | tokens_out | plan_cache_hits | errors |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | anthropic/claude-sonnet-4-6 | 1 | regression | 20 | 92.5 | 92.5 | 100.0 | 2531.3 | 3715.6 | 20 | 75536 | 1384 | 0 | 0 |
| baseline | anthropic/claude-sonnet-4-6 | 1 | development | 40 | 99.25 | 100.0 | 96.67 | 3077.9 | 4186.6 | 40 | 149945 | 2674 | 0 | 0 |
| baseline | anthropic/claude-sonnet-4-6 | 2 | regression | 20 | 92.5 | 92.5 | 100.0 | 2452.6 | 3176.0 | 20 | 75536 | 1395 | 0 | 0 |
| baseline | anthropic/claude-sonnet-4-6 | 2 | development | 40 | 99.25 | 100.0 | 96.67 | 3108.9 | 4303.1 | 40 | 149945 | 2688 | 0 | 0 |
| cache | anthropic/claude-sonnet-4-6 | 1 | regression | 20 | 92.5 | 92.5 | 100.0 | 2349.9 | 3171.4 | 20 | 75536 | 1374 | 0 | 0 |
| cache | anthropic/claude-sonnet-4-6 | 1 | development | 40 | 99.25 | 100.0 | 96.67 | 2984.8 | 4153.4 | 40 | 149945 | 2687 | 0 | 0 |
| cache | anthropic/claude-sonnet-4-6 | 2 | regression | 20 | 92.5 | 92.5 | 100.0 | 1.3 | 3.7 | 0 | 0 | 0 | 20 | 0 |
| cache | anthropic/claude-sonnet-4-6 | 2 | development | 40 | 99.25 | 100.0 | 96.67 | 1.1 | 3.3 | 0 | 0 | 0 | 40 | 0 |
| baseline | anthropic/claude-opus-4-6 | 1 | regression | 20 | 90.0 | 90.0 | 100.0 | 3182.3 | 4362.4 | 20 | 75536 | 1354 | 0 | 0 |
| baseline | anthropic/claude-opus-4-6 | 1 | development | 40 | 99.25 | 100.0 | 96.67 | 4618.8 | 6347.9 | 40 | 149945 | 4172 | 0 | 0 |
| baseline | anthropic/claude-opus-4-6 | 2 | regression | 20 | 90.0 | 90.0 | 100.0 | 3141.4 | 4091.1 | 20 | 75536 | 1354 | 0 | 0 |
| baseline | anthropic/claude-opus-4-6 | 2 | development | 40 | 99.25 | 100.0 | 96.67 | 4768.4 | 6656.7 | 40 | 149945 | 4129 | 0 | 0 |
| cache | anthropic/claude-opus-4-6 | 1 | regression | 20 | 90.0 | 90.0 | 100.0 | 3340.7 | 4111.5 | 20 | 75536 | 1549 | 0 | 0 |
| cache | anthropic/claude-opus-4-6 | 1 | development | 40 | 99.25 | 100.0 | 96.67 | 4515.9 | 7149.8 | 40 | 149945 | 4279 | 0 | 0 |
| cache | anthropic/claude-opus-4-6 | 2 | regression | 20 | 90.0 | 90.0 | 100.0 | 1.9 | 4.9 | 0 | 0 | 0 | 20 | 0 |
| cache | anthropic/claude-opus-4-6 | 2 | development | 40 | 99.25 | 100.0 | 96.67 | 1.1 | 3.3 | 0 | 0 | 0 | 40 | 0 |
| baseline | zai/glm-5.3 | 1 | regression | 20 | 100.0 | 100.0 | 100.0 | 10696.2 | 32490.8 | 21 | 68515 | 10405 | 0 | 0 |
| baseline | zai/glm-5.3 | 1 | development | 40 | 99.25 | 100.0 | 96.67 | 5283.3 | 11784.0 | 40 | 129437 | 8858 | 0 | 0 |
| baseline | zai/glm-5.3 | 2 | regression | 20 | 95.0 | 95.0 | 100.0 | 12260.3 | 13213.4 | 21 | 68515 | 12602 | 0 | 0 |
| baseline | zai/glm-5.3 | 2 | development | 40 | 99.25 | 100.0 | 96.67 | 5647.6 | 11613.5 | 40 | 129437 | 10552 | 0 | 0 |
| cache | zai/glm-5.3 | 1 | regression | 20 | 95.0 | 95.0 | 100.0 | 7846.8 | 15905.8 | 20 | 65206 | 8249 | 0 | 0 |
| cache | zai/glm-5.3 | 1 | development | 40 | 96.75 | 97.5 | 96.67 | 5900.4 | 15925.0 | 40 | 129437 | 10398 | 0 | 0 |
| cache | zai/glm-5.3 | 2 | regression | 20 | 95.0 | 95.0 | 100.0 | 1.2 | 3.5 | 0 | 0 | 0 | 20 | 0 |
| cache | zai/glm-5.3 | 2 | development | 40 | 96.75 | 97.5 | 96.67 | 1.1 | 3.3 | 0 | 0 | 0 | 40 | 0 |
