# db/__init__.py
from .client import db

__all__ = ["db"]

# The __init__.py re-exports db so you have two clean ways to import it anywhere in your codebase — both are valid, use whichever feels cleaner:
# python# Option 1 — explicit, recommended
# from db.client import db

# # Option 2 — shorthand via __init__.py
# from db import db