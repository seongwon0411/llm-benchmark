# Evaluated Models

This document lists the models with preserved benchmark runs in Version 7.2.2.

Only models with actual benchmark artifacts in the `runs/` directory are included here.

## Version 7.2.2 Models

| # | Model | Quantization |
|---:|---|---|
| 1 | DeepSeek-R1-0528-Qwen3-8B | Q4_K_M |
| 2 | Devstral-Small-2505 | Q4_K_M |
| 3 | Gemma-3-4B-IT | Q5_K_M |
| 4 | Granite-3.3-8B-Instruct | Q4_K_M |
| 5 | Granite-4.0-H-Micro | Q4_K_M |
| 6 | InternLM3-8B-Instruct | Q4_K_M |
| 7 | Ministral-3-3B-Instruct-2512 | Q4_K_M |
| 8 | Ministral-3-8B-Reasoning-2512 | Q6_K |
| 9 | Phi-4 | Q6_K |
| 10 | Qwen2.5-14B-Instruct | Q5_K_M |
| 11 | Qwen2.5-Coder-14B-Instruct | Q5_K_M |
| 12 | Qwen3-30B-A3B | Q5_K_M |
| 13 | Qwen3-4B | Q6_K |
| 14 | Qwen3-8B | Q6_K |
| 15 | Qwen3-14B | Q4_K_M |

## Model Artifacts

Each evaluated model has its own directory under:

`runs/<model-name>/`

Depending on the benchmark task, these directories may contain:

- original model transcripts
- generated Python code
- pytest test files
- Markdown reports
- CSV analysis results
- JSON outputs
- generated charts
- Excel workbooks
- PowerPoint presentations
- research briefs
- review and critique documents

These artifacts are preserved so that benchmark scores can be inspected against the actual work produced by each model.

## Important Note

The quantization shown in this table is part of the tested model configuration.

Results should therefore not automatically be generalized to other quantizations of the same base model.

Additional downloaded models that were not evaluated in Version 7.2.2 are not included in this table.
