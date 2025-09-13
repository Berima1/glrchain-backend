from fastapi import APIRouter
router = APIRouter()
@router.get('/stats')
async def stats():
    return {'incidents': 0, 'verified': 0}
