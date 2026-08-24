import matplotlib.pyplot as plt

# 데이터 preparation
processes = ['Old', 'New']
yields = [96, 98.5]

# 차트 생성
plt.figure(figsize=(8, 5))
bars = plt.bar(processes, yields, color=['blue', 'green'])

# 라벨링
for bar in bars:
    height = bar.get_height()
    plt.text(bar.get_x() + bar.get_width()/2., height,
             f'{height}%', ha='center', va='bottom')

plt.title('Yield Comparison: Old vs New Process')
plt.ylabel('Yield Percentage (%)')
plt.ylim(0, 105)

# 저장
plt.savefig('yield_chart.png')