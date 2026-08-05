import time
import json
import sys
from typing import Any
import os
from pathlib import Path

from .app_logger import timeFromStart_ms


class JsonLinesLogger:

    def __init__(self, fname: str, name: str | None = None):

        if fname.startswith("~"):
            fname = str(Path.home()) + os.sep + fname.removeprefix("~").lstrip(os.sep)

        fname = fname.replace(
            "[LOCAL_WHEN]", time.strftime("%Y-%m-%d_%H-%M-%S_LOCAL", time.localtime())
        )
        self.fname = fname
        self.name = name
        Path(self.fname).parent.mkdir(parents=True, exist_ok=True)

    def add(self, message: Any) -> bool:
        """Add a message to the log file in JSON Lines format. If the log file is not specified, print the message to stdout.
        Returns True if the message was printed to stdout"""
        from ukkoUtils.module_utils import asJsonStr

        if self.fname is None:

            print(asJsonStr(message, indent=2))
            return True
        else:
            """Add a message to the log file in JSON Lines format."""
            try:
                objOut = {}

                if self.name:
                    objOut["name"] = self.name
                objOut["timestamp"] = time.time()
                objOut["fromStart_msᵀ"] = timeFromStart_ms()[0]

                objOut["message"] = message

                with open(self.fname, "a", encoding="utf-8") as f:
                    f.write(asJsonStr(objOut) + "\n")
            except Exception as e:
                print(f"Failed to write to log file {self.fname}: {e}", file=sys.stderr)
            return False
