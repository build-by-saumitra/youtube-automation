from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import User
from pydantic import BaseModel

router = APIRouter()

class UserSecretsRequest(BaseModel):
    username: str
    client_secrets_json: str

@router.get("/users")
def get_users(db: Session = Depends(get_db)):
    """Returns users and their hashed passwords for Streamlit Auth."""
    users = db.query(User).all()
    credentials = {"usernames": {}}
    for u in users:
        credentials["usernames"][u.username] = {
            "email": f"{u.username}@example.com",
            "name": u.name,
            "password": u.password_hash
        }
    return credentials

@router.post("/users/secrets")
def update_secrets(req: UserSecretsRequest, db: Session = Depends(get_db)):
    """Update a user's client_secrets.json."""
    user = db.query(User).filter_by(username=req.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.client_secrets_json = req.client_secrets_json
    db.commit()
    return {"status": "success"}

@router.get("/users/{username}/secrets")
def get_secrets(username: str, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(username=username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"client_secrets_json": user.client_secrets_json}
