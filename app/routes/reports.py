from fastapi import APIRouter, Depends
from app.routes.auth import get_current_user

router = APIRouter()

@router.get("/me")
async def read_me(current_user = Depends(get_current_user)):
    return {"id": current_user.id, "username": current_user.username, "role": current_user.role}
