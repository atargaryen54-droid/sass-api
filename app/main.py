from fastapi import FastAPI
from app.api.routes import auth
from app.core.database import engine
from sqlalchemy import text
from fastapi import Depends
from app.api.deps import get_current_user
from app.models.user import User
from sqladmin import Admin, ModelView
from app.api.routes import api_keys
from app.api.routes import clients
from app.api.routes import projects



app = FastAPI()

app.include_router(auth.router)
app.include_router(api_keys.router)
app.include_router(clients.router)
app.include_router(projects.router)



@app.get("/")
def health_check():
    return {"status":"alive"}

@app.get("/db-check")
def db_check():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT 1"))
        return {"db": "connected"}
 
    
@app.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email
    }

admin = Admin(app, engine)

class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email]

admin.add_view(UserAdmin)

