import matplotlib.pyplot as plt

processes = ['Old', 'New']
yields = [0.96, 0.985]

plt.figure(figsize=(6,4))
plt.bar(processes, yields, color=['#ff7f0e', '#1f77b4'])
plt.ylabel('Yield')
plt.title('Process Yield Comparison')
plt.ylim(0.9, 1.0)
plt.savefig('yield_chart.png')
plt.close()