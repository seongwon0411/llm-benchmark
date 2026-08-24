import pandas as pd
import matplotlib.pyplot as plt

data = pd.read_csv('maintenance_summary.csv')
plt.bar(data['line'], data['mtbf'])
plt.xlabel('Line')
plt.ylabel('MTBF')
plt.title('MTBF by Production Line')
plt.savefig('mtbf.png')