# prisma/seed.py
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.client import db

APPRECIATION_TYPES = [
    {
        "name": "Team Player",
        "description": "Always shows up for the team, collaborates seamlessly, and lifts everyone around them.",
        "emojiPath": "assets/appreciation-emojis/team-player.svg",
        "displayOrder": 1,
    },
    {
        "name": "Problem Solver",
        "description": "Tackles tough challenges head-on and finds smart solutions when it matters most.",
        "emojiPath": "assets/appreciation-emojis/problem-solver.svg",
        "displayOrder": 2,
    },
    {
        "name": "Above & Beyond",
        "description": "Consistently goes the extra mile without being asked.",
        "emojiPath": "assets/appreciation-emojis/above-and-beyond.svg",
        "displayOrder": 3,
    },
    {
        "name": "Great Mentor",
        "description": "Invests time in others, shares knowledge generously, and helps people grow.",
        "emojiPath": "assets/appreciation-emojis/great-mentor.svg",
        "displayOrder": 4,
    },
    {
        "name": "Creative Thinker",
        "description": "Brings fresh ideas and innovative thinking to every problem.",
        "emojiPath": "assets/appreciation-emojis/creative-thinker.svg",
        "displayOrder": 5,
    },
    {
        "name": "Reliable Rock",
        "description": "Someone you can always count on — consistent, dependable, and steady under pressure.",
        "emojiPath": "assets/appreciation-emojis/reliable-rock.svg",
        "displayOrder": 6,
    },
    {
        "name": "Clutch Performer",
        "description": "Delivers when the stakes are high and deadlines are tight.",
        "emojiPath": "assets/appreciation-emojis/clutch-performer.svg",
        "displayOrder": 7,
    },
    {
        "name": "Customer Champion",
        "description": "Goes above and beyond for clients and always represents the team brilliantly.",
        "emojiPath": "assets/appreciation-emojis/customer-champion.svg",
        "displayOrder": 8,
    },
    {
        "name": "Quick Learner",
        "description": "Picks up new skills and adapts to change faster than anyone.",
        "emojiPath": "assets/appreciation-emojis/quick-learner.svg",
        "displayOrder": 9,
    },
    {
        "name": "Event Champion",
        "description": "Volunteers their time and energy to make office events and activities happen.",
        "emojiPath": "assets/appreciation-emojis/event-champion.svg",
        "displayOrder": 10,
    },
    {
        "name": "Helping Hand",
        "description": "Always there for colleagues personally — supportive, kind, and genuinely caring.",
        "emojiPath": "assets/appreciation-emojis/helping-hand.svg",
        "displayOrder": 11,
    },
    {
        "name": "Office Heartbeat",
        "description": "The person who keeps the energy, culture, and community alive in the workplace.",
        "emojiPath": "assets/appreciation-emojis/office-heartbeat.svg",
        "displayOrder": 12,
    },
]


async def seed():
    await db.connect()
    print("Seeding appreciation types...")

    for appreciation_type in APPRECIATION_TYPES:
        await db.appreciationtype.upsert(
            where={"name": appreciation_type["name"]},
            data={
                "create": {
                    "name": appreciation_type["name"],
                    "description": appreciation_type["description"],
                    "emojiPath": appreciation_type["emojiPath"],
                    "displayOrder": appreciation_type["displayOrder"],
                    "isActive": True,
                },
                "update": {
                    "description": appreciation_type["description"],
                    "emojiPath": appreciation_type["emojiPath"],
                    "displayOrder": appreciation_type["displayOrder"],
                },
            },
        )
        print(f"  ✓ {appreciation_type['name']}")

    print("Seeding complete.")
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(seed())