# -*- coding: utf-8 -*-
import benchmark as b

tasks = {t["id"]: t for t in b.ALL_TASKS}

def check(name, cond, detail=""):
    if not cond:
        raise AssertionError(f"{name} FAILED: {detail}")
    print(f"[PASS] {name}")

# v6.3 retained tests ------------------------------------------------
c04_good = """
from collections import OrderedDict
def dedup(xs):
    return list(OrderedDict.fromkeys(xs))
평균 시간복잡도는 O(n)이다.
"""
s, r = b.objective_score(tasks["C04"], c04_good)
check("C04 OrderedDict alternative", s == 100.0, (s, r))

d04_good = """
```python
line_avg = df.groupby('line')['defect_rate'].mean()
filtered = line_avg[line_avg > 0.03]
result = filtered.sort_values(ascending=False)
```
"""
s, r = b.objective_score(tasks["D04"], d04_good)
check("D04 separate aggregate pipeline", s == 100.0, (s, r))

d04_bad = """
```python
result = df[df['defect_rate'].groupby(df['line']).mean() > 0.03].sort_values('line', ascending=False)
```
"""
s, r = b.objective_score(tasks["D04"], d04_bad)
check("D04 rejects row-filter/sort-line bug", s < 100.0, (s, r))

# v6.4: the real SmolLM3 chained expression must score 100.
d04_chain = """
```python
mean_defect_rates = df.groupby('line')['defect_rate'].mean()
high_mean_lines = mean_defect_rates[mean_defect_rates > 0.03].sort_values(ascending=False)
print(high_mean_lines)
```
"""
s, r = b.objective_score(tasks["D04"], d04_chain)
check("D04 chained aggregate filter+sort", s == 100.0, (s, r))

# W02: numbered list markers must not inflate sentence count.
w02_numbered = """1. 벡터 데이터베이스는 문서의 의미를 숫자 벡터로 표현합니다.
2. 비슷한 의미의 문서는 이 숫자 공간에서도 서로 가까운 위치에 놓입니다.
3. 그래서 질문과 가까운 문서를 찾아 비슷한 내용을 검색할 수 있습니다."""
check("W02 numbered 3 sentences", b._sentence_count(w02_numbered) == 3, b._sentence_count(w02_numbered))

# PPT formats
slides_markdown = """
#### Slide 1: 제목
- 핵심 A
- 핵심 B
#### Slide 2: 로컬
- 핵심 A
- 핵심 B
#### Slide 3: 클라우드
- 핵심 A
- 핵심 B
#### Slide 4: VRAM
- 핵심 A
- 핵심 B
#### Slide 5: 멀티에이전트
- 핵심 A
- 핵심 B
"""
c, d = b._slide_count(slides_markdown)
check("Slide markdown parser", c == 5, (c, d))

slides_ppt_chapter = """
## PPT 제1장: 로컬 LLM
- **핵심 내용:**
  - 포인트 A
  - 포인트 B
## PPT 제2장: 클라우드 비교
- **핵심 내용:**
  - 포인트 A
  - 포인트 B
## PPT 제3장: VRAM
- **핵심 내용:**
  - 포인트 A
  - 포인트 B
## PPT 제4장: 양자화
- **핵심 내용:**
  - 포인트 A
  - 포인트 B
## PPT 제5장: 멀티에이전트
- **핵심 내용:**
  - 포인트 A
  - 포인트 B
"""
c, d = b._slide_count(slides_ppt_chapter)
check("PPT 제N장 parser", c == 5, (c, d))
counts = b._slide_key_point_counts(slides_ppt_chapter)
check("P03 exact two points each", all(n == 2 for _, n in counts) and len(counts) == 5, counts)

# Real Qwen2.5-Coder P03: only presenter role, no actual talking points.
p03_empty = """
1. 로컬 LLM 소개
   - 발표자: AI 개발자
2. 클라우드 LLM vs 로컬 LLM
   - 발표자: 데이터 과학자
3. VRAM의 의미와 사용
   - 발표자: 디지털 시스템 설계자
4. 양자화의 개념과 활용
   - 발표자: 컴퓨터 프로그래밍 엔지니어
5. 멀티에이전트에서 모델 배치 이유
   - 발표자: 머신러닝 연구원
"""
hs, cap, rows = b.evaluate_hard_checks(tasks["P03"], p03_empty)
check("P03 presenter-only answer penalized", hs <= 60 and cap is not None and cap <= 80, (hs, cap, rows))

# R03: wrong A/B selections from the actual smoke run must hit cap.
r03_b_wrong = """센서 B는 모든 요구 조건을 충족합니다: 측정범위는 맞고 정확도 ±1.0°C은 ±0.8°C 이내를 만족하며 샘플링 50Hz입니다.
센서 A는 -30°C를 지원하지 않고 10Hz라서 탈락합니다.
따라서 선택할 센서는 센서 B입니다."""
hs, cap, rows = b.evaluate_hard_checks(tasks["R03"], r03_b_wrong)
check("R03 wrong B selection cap", cap is not None and cap <= 40, (hs, cap, rows))

r03_a_wrong = """[자료A] 센서는 -30°C 환경에서 정확도 ±0.5°C 이내로 측정할 수 있으며 샘플링 10Hz 이상으로 충분합니다. 따라서 요구조건을 모두 만족하는 센서입니다.
[자료B] 센서는 정확도 ±1.0°C라 탈락합니다.
따라서 [자료A] 센서는 요구조건을 모두 만족하며 사용할 수 있습니다."""
hs, cap, rows = b.evaluate_hard_checks(tasks["R03"], r03_a_wrong)
check("R03 wrong A selection cap", cap is not None and cap <= 40, (hs, cap, rows))

# W03: natural "권장" wording should pass direction checks.
w03_good_direction = """예산이 가장 중요할 때는 초기비용이 낮은 B안을 권장합니다. 정확도가 가장 중요할 때는 96%인 A안을 권장합니다."""
hs, cap, rows = b.evaluate_hard_checks(tasks["W03"], w03_good_direction)
direction_rows = [r for r in rows if "권고" in r["label"]]
check("W03 natural 권장 wording", all(r["ok"] for r in direction_rows), direction_rows)

# W03: false maintenance-cost comparison must be caught.
w03_bad_cost = """예산이 가장 중요할 때 B안을 권장합니다. B안의 연간 유지비 2천만원은 낮아 운영비가 적습니다. 정확도가 중요하면 A안을 권장합니다."""
hs, cap, rows = b.evaluate_hard_checks(tasks["W03"], w03_bad_cost)
check("W03 reversed maintenance-cost claim", cap is not None and cap <= 65, (hs, cap, rows))

# Keep prior K03/K04 protections.
k03 = tasks["K03"]
hs, cap, rows = b.evaluate_hard_checks(k03, "모순은 없습니다. 6주와 8주가 일치하지 않는 부분은 있습니다.")
check("K03 denial cap", cap is not None and cap <= 40, (hs, cap, rows))

k04 = tasks["K04"]
hs, cap, rows = b.evaluate_hard_checks(k04, "이 코드는 SQL 인젝션에 취약하므로 parameterized query를 사용해야 합니다.")
check("K04 password omission cap", cap is not None and cap <= 60, (hs, cap, rows))

print("SCORER SELF TEST PASSED")
