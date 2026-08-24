## 사고 요약

### 타임라인
- 14:02 모터 온도 86.7C, 고온 경고 발생 [incident_log:L3]
- 14:04 모터 온도 91.1C [incident_log:L4]
- 14:07 보호정지 발생 [incident_log:L5]
- 14:16 냉각 흡입구 분진 축적 확인 [incident_log:L6]
- 14:31 분진 제거 후 재가동 [incident_log:L7]

### 직접 트리거
- 90C 이상 지속 → 보호정지 동작 [manual:L3]
- 냉각 흡입구 분진 축적 [maintenance_note:L3]

### 가능한 근본원인
1. 냉각 유량 저하 (분진으로 인한 흡입구 막힘) [incident_log:L6] + [manual:L4]
2. 베어링 마찰 증가 (진동 데이터 누락 확인 불가) [maintenance_note:L4]
3. 과부하 가능성 (정비 기록 없음) [manual:L4]

### 확인 불가능한 항목
- 베어링 진동값 원본 누락 [maintenance_note:L4]
- 윤활 상태 이상 여부 [maintenance_note:L2]

### 다음 검증 조치
1. 냉각 시스템 정압 테스트 및 흡입구 청소 주기 점검 [maintenance_note:L3]
2. 베어링 진동 데이터 재수집 및 분석 [maintenance_note:L4]
3. 과부하 여부 확인을 위한 전력 측정 [manual:L2]