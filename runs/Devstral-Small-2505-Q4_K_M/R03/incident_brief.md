# 사고 요약

## 타임라인
- 2026-07-14 13:30: 정기 윤활 작업 완료 [incident_log.txt:L1]
- 2026-07-14 13:58: 모터 온도 78.2C [incident_log.txt:L2]
- 2026-07-14 14:02: 모터 온도 86.7C, 고온 경고 발생 [incident_log.txt:L3]
- 2026-07-14 14:04: 모터 온도 91.1C [incident_log.txt:L4]
- 2026-07-14 14:07: 보호정지 발생 [incident_log.txt:L5]
- 2026-07-14 14:16: 냉각 흡입구에 분진 축적 확인 [incident_log.txt:L6]
- 2026-07-14 14:31: 분진 제거 후 재가동 [incident_log.txt:L7]
- 2026-07-14 14:45: 모터 온도 72.4C, 정상 운전 [incident_log.txt:L8]

## 직접 트리거
- 냉각 흡입구에 분진 축적 [incident_log.txt:L6]

## 가능한 근본원인
- 냉각 유량 저하 (분진 축적으로 인한) [manual.txt:L4]
- 베어링 마찰 증가 (정기 윤활 작업 후에도 발생 가능) [manual.txt:L4]

## 확인 불가능한 항목
- 베어링 진동값 (해당 시간대 수집 누락) [maintenance_note.txt:L4]

## 다음 검증조치
- 냉각 흡입구 청소 주기 재검토 및 강화 [maintenance_note.txt:L3]
- 베어링 상태 점검 및 기록 시스템 개선