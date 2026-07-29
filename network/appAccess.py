import os, sys
from pathlib import Path

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{Path(__file__).parent}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

#
################################################################################


def isRunning() -> bool:
    """Returns True if the application is running, False if it is stopping."""
    import ukko_pylibs.appAssist.appSupport as app  # <-- Import here to avoid circular import issues

    return app.isRunning()


def doHalt(reason: str):
    """Halts the application with a reason."""
    import ukko_pylibs.appAssist.appSupport as app  # <-- Import here to avoid circular import issues

    app.doHalt(reason)
