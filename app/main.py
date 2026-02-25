from fastapi import FastAPI
from app.api.routes import auth



app = FastAPI()

app.include_router(auth.router)


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
