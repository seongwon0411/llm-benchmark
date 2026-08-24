# Benchmark Methodology

## Overview

This repository evaluates local open-weight language models using practical task-oriented benchmarks.

The benchmark focuses on whether a model can successfully complete realistic work rather than only answer short academic questions.

The evaluated task categories include:

- Research
- Coding
- Data Analysis
- Writing
- PowerPoint Generation
- Critic / Review
- Instruction Following
- Tool Calling

The benchmark was executed locally using GGUF models through LM Studio.

---

## Benchmark Philosophy

The benchmark is designed around actual work outputs.

Depending on the task, the model may be required to:

- modify Python source code
- pass automated tests
- analyze CSV or spreadsheet data
- generate charts
- create reports
- create PowerPoint presentations
- review flawed documents or code
- follow explicit instructions
- use available tools correctly

The generated artifacts are preserved in the `runs/` directory so that benchmark results can be inspected directly.

---

## Task Categories

### Research

Measures the model's ability to collect, reconcile, and summarize information from provided source materials.

### Coding

Measures the model's ability to understand requirements, modify code, and satisfy automated tests.

Where applicable, generated code is evaluated using pytest.

### Data Analysis

Measures the model's ability to analyze structured data, calculate required metrics, and create useful output artifacts such as CSV, JSON, or charts.

### Writer

Measures the model's ability to produce structured professional documents based on supplied requirements and source material.

### PowerPoint

Measures the model's ability to produce a usable presentation from supplied data and briefs.

Generated PPTX files are preserved for manual inspection.

### Critic

Measures the model's ability to detect problems in documents, code, or presentations and provide useful corrections or recommendations.

### Instruction Following

Measures whether the model follows required format, constraints, and task-specific instructions.

### Tool Calling

Measures whether the model successfully uses the tools required by a task.

---

## Evaluation Versions

This repository contains results from two different benchmark methodologies.

### Version 1

The first benchmark version evaluates models across multiple practical task categories and records:

- category scores
- overall score
- generation speed
- model output
- generated artifacts

The detailed results are stored in:

`results/v1/`

---

### Version 7.2.2

Version 7.2.2 introduces a stricter artifact-based evaluation process.

Important characteristics include:

- missing or invalid outputs can receive zero points
- failed benchmark runs are included in the final evaluation
- coding tasks are validated using automated tests
- generated files are checked as part of scoring
- PowerPoint tasks include deterministic artifact checks
- task execution status is tracked separately from task score

The detailed results are stored in:

`results/v7_2_2/`

The raw task outputs are stored in:

`runs/`

---

## Reproducibility

The repository includes:

- benchmark source code
- benchmark configuration files
- task definitions
- model selection configuration
- scoring logic
- generated model outputs
- result reports

This allows the benchmark methodology and individual model outputs to be inspected independently.

---

## Important Note

Scores from different benchmark versions should not be compared directly.

Version 1 and Version 7.2.2 use different evaluation logic and scoring rules.

Comparisons between models should therefore be made within the same benchmark version.
