import pandas as pd
import matplotlib.pyplot as plt
import json

# Load data
df = pd.read_csv('factory_kpi.csv')

# Analysis metrics
analysis = {
    'total_units': int(df['units_inspected'].sum()),
    'total_defects': int(df['defects'].sum()),
    'avg_downtime': df['downtime_min'].mean(),
    'pilot_count': df['pilot'].value_counts().astype(int).apply(lambda x: int(x)).to_dict()
}

# Yearly summary
yearly_summary = df.groupby('year').agg({
    'units_inspected': 'sum',
    'defects': 'sum',
    'downtime_min': 'mean'
}).reset_index()

# Save outputs
with open('analysis.json', 'w') as f:
    json.dump(analysis, f)

yearly_summary.to_csv('yearly_summary.csv', index=False)

# Trend plot
df.groupby('year')[['units_inspected', 'defects']].mean().plot(kind='line')
plt.title('Factory Trends 2024-2026')
plt.savefig('trend.png')