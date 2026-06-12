import asyncio
import sys
import os

# Add parent directory to path to allow importing db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.client import db
from services.user_service import serialize_user_with_counts

async def main():
    await db.connect()
    
    users = await db.user.find_many()
    for u in users:
        data = await serialize_user_with_counts(u)
        print(f"Email: {u.email}")
        print(f"  appreciationGivenCount (Given): {data['appreciationGivenCount']}")
        print(f"  appreciationReceivedCount (Appreciated): {data['appreciationReceivedCount']}")
        print("-" * 40)

    await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
