"""Mirror stdout/stderr to timestamped log files.

Note: instantiating Tee rebinds sys.stdout/sys.stderr process-wide -
see KNOWN-ISSUES.md at the repository root.
"""

from .tee import Tee

__all__ = ["Tee"]
