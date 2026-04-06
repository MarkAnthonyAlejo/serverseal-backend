"""Shared Flask extensions — imported by both app.py (init) and routes.py (decorators).

Keeping them here breaks the circular-import that would occur if they lived in app.py.
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# storage_uri="memory://" means counters reset on each restart and are NOT shared
# across Gunicorn workers.  This is acceptable for a simple rate limiter; add a
# Redis URI (RATELIMIT_STORAGE_URL env var) later if you scale beyond one dyno.
limiter = Limiter(
    get_remote_address,
    default_limits=[],          # no blanket global limit — apply per-route only
    storage_uri="memory://",
)
