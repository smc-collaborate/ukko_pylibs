from copy import deepcopy

import time

from typing import Any, Tuple
import os
from pathlib import Path

from ukkoUtils import ThreadSafe


from .app_logger import appLog


class JLogReference:
    def __init__(self, fname: str, lineNum: int, caption: str):
        self.ref_withPadding = f"{fname}#{lineNum:<4}"
        self.ref_plain = self.ref_withPadding.strip()

        self.caption = caption
        self.ownerForPrinting: str | None = None

    def asStyled(self) -> str:
        try:
            from ukkoStyling import styling

            return styling.asLink(
                self.ref_withPadding, styleLeadingAndTrailingWhitespace=False
            )
        except:
            pass
        return self.ref_withPadding

    @property
    def plainText(self) -> str:
        return self.ref_plain

    def asDecoratedWithCaption(self) -> str:
        return self.asStyled() + " : " + self.caption

    def noteOwnerForPrinting(self, printingOwner: Any):
        self.ownerForPrinting = printingOwner

    def printOnce(self):
        if self.ownerForPrinting is None:
            appLog.print_always(self.asDecoratedWithCaption())
            self.ownerForPrinting = "_printOnce()"
        # |x| else:
        # |x|     appLog.print_always(self.asDecoratedWithCaption()+" -- "+self.ownerForPrinting)

    @staticmethod
    def create_Empty() -> "JLogReference":
        return JLogReference("", 0, "")


class JsonLinesLogger:

    def __init__(self, fname: str, name: str | None = None):
        self.protected = ThreadSafe[JsonLinesLogger._ProtectedPart](
            JsonLinesLogger._ProtectedPart(fname, name)
        )

    @property
    def path(self) -> Path:
        with self.protected as protected:
            return protected.path

    def printNewEntries(self):
        with self.protected as protected:
            return protected.printNewEntries()

    def getOverview(self, withCount: bool = True) -> Tuple[str, dict[Any, int]]:
        """Returns: Styled text description & key counts"""
        with self.protected as protected:
            return protected.getOverview(withCount)

    def add(
        self,
        categoriesWithInfo: dict[str, Any],
        fullEntry: Any,
        caption: str,
        captionToShow: str | None = None,
    ) -> JLogReference:

        with self.protected as protected:
            return protected.add(categoriesWithInfo, fullEntry, caption, captionToShow)

    class _ProtectedPart:
        def printNewEntries(self):
            for x in self.cachedList:
                x.printOnce()

            self.cachedList = []

        def __init__(self, fname: str, name: str | None = None):
            if fname.startswith("~"):
                fname = (
                    str(Path.home()) + os.sep + fname.removeprefix("~").lstrip(os.sep)
                )

            fname = fname.replace(
                "[LOCAL_WHEN]",
                time.strftime("%Y-%m-%d_%H-%M-%S_LOCAL", time.localtime()),
            )
            self.path = Path(fname).absolute()
            self.name = name
            self.lineCount = 0

            self.keyCounts: dict[Any, int] = {}
            self.path.parent.mkdir(parents=True, exist_ok=True)

            self.isAppendable = False
            self.symLink: Path | None = None
            self.cachedList: list[JLogReference] = []

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

        def getOverview(self, withCount: bool = True) -> Tuple[str, dict[Any, int]]:
            """Returns: Styled text description & key counts"""
            from prettyText import pluralize
            from ukkoStyling import styling

            result = styling.asBoldLink(self.path)
            if withCount:
                result += " " + pluralize(self.lineCount, "entry")

            if self.symLink is not None:
                result += f" (Linked as {styling.asBoldLink(self.symLink)})"

            return result, deepcopy(self.keyCounts)

        def add(
            self,
            categoriesWithInfo: dict[str, Any],
            fullEntry: Any,
            caption: str,
            captionToShow: str | None = None,
        ) -> JLogReference:

            logRef: JLogReference
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

            self.cachedList.append(logRef)
            return logRef
