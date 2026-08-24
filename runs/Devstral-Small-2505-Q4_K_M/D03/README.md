공정 변경 시험을 분석해 `analysis.json`, `comparison.csv`, `yield_chart.png`를 생성하세요.
수율 = passed/inspected. 개선폭은 percentage point(pp)로 계산합니다.
양쪽 표본이 각각 1000개 이상이고 수율 개선폭이 2.0pp 이상이면 `recommend_new=true`.
연간 100,000개 생산을 가정했을 때 불량 감소로 절감되는 scrap cost를 계산하세요(다른 비용은 가정 금지).
analysis.json 필드: old_yield, new_yield, improvement_pp, recommend_new, annual_scrap_saving_won.
