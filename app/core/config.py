import os
from cryptography.fernet import Fernet

def get_secret_key():
    secret = os.getenv("SECRET_KEY")
    if not secret:
        # Generate a new key if missing
        secret = Fernet.generate_key().decode()
        print("⚠️ WARNING: SECRET_KEY not set, generated a new one for this session.")
    else:
        try:
            # Validate secret
            Fernet(secret.encode() if isinstance(secret, str) else secret)
        except Exception:
            print("⚠️ WARNING: Invalid SECRET_KEY, generating a new one.")
            secret = Fernet.generate_key().decode()
    return secret

SECRET_KEY = get_secret_key()
