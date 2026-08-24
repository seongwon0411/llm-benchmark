import csv
import json
import matplotlib.pyplot as plt

# Read CSV data
with open('maintenance_kpi.csv', 'r') as file:
    reader = csv.DictReader(file)
    data = list(reader)

# Calculate MTBF and MTTR for each line
analysis_data = {}
for row in data:
    line = row['line']
    operating_hours = float(row['operating_hours'])
    failures = float(row['failures'])
    repair_minutes = float(row['repair_minutes'])

    mtbf = operating_hours / failures if failures > 0 else 0
    mttr_h = repair_minutes / 60 / failures if failures > 0 else 0

    analysis_data[f'{line.lower()}_mtbf'] = mtbf
    analysis_data[f'{line.lower()}_mttr_h'] = mttr_h

# Determine the priority line (lowest MTBF)
priority_line = min(data, key=lambda x: float(x['operating_hours']) / float(x['failures']))['line']
analysis_data['priority_line'] = priority_line

# Write analysis.json
with open('analysis.json', 'w') as file:
    json.dump(analysis_data, file, indent=4)

# Create maintenance_summary.csv
summary_fields = ['line', 'mtbf', 'mttr_h']
summary_data = []
for row in data:
    line = row['line']
    mtbf = analysis_data[f'{line.lower()}_mtbf']
    mttr_h = analysis_data[f'{line.lower()}_mttr_h']
    summary_data.append({'line': line, 'mtbf': mtbf, 'mttr_h': mttr_h})

with open('maintenance_summary.csv', 'w', newline='') as file:
    writer = csv.DictWriter(file, fieldnames=summary_fields)
    writer.writeheader()
    writer.writerows(summary_data)

# Create MTBF bar chart
lines = [row['line'] for row in data]
mtbf_values = []
for row in data:
    line = row['line']
    mtbf_values.append(analysis_data[f'{line.lower()}_mtbf'])

plt.figure(figsize=(10, 6))
plt.bar(lines, mtbf_values, color='skyblue')
plt.xlabel('Line')
plt.ylabel('MTBF (hours)')
plt.title('Mean Time Between Failures (MTBF) by Line')
plt.savefig('mtbf.png')