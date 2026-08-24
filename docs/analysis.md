\# Benchmark Analysis



This document summarizes the main findings from Local LLM Benchmark Version 7.2.2.



The analysis is based on the benchmark results stored in:



`results/v7\_2\_2/model\_scores.csv`



Scores should only be compared between models evaluated using the same benchmark version.



\---



\## Overall Winner



\### Qwen3-30B-A3B-Q5\_K\_M



Qwen3-30B-A3B-Q5\_K\_M achieved the highest overall score in Version 7.2.2.



\- Overall: 82.90

\- Research: 92.72

\- Coding: 83.33

\- Data: 63.10

\- Writer: 87.71

\- PPT: 79.59

\- Critic: 90.95

\- Peak VRAM: 18.05 GiB

\- Median task latency: 50.57 seconds



The model produced the strongest overall balance across the evaluated practical workloads.



Rather than dominating only one category, it maintained relatively high scores across research, coding, writing, presentation generation, and critique tasks.



\---



\## Best Small Model



\### Qwen3-4B-Q6\_K



Qwen3-4B-Q6\_K achieved an overall score of 74.51 while using only 5.73 GiB of peak VRAM.



\- Overall: 74.51

\- Research: 96.62

\- Coding: 83.33

\- Data: 38.10

\- Writer: 86.00

\- PPT: 56.61

\- Critic: 86.41

\- Peak VRAM: 5.73 GiB



This result is notable because the model ranked second overall despite requiring substantially less VRAM than many larger models.



It represents one of the strongest candidates for resource-efficient local agents in this benchmark.



\---



\## Category Leaders



\### Research



\*\*Qwen3-14B-Q4\_K\_M — 98.83\*\*



Qwen3-14B achieved the highest Research score among the evaluated models.



\### Coding



\*\*Qwen3-30B-A3B-Q5\_K\_M — 83.33\*\*  

\*\*Qwen3-4B-Q6\_K — 83.33\*\*  

\*\*Devstral-Small-2505-Q4\_K\_M — 83.33\*\*



Three models reached the same Coding score.



\### Data Analysis



\*\*Qwen3-8B-Q6\_K — 75.00\*\*



Qwen3-8B achieved the highest Data score.



\### Writing



\*\*Qwen3-14B-Q4\_K\_M — 90.66\*\*  

\*\*Ministral-3-8B-Reasoning-2512-Q6\_K — 90.66\*\*



Both models achieved the highest Writer score.



\### PowerPoint



\*\*Qwen3-30B-A3B-Q5\_K\_M — 79.59\*\*



Qwen3-30B-A3B achieved the highest PowerPoint score.



\### Critic / Review



\*\*Qwen3-30B-A3B-Q5\_K\_M — 90.95\*\*



Qwen3-30B-A3B achieved the highest Critic score.



\---



\## Performance per VRAM



One of the most notable results is the performance of Qwen3-4B-Q6\_K.



Despite reaching only 5.73 GiB peak VRAM usage, it achieved an overall score of 74.51.



For comparison:



| Model | Overall | Peak VRAM |

|---|---:|---:|

| Qwen3-30B-A3B-Q5\_K\_M | 82.90 | 18.05 GiB |

| Qwen3-4B-Q6\_K | 74.51 | 5.73 GiB |

| Qwen2.5-14B-Instruct-Q5\_K\_M | 73.55 | 12.74 GiB |

| Ministral-3-8B-Reasoning-2512-Q6\_K | 72.01 | 8.60 GiB |

| Qwen3-8B-Q6\_K | 70.94 | 8.47 GiB |



The results suggest that model size or VRAM consumption alone does not determine practical benchmark performance.



\---



\## Important Findings



\### 1. Larger Models Are Not Always Better



The benchmark does not show a simple relationship between model size and task performance.



Qwen3-4B-Q6\_K ranked second overall while outperforming several substantially larger models.



This suggests that model architecture, training, instruction following, and task compatibility can be as important as parameter count.



\---



\### 2. Models Have Strong Task Specialization



Different models performed best in different categories.



For example:



\- Qwen3-14B performed particularly well in Research and Writing.

\- Qwen3-8B achieved the highest Data score.

\- Qwen3-30B-A3B produced the strongest overall performance and led PPT and Critic.

\- Qwen3-4B provided strong Coding and Research performance with relatively low VRAM usage.



This indicates that selecting a model based only on its overall score may not always produce the best system.



\---



\### 3. Artifact-Based Evaluation Changes the Results



Version 7.2.2 evaluates more than textual responses.



Tasks can require models to produce actual artifacts such as:



\- Python programs

\- CSV files

\- charts

\- Excel workbooks

\- PowerPoint presentations

\- Markdown reports



Missing, invalid, or unusable artifacts can significantly reduce task scores.



This makes the benchmark closer to evaluating practical task completion rather than only response quality.



\---



\## Implications for Multi-Agent Systems



The benchmark results suggest that a multi-agent system does not necessarily need to use the same model for every role.



A possible role allocation based on Version 7.2.2 results is:



| Agent Role | Candidate Model |

|---|---|

| General / Orchestrator | Qwen3-30B-A3B-Q5\_K\_M |

| Research Agent | Qwen3-14B-Q4\_K\_M |

| Coding Agent | Qwen3-30B-A3B-Q5\_K\_M / Qwen3-4B-Q6\_K |

| Data Agent | Qwen3-8B-Q6\_K |

| Writing Agent | Qwen3-14B-Q4\_K\_M |

| Presentation Agent | Qwen3-30B-A3B-Q5\_K\_M |

| Critic / Verifier | Qwen3-30B-A3B-Q5\_K\_M |

| Lightweight Agent | Qwen3-4B-Q6\_K |



This is a benchmark-derived candidate allocation rather than a definitive production recommendation.



Further testing should evaluate interactions between agents, concurrency, context length, memory usage, and end-to-end workflow reliability.



\---



\## Conclusion



Version 7.2.2 shows that practical local LLM performance cannot be predicted from model size alone.



Qwen3-30B-A3B-Q5\_K\_M achieved the strongest overall result, while Qwen3-4B-Q6\_K demonstrated particularly strong performance relative to its VRAM requirements.



The category results also show meaningful specialization between models.



These findings support testing heterogeneous multi-agent architectures in which different local models are assigned to tasks that match their demonstrated strengths.

