```markdown
# Security Review: auth.py

## 1. Hardcoded Password
- **Severity**: Critical
- **Scenario**: Password 'admin123' is hardcoded in the code. If leaked, grants full access.
- **Fix**: Use environment variables or secure secret management (e.g., Vault).

## 2. SQL Injection Vulnerability
- **Severity**: High
- **Scenario**: User input directly concatenated into SQL queries allows attackers to inject malicious commands.
- **Fix**: Use parameterized queries (e.g., `?` placeholders) instead of string concatenation.

## 3. Lack of Error Handling
- **Severity**: Medium
- **Scenario**: Unhandled database exceptions may expose sensitive error messages.
- **Fix**: Add try-except blocks to catch exceptions and log them securely.

## 4. Sensitive Data in Logs
- **Severity**: High
- **Scenario**: `print("LOGIN", user, password)` logs credentials in plain text.
- **Fix**: Remove debug prints or use logging with proper sanitization.
```