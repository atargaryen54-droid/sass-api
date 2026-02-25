from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def health_check():
    return {"status":"alive"}


from app.core.database import engine
from sqlalchemy import text

@app.get("/db-check")
def db_check():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return {"db": "connected"}
