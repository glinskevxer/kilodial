"""The terminal's view of the layout helpers, which live with the reports.

Every command imports its table and pairs from here, and this module is now a
door onto ``kilodial.report.layout``. The functions moved because the report
document renders through the same code and a report is not a command; keeping
them under the command line meant the report layer imported upward.

The door is kept rather than updating fifteen import lines, and it is kept
deliberately thin: anything added here rather than in the layout module would be
a second place to look.
"""

from __future__ import annotations

from kilodial.report.layout import GAP, or_dash, pairs, table, yes_no

__all__ = ["GAP", "or_dash", "pairs", "table", "yes_no"]
