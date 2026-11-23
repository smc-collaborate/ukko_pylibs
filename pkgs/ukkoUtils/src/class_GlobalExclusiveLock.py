import filelock
import tempfile
import os
import re


class GlobalExclusiveLock:
    def __init__(self, id: str | None, prefixKind=""):
        if id is None:
            self.fileLock = None
        else:

            _replacement = "_"

            sanitisedId = (
                re.sub(
                    r'[<>:"/\\|?*\x00-\x1f\s]+', _replacement, id.removeprefix("/dev/")
                ).strip(f". {_replacement}")
                or "unamed"
            )

            self.fileLock = filelock.FileLock(
                tempfile.gettempdir() + os.sep + prefixKind + sanitisedId + ".lock",
                timeout=5,
            )

    @property
    def isEnabled(self):
        return self.fileLock is not None

    def __enter__(self):
        # Setup: acquire and return the resource
        if self.fileLock:
            self.fileLock.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Teardown: release the resource
        if self.fileLock:
            return self.fileLock.__exit__(exc_type, exc_val, exc_tb)
        else:
            return False

    Timeout = filelock.Timeout
