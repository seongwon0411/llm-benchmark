import matplotlib.pyplot as plt

lines = ['A', 'B', 'C']
mtbf_values = [180, 100, 146]

plt.figure(figsize=(8, 4))
plt.bar(lines, mtbf_values, color=['blue', 'red', 'green'])
plt.title('MTBF by Line')
plt.ylabel('MTBF (hours)')
plt.savefig('mtbf.png')
plt.close()