import pandas as pd
import matplotlib.pyplot as plt

# Read CSV
data = pd.read_csv('factory_kpi.csv')
data['pilot'] = data['pilot'].astype(bool)

# Analysis
yearly_summary = data.groupby('year').agg(
    total_units=('units_inspected', 'sum'),
    total_defects=('defects', 'sum'),
    avg_downtime=('downtime_min', 'mean')
).reset_index()

analysis = {
    'total_years': len(yearly_summary),
    'max_units': data['units_inspected'].max(),
    'min_defects': data['defects'].min(),
    'avg_downtime_all': data['downtime_min'].mean()
}

# Save outputs
yearly_summary.to_csv('yearly_summary.csv', index=False)
pd.DataFrame([analysis]).to_json('analysis.json', orient='records')

# Plot trend
plt.figure(figsize=(10,6))
data.groupby(['year', 'line'])['defects'].sum().unstack().plot(kind='bar')
plt.title('Defect Trends by Line')
plt.savefig('trend.png')