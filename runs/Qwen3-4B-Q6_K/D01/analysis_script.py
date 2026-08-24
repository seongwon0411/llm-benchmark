import pandas as pd
import matplotlib.pyplot as plt
import json

df = pd.read_csv('factory_kpi.csv')

defect_rates_2024 = df[df['year'] == '2024']['defects'] / df[df['year'] == '2024']['units_inspected']
defect_rate_2024 = defect_rates_2024.mean()

defect_rates_2025 = df[df['year'] == '2025']['defects'] / df[df['year'] == '2025']['units_inspected']
defect_rate_2025 = defect_rates_2025.mean()

defect_rates_2026 = df[df['year'] == '2026']['defects'] / df[df['year'] == '2026']['units_inspected']
defect_rate_2026_pilot = defect_rates_2026.mean()

max_downtime = df['downtime_min'].max()

analysis_data = {
    'defect_rate_2024': float(defect_rate_2024),
    'defect_rate_2025': float(defect_rate_2025),
    'defect_rate_2026_pilot': float(defect_rate_2026_pilot),
    'highest_downtime_line_all_years': int(max_downtime),
    'pilot_caveat': True
}

with open('analysis.json', 'w') as f:
    json.dump(analysis_data, f)

yearly_summary = df.groupby('year').apply(
    lambda x: pd.DataFrame({
        'total_units_inspected': [x['units_inspected'].sum()],
        'total_defects': [x['defects'].sum()],
        'average_defect_rate': [x['defects'].sum() / x['units_inspected'].sum()]
    })
).reset_index(drop=True)

yearly_summary.to_csv('yearly_summary.csv', index=False)

yearly_summary.to_csv('yearly_summary.csv', index=False)

plt.plot(df['year'], df['defects'] / df['units_inspected'])
plt.xlabel('Year')
plt.ylabel('Defect Rate')
plt.title('Defect Rate Trend')
plt.savefig('trend.png')