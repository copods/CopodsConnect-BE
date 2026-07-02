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
        "emojiPath": "assets/appreciation-emojis/team_player.svg",
        "badgePath": "assets/appreciation-badges/team_player.png",
        "displayOrder": 1,
        "badgePath": "assets/appreciation-badges/team_player.png",
    },
    {
        "name": "Problem Solver",
        "description": "Tackles tough challenges head-on and finds smart solutions when it matters most.",
        "emojiPath": "assets/appreciation-emojis/problem_solver.svg",
        "badgePath": "assets/appreciation-badges/problem_solver.png",
        "displayOrder": 2,
        "badgePath": "assets/appreciation-badges/problem_solver.png",
    },
    {
        "name": "Above & Beyond",
        "description": "Consistently goes the extra mile without being asked.",
        "emojiPath": "assets/appreciation-emojis/above_and_beyond.svg",
        "badgePath": "assets/appreciation-badges/above_and_beyond.png",
        "displayOrder": 3,
        "badgePath": "assets/appreciation-badges/above_and_beyond.png",
    },
    {
        "name": "Great Mentor",
        "description": "Invests time in others, shares knowledge generously, and helps people grow.",
        "emojiPath": "assets/appreciation-emojis/great_mentor.svg",
        "badgePath": "assets/appreciation-badges/great_mentor.png",
        "displayOrder": 4,
        "badgePath": "assets/appreciation-badges/great_mentor.png",
    },
    {
        "name": "Creative Thinker",
        "description": "Brings fresh ideas and innovative thinking to every problem.",
        "emojiPath": "assets/appreciation-emojis/creative_thinker.svg",
        "badgePath": "assets/appreciation-badges/creative_thinker.png",
        "displayOrder": 5,
        "badgePath": "assets/appreciation-badges/creative_thinker.png",
    },
    {
        "name": "Reliable Rock",
        "description": "Someone you can always count on — consistent, dependable, and steady under pressure.",
        "emojiPath": "assets/appreciation-emojis/reliable_rock.svg",
        "badgePath": "assets/appreciation-badges/reliable_rock.png",
        "displayOrder": 6,
        "badgePath": "assets/appreciation-badges/reliable_rock.png",
    },
    {
        "name": "Clutch Performer",
        "description": "Delivers when the stakes are high and deadlines are tight.",
        "emojiPath": "assets/appreciation-emojis/clutch_performer.svg",
        "badgePath": "assets/appreciation-badges/clutch_performer.png",
        "displayOrder": 7,
        "badgePath": "assets/appreciation-badges/clutch_performer.png",
    },
    {
        "name": "Customer Champion",
        "description": "Goes above and beyond for clients and always represents the team brilliantly.",
        "emojiPath": "assets/appreciation-emojis/customer_champion.svg",
        "badgePath": "assets/appreciation-badges/customer_champion.png",
        "displayOrder": 8,
        "badgePath": "assets/appreciation-badges/customer_champion.png",
    },
    {
        "name": "Quick Learner",
        "description": "Picks up new skills and adapts to change faster than anyone.",
        "emojiPath": "assets/appreciation-emojis/quick_learner.svg",
        "badgePath": "assets/appreciation-badges/quick_learner.png",
        "displayOrder": 9,
        "badgePath": "assets/appreciation-badges/quick_learner.png",
    },
    {
        "name": "Event Champion",
        "description": "Volunteers their time and energy to make office events and activities happen.",
        "emojiPath": "assets/appreciation-emojis/event_champion.svg",
        "badgePath": "assets/appreciation-badges/event_champion.png",
        "displayOrder": 10,
        "badgePath": "assets/appreciation-badges/event_champion.png",
    },
    {
        "name": "Lifeline",
        "description": "Always there for colleagues personally — supportive, kind, and genuinely caring.",
        "emojiPath": "assets/appreciation-emojis/lifeline.svg",
        "badgePath": "assets/appreciation-badges/lifeline.png",
        "displayOrder": 11,
        "badgePath": "assets/appreciation-badges/lifeline.png",
    },
    {
        "name": "Office Heartbeat",
        "description": "The person who keeps the energy, culture, and community alive in the workplace.",
        "emojiPath": "assets/appreciation-emojis/office_heartbeat.svg",
        "badgePath": "assets/appreciation-badges/office_heartbeat.png",
        "displayOrder": 12,
        "badgePath": "assets/appreciation-badges/office_heartbeat.png",
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
                    "badgePath": appreciation_type["badgePath"],
                    "displayOrder": appreciation_type["displayOrder"],
                    "isActive": True,
                },
                "update": {
                    "description": appreciation_type["description"],
                    "emojiPath": appreciation_type["emojiPath"],
                    "badgePath": appreciation_type["badgePath"],
                    "displayOrder": appreciation_type["displayOrder"],
                },
            },
        )
        print(f"  ✓ {appreciation_type['name']}")

    print("Seeding complete.")
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(seed())