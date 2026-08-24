# 보안 리뷰 결과

## 문제 1: SQL Injection 취약점 (Critical)
**Severity**: Critical
**시나리오**: 악의적인 사용자가 `user` 또는 `password`에 SQL injection 코드를 삽입하여 데이터베이스 조회/수정을 수행.
- 예: `admin' --`로 로그인 시 `role` 조회를 종료하고 임의의 데이터를 반환할 수 있다.

**수정 방향**: 인자 바인딩을 사용한 Prepared Statement로 수정:
```python
sql = "SELECT role FROM users WHERE name=? AND password=?"
row = conn.execute(sql, (user, password)).fetchone()
```

--- 
## 문제 2: 로그 기록 미완료 (High)
**Severity**: High
**시나리오**: 로그인 실패 시 `audit` 테이블에 기록이 남지 않음 → 공격자 추적 불가.
- 예: `admin' OR '1'='1`로 무효 로그인 시 오류가 발생하지 않는다.

**수정 방향**: 실패 시에도 audit 기록을 추가:
```python
if not row:
    conn.execute("UPDATE audit SET last_user='" + user + "', status='failed'")
```

--- 
## 문제 3: 비밀번호 노출 (Medium)
**Severity**: Medium
**시나리오**: `PASSWORD` 상수에 `admin123`가 명시적으로 저장되어 있음 → 암호 해독 가능.
- 예: 파일의 내용이 유출되면 모든 사용자 계정의 비밀번호를 도용할 수 있다.

**수정 방향**: 환경 변수나 암호화로 관리:
```python
import os
PASSWORD = os.getenv("DB_PASSWORD")  # DB에서 가져오거나 암호화
```

--- 
## 문제 4: audit 테이블 수정 취약 (Medium)
**Severity**: Medium
**시나리오**: `audit` 테이블에 `last_user`만 기록되면, 다른 사용자가 로그인 시점 조회가 불가능.
- 예: `admin`의 마지막 로그인이 `user1`로 기록되어 있지만 실제로는 `user2`가 사용 중일 수 있다.

**수정 방향**: `audit` 테이블에 `last_login_time`을 추가하여 시간 기반 추적:
```python
conn.execute("UPDATE audit SET last_user='" + user + "', last_login_time=NOW()")
```