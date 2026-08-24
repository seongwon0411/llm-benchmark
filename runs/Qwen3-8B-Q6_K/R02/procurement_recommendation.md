## 구매 추천 보고서

### 1. 요구조건 요약
- 2년 총 라이선스 비용: 2억원 이하 [requirements.txt:L1]
- SLA: 99.90% 이상 [requirements.txt:L2]
- 온프레미스 배포 필수 [requirements.txt:L3]
- P1 기술지원 응답시간: 4시간 이내 [requirements.txt:L4]

### 2. 벤더 평가
#### Vendor A
- 총비용: 7,500만원/년 × 2년 = **1억5천만원** [vendor_A.txt:L2]
- SLA: 99.95% → 충족 [vendor_A.txt:L3]
- 온프레미스: 지원 [vendor_A.txt:L4]
- P1 응답시간: 8시간 → **불충족** [vendor_A.txt:L5]
> 탈락 (P1 응답시간 초과)

#### Vendor B
- 총비용: 9,000만원/년 × 2년 = **1억8천만원** [vendor_B.txt:L2]
- SLA: 99.90% → 충족 [vendor_B.txt:L3]
- 온프레미스: 지원 [vendor_B.txt:L4]
- P1 응답시간: 2시간 → **충족** [vendor_B.txt:L5]
> 적합 (모든 조건 충족)

#### Vendor C
- 총비용: 6,000만원/년 × 2년 = **1억2천만원** [vendor_C.txt:L2]
- SLA: 99.99% → 충족 [vendor_C.txt:L3]
- 온프레미스: **불가능** (SaaS 전용) [vendor_C.txt:L4]
- P1 응답시간: 1시간 → **충족** [vendor_C.txt:L5]
> 탈락 (온프레미스 미지원)

### 3. 최종 추천
✅ **Vendor B**만 모든 요구조건을 충족합니다.

