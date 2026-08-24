# Benchmark Versions

This repository contains results from two benchmark methodologies.

The two result sets should be treated as separate experiments because the evaluation and scoring logic changed between versions.

---

## Version 1

Version 1 is the original practical local LLM benchmark.

It evaluates models across multiple work-oriented categories, including:

- Research
- Coding
- Data Analysis
- Writing
- PowerPoint Generation
- Critic / Review
- Instruction Following
- Tool Calling

The benchmark records model responses, generated artifacts, category scores, overall scores, and performance information.

### Files

Benchmark implementation:

`benchmark_v1/`

Results:

`results/v1/`

Important result files include:

- `report.html`
- `model_scores.csv`
- `task_scores.csv`
- `detailed_responses.csv`
- `inventory.csv`

---

## Version 7.2.2

Version 7.2.2 is a stricter revision of the benchmark.

The benchmark was redesigned to place greater emphasis on whether the model actually completed the requested task and produced valid artifacts.

Changes include:

- stricter artifact validation
- automated testing for coding tasks
- explicit execution status tracking
- zero-score handling for failed or invalid task outputs
- deterministic checks for generated artifacts
- improved handling of benchmark execution failures
- preservation of model-generated task artifacts for inspection

### Files

Benchmark implementation:

`benchmark_v7_2_2/`

Results:

`results/v7_2_2/`

Raw model outputs and generated artifacts:

`runs/`

---

## Why Scores Differ

Scores from Version 1 and Version 7.2.2 are not directly comparable.

A model can receive a substantially different score between the two versions because:

1. scoring rules changed
2. artifact validation became stricter
3. failed executions may receive zero points
4. coding outputs are checked against automated tests
5. task completion is evaluated more strictly

For this reason, model rankings should only be compared against other models evaluated using the same benchmark version.

---

## Repository Policy

Both benchmark versions are preserved intentionally.

Version 1 represents the original experiment.

Version 7.2.2 represents the later, stricter benchmark methodology.

Keeping both versions makes it possible to inspect how the benchmark methodology evolved instead of replacing older results with newer scores.
