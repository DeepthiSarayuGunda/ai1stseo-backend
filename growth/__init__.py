"""
growth/ — Isolated growth plan modules for ai1stseo.com.
This package contains features for the 5-month growth plan.
No shared core logic is modified — all new code lives here.
"""

try:
    from growth.growth_api import growth_bp
except Exception as e:
    import logging
    logging.getLogger(__name__).error("Failed to import growth_bp: %s", e)
    # Re-raise so app.py's try/except can catch it cleanly
    raise

__all__ = ["growth_bp"]
