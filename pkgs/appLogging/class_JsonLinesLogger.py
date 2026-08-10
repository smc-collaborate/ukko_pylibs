import time

import sys
from typing import Any, Tuple
import os
from pathlib import Path


class JsonLinesLogger:

    def __init__(self, fname: str, name: str | None = None):

        if fname.startswith("~"):
            fname = str(Path.home()) + os.sep + fname.removeprefix("~").lstrip(os.sep)

        fname = fname.replace(
            "[LOCAL_WHEN]", time.strftime("%Y-%m-%d_%H-%M-%S_LOCAL", time.localtime())
        )
        self.fname = fname
        self.name = name
        self.lineCount = 0

        self.keyCounts: dict[Any, int] = {}
        Path(self.fname).parent.mkdir(parents=True, exist_ok=True)

    def add(
        self, categoriesWithInfo: dict[str, Any], fullEntry: Any, caption: str
    ) -> Tuple[bool, str]:
        """Add a message to the log file in JSON Lines format. If the log file is not specified, print the message to stdout.
        Returns (bool:'The message was printed to stdout', text:log Reference or ''"""

        if isinstance(categoriesWithInfo, dict):
            for _key in categoriesWithInfo.keys():
                self.keyCounts[_key] = self.keyCounts.get(_key, 0) + 1
        self.lineCount += 1

        from .app_logger import timeFromStart_ms
        from ukkoUtils import pathAsDisplay, asJsonStr

        objOut = {}

        objOut["categories"] = categoriesWithInfo
        if self.name:
            objOut["name"] = self.name
        objOut["timestamp"] = time.time()
        objOut["fromStart_msᵀ"] = timeFromStart_ms()[0]

        objOut["entry"] = fullEntry
        objOut["caption"] = caption

        if self.fname is None:

            print(asJsonStr(objOut, indent=2))
            return True, ""

        else:
            """Add a message to the log file in JSON Lines format."""
            try:
                with open(self.fname, "a", encoding="utf-8") as f:
                    f.write(asJsonStr(objOut) + "\n")
            except Exception as e:
                print(f"Failed to write to log file {self.fname}: {e}", file=sys.stderr)
                return False, ""
            return False, f"{pathAsDisplay(self.fname)}#{self.lineCount:<4}"
