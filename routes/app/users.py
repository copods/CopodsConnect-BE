# routes/app/users.py
from fastapi import APIRouter, Depends, Query
from middlewares.auth import get_current_user, require_platform
from services.app import user_search_service
from utils.ApiResponse import api_response

app_users_router = APIRouter(
    prefix="/app/users",
    tags=["App Users"],
    dependencies=[Depends(require_platform("app"))],
)


@app_users_router.get("/search")
async def search_users(
    q: str = Query(default=""),
    current_user=Depends(get_current_user),
):
    result = await user_search_service.search_users(q.strip(), current_user.id)
    return api_response(200, result, "Users fetched successfully")