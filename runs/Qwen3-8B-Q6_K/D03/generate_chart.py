import pandas as pd
import matplotlib.pyplot as plt

data = pd.read_csv('process_trial.csv')
old_yield = data.loc[data['process'] == 'old', 'passed'].values[0] / data.loc[data['process'] == 'old', 'inspected'].values[0]
new_yield = data.loc[data['process'] == 'new', 'passed'].values[0] / data.loc[data['process'] == 'new', 'inspected'].values[0]

plt.bar(['Old', 'New'], [old_yield, new_yield])
plt.title('Yield Comparison')
plt.ylabel('Yield')
plt.ylim(0, 1)
plt.savefig('yield_chart.png')
plt.close()