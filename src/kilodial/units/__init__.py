"""Quantities the shop measures in, and the arithmetic that goes with them.

Nothing in here knows about storage or about the shop's rules. The types exist
so that a registration percentage and a tolerance band cannot be added together
by accident, and so that every number that ends up on a customer's bill has
gone through one rounding policy instead of whichever one the caller felt like.
"""

from __future__ import annotations

from kilodial.units.money import Money
from kilodial.units.registration import Registration

__all__ = ["Money", "Registration"]
