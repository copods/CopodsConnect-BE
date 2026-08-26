import asyncio
import os
import sys

# Add the parent directory to sys.path so we can import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
# Load environment variables
load_dotenv(override=True)

from db.client import db
from jobs.unban_job import clear_expired_bans
from jobs.purge_soft_deleted_job import purge_soft_deleted_users
from jobs.daily_celebration_job import create_daily_celebration_posts
from jobs.leaderboard_digest_job import send_most_appreciated_monthly
from services.app.post_service import recover_stuck_pending_posts

class MockBackgroundTasks:
    def __init__(self):
        self.tasks = []
    def add_task(self, func, *args, **kwargs):
        self.tasks.append((func, args, kwargs))
    async def run_all(self):
        for func, args, kwargs in self.tasks:
            if asyncio.iscoroutinefunction(func):
                await func(*args, **kwargs)
            else:
                func(*args, **kwargs)

async def test_all_jobs():
    print("Connecting to database...")
    await db.connect()
    
    try:
        print("\n--- 1. Testing clear_expired_bans ---")
        await clear_expired_bans()
        print("✅ Finished clear_expired_bans")
        
        print("\n--- 2. Testing purge_soft_deleted_users ---")
        await purge_soft_deleted_users()
        print("✅ Finished purge_soft_deleted_users")
        
        print("\n--- 3. Testing create_daily_celebration_posts ---")
        await create_daily_celebration_posts()
        print("✅ Finished create_daily_celebration_posts")
        
        print("\n--- 4. Testing send_most_appreciated_monthly ---")
        await send_most_appreciated_monthly()
        print("✅ Finished send_most_appreciated_monthly")
        
        print("\n--- 5. Testing recover_stuck_pending_posts ---")
        bg_tasks = MockBackgroundTasks()
        await recover_stuck_pending_posts(bg_tasks)
        await bg_tasks.run_all()
        print("✅ Finished recover_stuck_pending_posts")
        
    except Exception as e:
        print(f"❌ Error while running jobs: {e}")
    finally:
        print("\nDisconnecting from database...")
        await db.disconnect()

if __name__ == "__main__":
    print("Starting Job Tester...")
    asyncio.run(test_all_jobs())
