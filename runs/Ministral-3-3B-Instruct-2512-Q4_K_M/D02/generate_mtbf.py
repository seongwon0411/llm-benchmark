# MTBF Comparison Graph
import matplotlib.pyplot as plt
import pandas as pd

data = {
    "line": ["A", "B", "C"],
    "mTBF": [180, 700/7, 730/5],
    "repair_time": [180, 420, 250]
}
df = pd.DataFrame(data)

plt.figure(figsize=(8, 6))
plt.bar(df.index, df["mTBF"], color=['blue', 'red', 'green'], alpha=0.7, label="MTBF (hours)")
plt.scatter(df.index, df["repair_time"], color='black', label="Avg Repair Time")
plt.title("Mean Time Between Failures (mTBF) Comparison")
plt.xlabel("Line")
plt.ylabel("Hours/Minutes")
plt.legend()
plt.grid(True, linestyle='--', alpha=0.6)
plt.savefig("mtbf.png", bbox_inches="tight")
plt.close()