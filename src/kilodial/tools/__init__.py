"""Checks the repository runs on itself, in CI and before a commit.

Every module in here is a gate rather than a library: it prints what it found
and exits non zero when something is wrong. They are importable and tested like
anything else, because a gate that has never been seen to fail is not a gate.
"""

from __future__ import annotations

OK = 0
FAILED = 1

__all__ = ["FAILED", "OK"]
