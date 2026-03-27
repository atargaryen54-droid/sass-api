from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.core.security import verify_token_hash

from app.models.api_key import ApiKey



reusable_oauth2 = HTTPBearer()

def get_client_from_api_key(
    auth: HTTPAuthorizationCredentials = Security(reusable_oauth2),
    db: Session = Depends(get_db)
):
    raw_key = auth.credentials

    if not raw_key.startswith("sk_"):
        raise HTTPException(status_code=401, detail="Invalid API key format")

    # 1. Extract prefix 
    prefix = raw_key[:12]

    # 2. Lookup key and Join Client in ONE query
    key_record = db.query(ApiKey).options(
        joinedload(ApiKey.client) 
    ).filter(ApiKey.key_prefix == prefix).first()

    if not key_record:
        raise HTTPException(status_code=401, detail="Invalid API credentials")

    # 3. Verify hash using the raw_key vs the stored hash
    if not verify_token_hash(raw_key, key_record.key_hash):
         raise HTTPException(status_code=401, detail="Invalid API credentials")

    # 4. Check if client exists (if not loaded via joinedload)
    if not key_record.client:
        raise HTTPException(status_code=401, detail="Client account inactive")

    return key_record.client