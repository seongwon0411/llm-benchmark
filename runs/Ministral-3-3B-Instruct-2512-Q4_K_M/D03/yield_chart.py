# yield_chart.py
import pandas as pd
import matplotlib.pyplot as plt

data = {
    "process": ["old", "new"],
    "passed": [960, 985],
    "inspected": [1000, 1000]
}

# Pass rate 계산
df = pd.DataFrame(data)
df["pass_rate_percentage"] = (df["passed"] / df["inspected"]) * 100

plt.figure(figsize=(8, 5))
plt.bar(df["process"], df["pass_rate_percentage"], color=['#4CAF50', '#2196F3'])
plt.title("Pass Rate Comparison (Old vs New Process)")
plt.ylabel("% Passed")
plt.ylim(90, 100)
plt.grid(axis='y', linestyle='--', alpha=0.7)
plt.savefig("yield_chart.png", bbox_inches='tight')
print("yield_chart.png 생성 완료!")