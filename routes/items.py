from fastapi import APIRouter
from schemas import APIResponse

router = APIRouter()

@router.get("/items", response_model=APIResponse)
async def get_items():
    try:
        items = ["item1", "item2"]

        return APIResponse(
            data=items,
            msg="Items fetched successfully",
            status=True,
            err=None
        )

    except Exception as e:
        return APIResponse(
            data=None,
            msg="Failed to fetch items",
            status=False,
            err=str(e)
        )