import secrets
from app.core.security import hash_token

class ApiKeyService:

    @staticmethod
    def generate_key():

        raw = "sk_live_" + secrets.token_urlsafe(32)

        prefix = raw[:12]

        hashed = hash_token(raw)

        return raw, prefix, hashed
