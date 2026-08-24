import pandas as pd
from matplotlib import pyplot as plt

defect_rates = {}

# Read CSV file
kpi_data = pd.read_csv('factory_kpi.csv')

# Calculate defect rates for each year, excluding pilot data in 2026
for year in kpi_data['year'].unique():
    if year == 2026:
        defects_2026_pilot = kpi_data[kpi_data['pilot']]["defects"].sum()
        units_inspected_2026_pilot = kpi_data[kpi_data['pilot']]["units_inspected"].sum()
    else:
        defects_year = kpi_data[kpi_data['year'] == year]['defects'].sum()
        units_inspected_year = kpi_data[kpi_data['year'] == year]['units_inspected'].sum()
        defect_rates[year] = defects_year / units_inspected_year

defect_rate_2024 = defect_rates.get(2024)
defect_rate_2025 = defect_rates.get(2025)
defect_rate_2026_pilot = defects_2026_pilot / units_inspected_2026_pilot

# Find the line with highest downtime in all years
highest_downtime_line_all_years = kpi_data.groupby('line')['downtime_min'].sum().idxmax()

# Create yearly summary CSV file
yearly_summary = pd.DataFrame({
    'Year': [2024, 2025], 
    'Defect Rate': [defect_rate_2024, defect_rate_2025]
})
yearly_summary.to_csv('yearly_summary.csv', index=False)

# Create trend plot
plt.figure(figsize=(10,6))
plt.plot(defect_rates.keys(), defect_rates.values(), marker='o')
plt.title('Defect Rate Trend Over Years')
plt.xlabel('Year')
plt.ylabel('Defect Rate')
plt.grid(True)
plt.savefig('trend.png')

# Create analysis.json file
analysis_data = {
    'defect_rate_2024': defect_rate_2024,
    'defect_rate_2025': defect_rate_2025,
    'defect_rate_2026_pilot': defect_rate_2026_pilot,
    'highest_downtime_line_all_years': highest_downtime_line_all_years,
    'pilot_caveat': True
}
with open('analysis.json', 'w') as f:
    import json
    json.dump(analysis_data, f)
