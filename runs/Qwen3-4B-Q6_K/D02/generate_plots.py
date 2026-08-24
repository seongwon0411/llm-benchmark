import matplotlib.pyplot as plt

times = ['A', 'B', 'C']
mtbf_values = [180, 100, 146]

plt.bar(times, mtbf_values)
plt.xlabel('Line')
plt.ylabel('MTBF (hours)')
plt.title('MTBF Comparison by Line')
plt.savefig('mtbf.png')
plt.close()