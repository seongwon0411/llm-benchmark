# Local LLM Multi-Agent Benchmark

A practical benchmark for evaluating local open-weight language models on real work-oriented tasks.

Instead of evaluating models only with short question-answer tests, this project measures whether a model can successfully produce usable outputs such as:

- Python code
- data analysis results
- reports
- PowerPoint presentations
- research briefs
- critiques and reviews
- structured files and artifacts

The benchmark was executed locally using GGUF models through LM Studio.

---

## What Is Evaluated?

The benchmark evaluates the following capabilities:

- Research
- Coding
- Data Analysis
- Writing
- PowerPoint Generation
- Critic / Review
- Instruction Following
- Tool Calling

Generated artifacts and model transcripts are preserved in the repository so that scores can be inspected against the actual model outputs.

---

## Test Environment

- CPU: AMD Ryzen 9 9950X
- GPU: NVIDIA GeForce RTX 3090 24 GB
- RAM: 64 GB DDR5
- Storage: Samsung 990 PRO 4 TB NVMe
- OS: Windows 11
- Runtime: LM Studio
- Model format: GGUF
- Python: 3.11

> The benchmark results currently represent single RTX 3090 execution unless otherwise noted.

More details: [`docs/hardware.md`](docs/hardware.md)

---

# Version 7.2.2 Leaderboard

Version 7.2.2 uses the stricter artifact-based evaluation methodology.

Failed or incomplete tasks can receive zero points, and generated artifacts are validated as part of the benchmark.

| Rank | Model | Overall | Research | Coding | Data | Writer | PPT | Critic | Peak VRAM GiB | Median Latency s | Errors |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Qwen3-30B-A3B-Q5_K_M | **82.90** | 92.72 | 83.33 | 63.10 | 87.71 | 79.59 | 90.95 | 18.05 | 50.57 | 1 |
| 2 | Qwen3-4B-Q6_K | **74.51** | 96.62 | 83.33 | 38.10 | 86.00 | 56.61 | 86.41 | 5.73 | 30.61 | 2 |
| 3 | Qwen2.5-14B-Instruct-Q5_K_M | **73.55** | 93.18 | 37.50 | 64.30 | 85.71 | 71.52 | 89.07 | 12.74 | 21.45 | 0 |
| 4 | Ministral-3-8B-Reasoning-2512-Q6_K | **72.01** | 88.42 | 66.67 | 53.10 | 90.66 | 49.76 | 83.47 | 8.60 | 21.77 | 2 |
| 5 | Qwen3-8B-Q6_K | **70.94** | 96.62 | 48.17 | 75.00 | 88.83 | 29.20 | 87.79 | 8.47 | 43.04 | 2 |
| 6 | Qwen3-14B-Q4_K_M | **69.77** | 98.83 | 66.67 | 50.00 | 90.66 | 28.83 | 83.62 | 10.95 | 48.09 | 2 |
| 7 | Ministral-3-3B-Instruct-2512-Q4_K_M | **63.94** | 88.06 | 50.47 | 8.33 | 82.92 | 69.68 | 84.20 | 4.03 | 8.78 | 2 |
| 8 | Devstral-Small-2505-Q4_K_M | **56.35** | 94.35 | 83.33 | 0.00 | 55.71 | 16.11 | 88.62 | 16.06 | 29.13 | 6 |
| 9 | Qwen2.5-Coder-14B-Instruct-Q5_K_M | **52.18** | 72.23 | 33.33 | 26.67 | 26.50 | 75.39 | 79.00 | 12.74 | 11.03 | 3 |
| 10 | Phi-4-Q6_K | **47.84** | 90.61 | 48.17 | 0.00 | 89.96 | 0.00 | 58.29 | 14.34 | 104.44 | 7 |

Full results:

- [`results/v7_2_2/report.html`](results/v7_2_2/report.html)
- [`results/v7_2_2/model_scores.csv`](results/v7_2_2/model_scores.csv)
- [`results/v7_2_2/task_scores.csv`](results/v7_2_2/task_scores.csv)

---

## Current Best Result

**Qwen3-30B-A3B-Q5_K_M** achieved the highest overall score in Version 7.2.2:

- Overall: **82.90**
- Research: 92.72
- Coding: 83.33
- Data: 63.10
- Writer: 87.71
- PowerPoint: 79.59
- Critic: 90.95
- Peak VRAM: 18.05 GiB
- Median task latency: 50.57 seconds

---

## Important

This repository contains two benchmark methodologies.

Version 1 and Version 7.2.2 use different scoring rules and should **not** be compared directly.

See:

[`docs/benchmark_versions.md`](docs/benchmark_versions.md)

---

## Inspect the Actual Model Outputs

Benchmark scores are not the only results preserved in this repository.

Version 7.2.2 stores the actual files produced during each model run under:

`runs/<model-name>/<task-id>/`

For example:

```text
runs/Qwen3-30B-A3B-Q5_K_M/
├── C01/    # Coding
├── C02/
├── C03/
├── D01/    # Data Analysis
├── D02/
├── D03/
├── K01/    # Critic / Review
├── K02/
├── K03/
├── P01/    # PowerPoint
├── P02/
├── P03/
├── R01/    # Research
├── R02/
├── R03/
├── W01/    # Writing
├── W02/
└── W03/
```

### Example Artifacts

Depending on the task, a run can contain:

| Task | Example outputs |
|---|---|
| Coding | `.py` source code, pytest tests, README, transcript |
| Data Analysis | `.csv`, `.json`, analysis scripts, charts |
| Research | research briefs and source documents |
| Writing | executive memos, postmortems, revised SOPs |
| PowerPoint | generated `.pptx` presentations and `.xlsx` source data |
| Critic | document reviews, security reviews, presentation reviews |

For example, the Qwen3-30B-A3B run contains generated PowerPoint files such as:

- `factory_ai_review.pptx`
- `investment_committee.pptx`
- `incident_review.pptx`

It also contains generated code, charts, reports, spreadsheets, and the original task transcripts.

This makes it possible to inspect **why a model received a particular score**, rather than relying only on a leaderboard number.

---

## Repository Structure

```text
llm-benchmark/
├── README.md
├── .gitignore
├── benchmark_v1/
├── benchmark_v7_2_2/
├── docs/
│   ├── methodology.md
│   ├── hardware.md
│   ├── benchmark_versions.md
│   └── models.md
├── results/
│   ├── v1/
│   └── v7_2_2/
└── runs/
    └── Actual model-generated artifacts
```

---

## Documentation

- [Benchmark Methodology](docs/methodology.md)
- [Hardware & Environment](docs/hardware.md)
- [Benchmark Version Differences](docs/benchmark_versions.md)
- [Evaluated Models](docs/models.md)
