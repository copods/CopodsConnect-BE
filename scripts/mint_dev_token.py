# scripts/mint_dev_token.py
# DEV ONLY — mints a JWT for local Postman/testing. Do not use in production.

import asyncio
import os
import sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, ".env"))


async def main() -> None:
    from db.client import db
    from services.auth_service import _create_jwt

    email = sys.argv[1] if len(sys.argv) > 1 else os.getenv("DEV_USER_EMAIL")
    platform = sys.argv[2] if len(sys.argv) > 2 else "app"

    if not email:
        print("Usage: python scripts/mint_dev_token.py user@copods.co [app|panel]")
        print("   or set DEV_USER_EMAIL in .env")
        return

    if platform not in ("app", "panel"):
        print("Platform must be 'app' or 'panel'")
        return

    await db.connect()
    try:
        user = await db.user.find_unique(where={"email": email})
    finally:
        await db.disconnect()

    if not user:
        print(f"No user found for: {email}")
        return

    token = _create_jwt(user, platform)

    print("")
    print(f"--- DEV {platform.upper()} TOKEN ---")
    print(f"User:  {user.email}")
    print(f"ID:    {user.id}")
    print(f"Role:  {user.role}")
    print("")
    print(token)
    print("")


if __name__ == "__main__":
    asyncio.run(main())