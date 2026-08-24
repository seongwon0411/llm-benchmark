# Security Review

## Issue 1: Hardcoded Credentials (Severity: High)
- **Scenario**: The `PASSWORD` variable is stored as plaintext in code. If the file is exposed, attackers can directly access credentials.
- **Fix**: Use environment variables or secure secret management systems.

## Issue 2: SQL Injection Vulnerability (Severity: Critical)
- **Scenario**: User input is directly concatenated into SQL queries (`user` and `password`). Attackers could inject malicious payloads like `' OR '1'='1 to bypass authentication.
- **Fix**: Use parameterized queries with `?` placeholders.

## Issue 3: Audit Log SQL Injection (Severity: Critical)
- **Scenario**: The audit log update also uses string concatenation for `user`, allowing attackers to inject malicious SQL commands.
- **Fix**: Apply parameterization to all database operations.

## Issue 4: Lack of Password Hashing (Severity: Medium)
- **Scenario**: Passwords are stored and compared as plaintext. If the database is compromised, all passwords are exposed.
- **Fix**: Implement cryptographic hashing (e.g., bcrypt) for password storage and verification.