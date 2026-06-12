import asyncio
import sys
import os

# Add parent directory to path to allow importing db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.client import db

async def main():
    await db.connect()
    
    # List all users
    users = await db.user.find_many()
    print("USERS:")
    for u in users:
        print(f"ID: {u.id}, Email: {u.email}, Name: {u.name}, role: {u.role}")
    
    # List all appreciations
    apprs = await db.appreciation.find_many(include={"appreciationType": True})
    print("\nAPPRECIATIONS:")
    for a in apprs:
        print(f"ID: {a.id}, SenderID: {a.senderId}, Type: {a.appreciationType.name if a.appreciationType else a.appreciationTypeId}")

    recips = await db.appreciationrecipient.find_many()
    print("\nAPPRECIATION RECIPIENTS:")
    for r in recips:
        print(f"ID: {r.id}, AppreciationID: {r.appreciationId}, UserID: {r.userId}")

    await db.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
