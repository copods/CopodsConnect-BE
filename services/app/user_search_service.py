# services/app/user_search_service.py
from db.client import db

MAX_SEARCH_RESULTS = 100


async def search_users(query: str, current_user_id: str) -> list[dict]:
    base_where = {
        "hasLoggedInApp": True,
        "deletedAt": None,
        "isBanned": False,
        "id": {"not": current_user_id},
    }

    q = (query or "").strip()

    if not q:
        # @ only — return all eligible users, alphabetical
        users = await db.user.find_many(
            where=base_where,
            take=MAX_SEARCH_RESULTS,
            order={"name": "asc"},
        )
    else:
        users = await db.user.find_many(
            where={
                **base_where,
                "OR": [
                    {"name": {"contains": q, "mode": "insensitive"}},
                    {"email": {"contains": q, "mode": "insensitive"}},
                ],
            },
            take=MAX_SEARCH_RESULTS,
            order={"name": "asc"},
        )

    return [
        {
            "id": u.id,
            "name": u.name,
            "picture": u.picture,
            "designation": u.designation,
        }
        for u in users
    ]