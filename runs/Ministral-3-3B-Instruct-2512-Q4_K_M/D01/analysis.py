# CSV를 읽고 분석한 후 JSON/CSV/PNG 파일을 생성합니다.
import pandas as pd
import matplotlib.pyplot as plt
import json

# CSV 파일 읽기
df = pd.read_csv("factory_kpi.csv")

# 1. analysis.json: 전체 데이터 통계 요약 (정수/실수만 저장)
analysis_data = {
    "total_units_inspected": int(df["units_inspected"].sum()),
    "total_defects": int(df["defects"].sum()),
    "average_defect_rate": float((df["defects"] / df["units_inspected"]).mean()),
    "total_downtime_minutes": int(df["downtime_min"].sum()),
    "pilot_lines_count": df[df["pilot"]].shape[0],
}

# JSON 파일 생성
with open("analysis.json", "w") as f:
    json.dump(analysis_data, f, indent=4)

# 2. yearly_summary.csv: 연도별 요약 데이터 (Series를 직접 정수형으로 변환)
yearly_summary = df.groupby("year").agg({
    "units_inspected": lambda x: int(x.sum()),
    "defects": lambda x: int(x.sum()),
    "downtime_min": lambda x: int(x.sum())
}).reset_index()

with open("yearly_summary.csv", "w") as f:
    yearly_summary.to_csv(f, index=False)

# 3. trend.png: 연도별 KPI 트렌드 (수량 + 결함율 차트)
plt.figure(figsize=(12, 6))

# 수량 차트
ax1 = plt.subplot(2, 1, 1)
df.groupby("year")["units_inspected"].sum().plot(kind="bar", ax=ax1)
ax1.set_title("Units Inspected by Year")
ax1.set_ylabel("Total Units")

# 결함율 차트
defect_rate = (df.groupby("year")["defects"] / df.groupby("year")["units_inspected"] * 100)
ax2 = plt.subplot(2, 1, 2)
defect_rate.plot(kind="bar", ax=ax2)
ax2.set_title("Defect Rate (%) by Year")
ax2.set_ylabel("Defect Rate (%)")

plt.tight_layout()
plt.savefig("trend.png")