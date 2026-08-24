`maintenance_kpi.csv`에서 line별 MTBF와 MTTR을 계산하고 `analysis.json`, `maintenance_summary.csv`, `mtbf.png`를 생성하세요.
정의: MTBF = operating_hours / failures. MTTR(hours) = repair_minutes / 60 / failures.
analysis.json 필드: line_A_mtbf, line_B_mtbf, line_C_mtbf, line_A_mttr_h, line_B_mttr_h, line_C_mttr_h, priority_line.
priority_line은 MTBF가 가장 낮은 라인입니다.
