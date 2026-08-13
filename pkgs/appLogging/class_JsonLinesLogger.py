import threading
import time

from typing import Any
import os
from pathlib import Path


from .app_logger import appLog


class JLogReference:
    def __init__(self, fname: str, lineNum: int, caption: str):
        self.ref_withPadding = f"{fname}#{lineNum:<4}"
        self.ref_plain = self.ref_withPadding.strip()

        self.caption = caption
        self.hasBeenPrinted = False

    def asStyled(self) -> str:
        try:
            from ukkoStyling import styling

            return styling.asLink(
                self.ref_withPadding, styleLeadingAndTrailingWhitespace=False
            )
        except:
            pass
        return self.ref_withPadding

    def asPlain(self) -> str:
        return self.ref_plain

    def asDecoratedWithCaption(self) -> str:
        return self.asStyled() + " : " + self.caption

    def noteHasBeenPrinted(self):
        self.hasBeenPrinted = True

    def printOnce(self):
        if not self.hasBeenPrinted:
            appLog.print_always(self.asDecoratedWithCaption())
            self.hasBeenPrinted = True

    def __del__(self):
        self.printOnce()

    @staticmethod
    def create_Empty() -> "JLogReference":
        return JLogReference("", 0, "")


class JsonLinesLogger:

    def __init__(self, fname: str, name: str | None = None):

        if fname.startswith("~"):
            fname = str(Path.home()) + os.sep + fname.removeprefix("~").lstrip(os.sep)

        fname = fname.replace(
            "[LOCAL_WHEN]", time.strftime("%Y-%m-%d_%H-%M-%S_LOCAL", time.localtime())
        )
        self.path = Path(fname).absolute()
        self.name = name
        self.lineCount = 0

        self.keyCounts: dict[Any, int] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.isAppendable = False
        self.symLink: Path | None = None
        try:
            with open(str(self.path), "a", encoding="utf-8") as f:
                f.write("")
            self.isAppendable = True
        except Exception as e:
            appLog.print_error_withException(
                e, f"JsonLinesLogger: Failed to create log file {self.path}"
            )

        if self.isAppendable:
            try:
                _symLink = self.path.parent / "latest"
                if _symLink.exists() or _symLink.is_symlink():
                    _symLink.unlink()

                _symLink.symlink_to(self.path)
                self.symLink = _symLink
            except Exception as e:
                appLog.print_error_withException(
                    e,
                    f"JsonLinesLogger: Failed to create 'latest' link to file {self.path}",
                )

        self.lock = threading.Lock()

    def getOverview(self, withCount: bool = True) -> str:
        from prettyText import pluralize
        from ukkoStyling import styling

        result = styling.asBoldLink(self.path)
        if withCount:
            result += " " + pluralize(self.lineCount, "entry")

        if self.symLink != "":
            result += f" (Linked as {styling.asBoldLink(self.symLink)})"

        return result

    def add(
        self,
        categoriesWithInfo: dict[str, Any],
        fullEntry: Any,
        caption: str,
        captionToShow: str | None = None,
    ) -> JLogReference:

        logRef: JLogReference
        with self.lock:
            """Add a message to the log file in JSON Lines format. If the log file is not specified, print the message to stdout.
            Returns (bool:'The message was printed to stdout', text:log Reference or ''
            """

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

            if self.path is None:

                print(asJsonStr(objOut, indent=2))
                return JLogReference.create_Empty()

            """Add a message to the log file in JSON Lines format."""
            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(asJsonStr(objOut) + "\n")
            except Exception as e:
                appLog.print_error_withException(
                    e, f"JsonLinesLogger: Failed to write to log file {self.path}"
                )
                return JLogReference.create_Empty()

            logRef = JLogReference(
                pathAsDisplay(self.path),
                self.lineCount,
                (caption if captionToShow is None else captionToShow),
            )

        return logRef
