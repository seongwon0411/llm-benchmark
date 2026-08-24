import pandas as pd
import matplotlib.pyplot as plt
import json

def calculate_defect_rate(units_inspected, defects):
    return (defects / units_inspected) * 100

data = pd.read_csv('factory_kpi.csv')

# Calculate defect rates for each year
analysis = {
    'defect_rate_2024': calculate_defect_rate(data[data['year'] == 2024]['units_inspected'].sum(), data[data['year'] == 2024]['defects'].sum()),
    'defect_rate_2025': calculate_defect_rate(data[data['year'] == 2025]['units_inspected'].sum(), data[data['year'] == 2025]['defects'].sum()),
    'defect_rate_2026_pilot': calculate_defect_rate(data[data['year'] == 2026]['units_inspected'].sum(), data[data['year'] == 2026]['defects'].sum()),
    'highest_downtime_line_all_years': data.loc[data['downtime_min'].idxmax()]['line'],
    'pilot_caveat': True
}

# Save analysis to JSON
with open('analysis.json', 'w') as f:
    json.dump(analysis, f)

# Create yearly summary CSV
yearly_summary = data.groupby('year').agg({'units_inspected': 'sum', 'defects': 'sum'}).reset_index()
yearly_summary.to_csv('yearly_summary.csv', index=False)

# Plot trend of defect rates
plt.figure(figsize=(10, 6))
defect_rates = [analysis['defect_rate_2024'], analysis['defect_rate_2025'], analysis['defect_rate_2026_pilot']]
years = ['2024', '2025', '2026 (Pilot)']
plt.plot(years, defect_rates, marker='o')
plt.title('Defect Rate Trend')
plt.xlabel('Year')
plt.ylabel('Defect Rate (%)')
plt.grid(True)
plt.savefig('trend.png')