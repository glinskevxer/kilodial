"""Records the shop keeps, with no idea how they are stored.

Everything here is frozen. A record that can be mutated in place is a record
that gets edited by whichever caller happened to hold it, and the shop's whole
argument for its numbers is that the paperwork did not change after the fact.
"""

from __future__ import annotations
