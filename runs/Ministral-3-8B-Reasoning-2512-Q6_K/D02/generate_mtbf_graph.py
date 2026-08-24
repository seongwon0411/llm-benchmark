import matplotlib.pyplot as plt

# MTBF 데이터
lines = ["A", "B", "C"]
mtbf_values = [180, 100, 146]

# 그래프 생성
plt.figure(figsize=(8, 5))
plt.bar(lines, mtbf_values, color=['blue', 'red', 'green'])
plt.title('MTBF by Line')
plt.xlabel('Line')
plt.ylabel('MTBF (hours)')
plt.ylim(0, max(mtbf_values) * 1.2)  # 그래프의 y축 범위 조정

# 그래프 저장
plt.savefig('mtbf.png')