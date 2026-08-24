# Benchmark Hardware

## System Overview

The benchmark was executed on a local Windows workstation designed for local LLM inference and practical AI workload testing.

## Hardware

- CPU: AMD Ryzen 9 9950X
- GPU: NVIDIA GeForce RTX 3090
- GPU VRAM: 24 GB
- System RAM: 64 GB DDR5
- Storage: Samsung 990 PRO 4 TB NVMe SSD
- Motherboard: ASRock X870E Taichi
- Power Supply: Corsair HX1500i
- Cooling: Arctic Liquid Freezer III 420

## GPU Configuration

At the time of the benchmark, the system was operated with one functional RTX 3090.

The workstation is designed for a dual RTX 3090 configuration, but the second GPU was unavailable during this benchmark run.

Therefore, benchmark results in this repository should be interpreted as single-GPU RTX 3090 results unless otherwise noted.

## Software Environment

- Operating System: Windows 11
- Inference Runtime: LM Studio
- Model Format: GGUF
- GPU Acceleration: NVIDIA CUDA-compatible LM Studio runtime
- Python: 3.11
- Benchmark execution: Local machine

## Notes

Performance metrics such as:

- tokens per second
- task latency
- peak VRAM usage
- model load behavior

are dependent on the hardware and software environment.

Results from different systems may therefore vary even when using the same model and quantization.
