import sqlite3
PASSWORD = "admin123"

def login(conn, user, password):
    print("LOGIN", user, password)
    sql = "SELECT role FROM users WHERE name='" + user + "' AND password='" + password + "'"
    row = conn.execute(sql).fetchone()
    if row:
        conn.execute("UPDATE audit SET last_user='" + user + "'")
        return row[0]
    return None
