import pandas as pd
import matplotlib.pyplot as plt

data = pd.read_csv('maintenance_kpi.csv')
mtbf = data['operating_hours'] / data['failures']
mttr_h = (data['repair_minutes'] / 60) / data['failures']

plt.figure(figsize=(8,5))
plt.bar(data['line'], mtbf, color='skyblue')
plt.title('MTBF by Line')
plt.xlabel('Line')
plt.ylabel('MTBF (hours)')
plt.ylim(0, 200)
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.savefig('mtbf.png')
plt.close()