# Procurement Recommendation Report

## Criteria & Thresholds
- **Total 2‑year cost** ≤ KRW 20,000,000 (budget limit)
- **SLA ≥ 99.90%**
- **On‑premise support required** = Yes
- **Implementation/Build cost** = No additional fees
- **Vendor must satisfy *all* mandatory criteria** to be considered viable.

## Vendor Evaluation (excerpted lines)
### Vendor A
- **Lines**: `vendor_A.txt:L2` 7,500 million KRW annual license fee
- **Total 2‑year cost**: 7,500 × 2 = **15,000 M**
- **SLA**: L3 says *99.95%* → meets threshold
- **On‑premise support**: L4 says *지원* (Yes) → passes mandatory
- **Implementation cost**: None → OK
- **Overall score**: Meets **all** criteria.

### Vendor B
- **Lines**: `vendor_B.txt:L2` 9,000 million KRW annual license fee
- **Total 2‑year cost**: 9,000 × 2 = **18,000 M**
- **SLA**: L3 says *99.90%* → meets threshold
- **On‑premise support**: L4 says *지원* (Yes) → passes mandatory
- **Implementation cost**: None → OK
- **Overall score**: Meets **all** criteria.

### Vendor C
- **Lines**: `vendor_C.txt:L2` 6,000 million KRW annual license fee
- **Total 2‑year cost**: 6,000 × 2 = **12,000 M**
- **SLA**: L3 says *99.99%* → meets threshold
- **On‑premise support**: L4 says *고객사 온프레미스 설치 불가* (No) → **fails mandatory**
- **Implementation cost**: None → OK
- **Overall score**: **Rejected** due to missing on‑premise support.

## Recommendation
Based on the above analysis, **both Vendor A and Vendor B satisfy every required condition** (budget, SLA, on‑premise support, zero implementation fees). Vendor C is disqualified because it cannot provide on‑premise deployment as requested.\n\n**Recommended vendors:**
- **Vendor A** – Total 2‑year cost: KRW **15,000,000**\n- **Vendor B** – Total 2‑year cost: KRW **18,000,000**\n\n*Prepared by automated procurement assistant. All figures are derived directly from the supplied vendor documents.*