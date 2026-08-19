"""Run a CLI process and react to its output.

Child-process cleanup needs psutil, which is an optional extra:
``pip install pyutils-fw[process]``.
"""

from .run_process import RunProcess

__all__ = ["RunProcess"]
