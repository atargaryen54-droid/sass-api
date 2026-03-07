from fastapi import HTTPException, status
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError, ExpiredSignatureError
from app.core.config import settings
import bcrypt
import hashlib

def hash_password(password: str) -> str:
  
    pwd_bytes = password.encode('utf-8')  
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": subject,
        "exp": expire,
        "type": "access"
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )

    payload = {
        "sub": subject,
        "exp": expire,
        "type": "refresh"
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str):
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
def hash_token(token: str) -> str:
    token_hash_pre = hashlib.sha256(token.encode('utf-8')).hexdigest()
    token_bytes = token_hash_pre.encode('utf-8')  
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(token_bytes, salt)
    
    return hashed.decode('utf-8')

def verify_token_hash(token: str, token_hash: str) -> bool:
    token_hash_pre = hashlib.sha256(token.encode('utf-8')).hexdigest()
    return bcrypt.checkpw(
        token_hash_pre.encode('utf-8'), 
        token_hash.encode('utf-8')
    )