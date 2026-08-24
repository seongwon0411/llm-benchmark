# Security Review for auth.py

## 1. Hardcoded Password
- **Severity**: High
- **Scenario**: If an attacker gains access to the source code, they can easily retrieve the hardcoded password `admin123` and use it to authenticate as an admin.
- **Recommendation**: Store passwords in a secure configuration file or environment variable. Use encryption if necessary.

## 2. SQL Injection Vulnerability
- **Severity**: Critical
- **Scenario**: The code constructs SQL queries by concatenating user input directly into the query string, which makes it vulnerable to SQL injection attacks. An attacker could manipulate the `user` or `password` parameters to execute arbitrary SQL commands.
- **Recommendation**: Use parameterized queries or prepared statements instead of string concatenation to construct SQL queries.

## 3. Lack of Input Validation
- **Severity**: Medium
- **Scenario**: The code does not validate the input for the `user` and `password` parameters. This could lead to unexpected behavior or errors if the input contains special characters or is too long.
- **Recommendation**: Implement input validation to ensure that the `user` and `password` parameters meet expected criteria (e.g., length, character set).

## 4. Insufficient Logging
- **Severity**: Low
- **Scenario**: The code only prints login attempts to the console, which is not sufficient for auditing or monitoring purposes. If the application runs in a production environment, these logs may not be accessible.
- **Recommendation**: Implement proper logging mechanisms to record login attempts and other important events. Consider using a centralized logging system.