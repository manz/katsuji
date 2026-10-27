"""Build-time version source for hatchling.

Reads the `VERSION` env var when set (the release pipeline injects the tag),
otherwise falls back to a dev placeholder so local builds work without it.
"""

import os

DEV_VERSION = "0.0.0.dev0"


def get_version() -> str:
    """The tag without its `v`: `v0.5.0a2` is version 0.5.0a2."""
    return os.environ.get("VERSION", "").removeprefix("v") or DEV_VERSION
