"""One-shot script: create a web console admin user if the username doesn't exist.

Reads credentials from environment variables so they never appear in log output:
  CONSOLE_ADMIN_USER
  CONSOLE_ADMIN_PASSWORD
  CONSOLE_ADMIN_EMAIL
"""
import os
import sys

sys.path.insert(0, "/app")

from console.backend.database import SessionLocal
from console.backend.models.console_user import ConsoleUser
from console.backend.auth import hash_password

username = os.environ["CONSOLE_ADMIN_USER"]
password = os.environ["CONSOLE_ADMIN_PASSWORD"]
email    = os.environ["CONSOLE_ADMIN_EMAIL"]

db = SessionLocal()
try:
    existing = db.query(ConsoleUser).filter(ConsoleUser.username == username).first()
    if existing:
        print(f"User '{username}' already exists — skipping.")
        sys.exit(0)
    user = ConsoleUser(
        username=username,
        email=email,
        password_hash=hash_password(password),
        role="admin",
    )
    db.add(user)
    db.commit()
    print(f"Admin user '{username}' created successfully.")
finally:
    db.close()
