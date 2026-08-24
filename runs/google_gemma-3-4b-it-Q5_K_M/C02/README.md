# Time-series leakage fix
`pipeline.py`의 미래정보 누수와 split 경계 중복을 수정하세요. 테스트는 수정 금지이며 최종 채점에는 추가 회귀 테스트도 사용됩니다.
`make_feature`는 현재 시점 포함 과거 데이터만 사용해야 합니다.
