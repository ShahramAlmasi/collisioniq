"""Legacy widgets - kept for backward compatibility.

Note: CheckListFilterBox has been moved to modern_widgets.py with enhancements.
Use modern_widgets.CheckListFilterBox for new code.
"""
from __future__ import annotations

# Re-export from modern_widgets for backward compatibility
from .modern_widgets import CheckListFilterBox

__all__ = ["CheckListFilterBox"]
