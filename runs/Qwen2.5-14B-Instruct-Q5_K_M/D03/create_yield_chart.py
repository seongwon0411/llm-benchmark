import matplotlib.pyplot as plt

processes = ['old', 'new']
yield_rates = [0.96, 0.985]

plt.figure(figsize=(10, 6))
plt.bar(processes, yield_rates)
plt.title('Yield Rate Comparison')
plt.xlabel('Process')
plt.ylabel('Yield Rate')
plt.ylim(0, 1)

plt.savefig('yield_chart.png', dpi=300)