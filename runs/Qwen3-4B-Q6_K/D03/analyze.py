import pandas as pd
import matplotlib.pyplot as plt
import json
import os

df = pd.read_csv('process_trial.csv')
old_yield = df[df['process'] == 'old']['passed'].values[0] / df[df['process'] == 'old']['inspected'].values[0]
new_yield = df[df['process'] == 'new']['passed'].values[0] / df[df['process'] == 'new']['inspected'].values[0]

analysis_data = {
    "old_process": {"inspected": 1000, "passed": 960, "yield": old_yield, "unit_scrap_cost_won": 18000},
    "new_process": {"inspected": 1000, "passed": 985, "yield": new_yield, "unit_scrap_cost_won": 18000}
}

with open('analysis.json', 'w') as f:
    json.dump(analysis_data, f)

comparison_data = {
    "process": ["old", "new"],
    "inspected": [1000, 1000],
    "passed": [960, 985],
    "yield": [old_yield, new_yield],
    "unit_scrap_cost_won": [18000, 18000]
}

comparison_df = pd.DataFrame(comparison_data)
comparison_df.to_csv('comparison.csv', index=False)

plt.bar(['Old Process', 'New Process'], [old_yield, new_yield])
plt.ylabel('Yield (%)')
plt.title('Process Yield Comparison')
plt.savefig('yield_chart.png')