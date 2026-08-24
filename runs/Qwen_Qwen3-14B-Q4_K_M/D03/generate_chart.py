import pandas as pd
import matplotlib.pyplot as plt

data = pd.read_csv('comparison.csv')
plt.figure(figsize=(8, 4))
plt.bar(data['process'], data['yield'], color=['#ff9999', '#66b2ff'])
plt.title('Process Yield Comparison')
plt.ylabel('Yield Rate')
plt.ylim(0.95, 1.0)
plt.savefig('yield_chart.png')