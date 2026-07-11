"""Shared slowapi Limiter instance.

Kept in its own module (rather than defined in `app.api.main`) so route
modules can import it without creating a circular import with `main.py`
(which in turn imports the routers).
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
