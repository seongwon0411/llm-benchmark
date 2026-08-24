import pandas as pd
import matplotlib.pyplot as plt
import json

# Read CSV
df = pd.read_csv('factory_kpi.csv')

# Example analysis: yearly summary
yearly_summary = df.groupby('year').sum()
yearly_summary.to_csv('yearly_summary.csv')

# Trend plot
plt.figure(figsize=(10,5))
plt.plot(df['year'], df['KPI'], marker='o')
plt.title('Trend of KPI Over Years')
plt.xlabel('Year')
plt.ylabel('KPI Value')
plt.savefig('trend.png')

# Save analysis to JSON
analysis = {
    'total_rows': len(df),
    'columns': list(df.columns)
}
with open('analysis.json', 'w') as f:
    json.dump(analysis, f)