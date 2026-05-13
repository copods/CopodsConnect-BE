# db/client.py
from prisma import Prisma

# Single shared Prisma client instance for the entire application.
# Import this db object wherever you need database access.
# Connection lifecycle (connect/disconnect) is managed in main.py via lifespan.
#
# Usage in any service or route:
#   from db.client import db
#   user = await db.user.find_unique(where={"id": user_id})

db = Prisma()