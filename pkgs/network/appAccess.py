import os, sys
from pathlib import Path

################################################################################
#
# Ensure shared Packages are available
#

packages_dir = str((Path(__file__).parent.parent / "pkgs").absolute())
if not packages_dir.endswith("/pkgs") or not os.path.exists(packages_dir):
    exit(f"❌  {__file__}\n    Misconfigured: [/path/to]/pkgs is not {packages_dir}")

if packages_dir not in sys.path:
    sys.path.append(packages_dir)
#
################################################################################


def isRunning() -> bool:
    """Returns True if the application is running, False if it is stopping."""
    from appAssist import app  # <-- Import here to avoid circular import issues

    return app.isRunning()


def doHalt(reason: str):
    """Halts the application with a reason."""
    from appAssist import app  # <-- Import here to avoid circular import issues

    app.doHalt(reason)
