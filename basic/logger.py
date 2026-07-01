from enum import Enum
import errno
import json
import sys
import traceback
from typing import Any, Callable, TextIO, Tuple
import os


################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.class_HandledException import HandledException
from ukko_pylibs.basic.simpleUtils import PrettyText

#
################################################################################

msgKinds: dict[int, "MsgKind"] = {}


class MsgKind:
    def __init__(
        self,
        value: int,
        name: str,
        icon: str,
        thresholdName: str,
        isDefaultLevel: bool = False,
    ):
        self.value = value
        self.name = name
        self.icon = icon
        self.thresholdName = thresholdName
        self.isDefaultLevel = isDefaultLevel
        msgKinds[value] = self

    @staticmethod
    def add(
        value: int,
        name: str,
        icon: str,
        thresholdName: str,
        isDefaultLevel: bool = False,
    ) -> "MsgKind":
        if value in msgKinds:
            raise ValueError(f"MsgKind with value {value} already exists")
        return MsgKind(value, name, icon, thresholdName, isDefaultLevel)

    def asDict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "name": self.name,
            "icon": self.icon,
            "thresholdName": self.thresholdName,
            "isDefaultLevel": self.isDefaultLevel,
        }


class SimpleLogger:

    MsgKind_ERROR = 0
    MsgKind_WARNING = 1
    MsgKind_INFO = 2
    MsgKind_DETAIL = 3
    MsgKind_TEDIOUS = 4

    @staticmethod
    def get_thresholds() -> Tuple[list[str], str]:
        defaultThreshold = ""
        thresholdList = list[str]()
        for _k, v in msgKinds.items():
            if v.isDefaultLevel:
                defaultThreshold = v.thresholdName
            if v.thresholdName:
                thresholdList.append(v.thresholdName)

        return thresholdList, defaultThreshold

    def _getLevelIconAndPrefix(self, value: int) -> Tuple[str, str, str]:
        if value in msgKinds:
            return (
                msgKinds[value].icon,
                msgKinds[value].name,
                msgKinds[value].thresholdName,
            )
        else:
            return "❓", f"[Level {value}]", ""

    ###############################
    # Thresholds and Verbosity Levels
    #
    # self.printThreshold.  Only messages with a level <= printThreshold will be printed.
    #

    def amPrinting(self, msgKindLevel: int) -> bool:
        return msgKindLevel <= self.printThreshold

    #
    ############################################################

    def amPrintingVerbose(self) -> bool:
        return self.amPrinting(SimpleLogger.MsgKind_DETAIL)

    def amPrintingDetailed(self) -> bool:
        return self.amPrinting(SimpleLogger.MsgKind_DETAIL)

    def amPrintingTediousDetail(self) -> bool:
        return self.amPrinting(SimpleLogger.MsgKind_TEDIOUS)

    def amPrintingInfo(self) -> bool:
        return self.amPrinting(SimpleLogger.MsgKind_INFO)

    def amPrintingError(self) -> bool:
        return self.amPrinting(SimpleLogger.MsgKind_ERROR)

    def print_progress(self, message: str | None = None) -> bool:
        if self.amPrintingVerbose():
            if message is None:
                sys.stderr.write("\n")
            else:
                sys.stderr.write(f"\rℹ️  {message}")
                # Deliberately do not print a newline here to allow overwriting the line with progress updates.
                # The caller should 'print_progress()' when complete.
                # Also - do not log these to the app log as they are transient and would not make sense in the log history.
            return True
        else:
            return False

    def doPrintEntry(
        self,
        level: int,
        message: Any | None,
        noPrefix: bool = False,
        dest: TextIO | None = None,
    ) -> None | str:
        """
        :return: None (if not printed) or the prefix to use on the next line if continuing this message
        """
        if message is None or not self.amPrinting(level):
            return None

        iconPrefix, txtPrefix, _ = self._getLevelIconAndPrefix(level)

        self.kindCounts[txtPrefix] = self.kindCounts.get(txtPrefix, 0) + 1

        if noPrefix:
            txtPrefix = ""

        msg_text = self.asPrintable(message)
        if msg_text == "":
            return None

        if dest is None:
            textOut = sys.stderr
        else:
            textOut = dest

        lines = msg_text.split("\n")
        topLine = lines.pop(0).strip().removeprefix(iconPrefix).strip()

        prefix = iconPrefix
        if iconPrefix != "" and txtPrefix != "":
            prefix += "  "
        prefix += txtPrefix
        bar = " "
        if not noPrefix and self.name != "":
            if prefix != "":
                prefix += "  "
            prefix += f"{self.name}"
            bar = " | "

        textOut.write(f"{prefix}{bar}{topLine}\n")
        padding = " " * PrettyText.UniLen_approx(prefix)
        for line in lines:
            textOut.write(f"{padding}{bar}{line}\n")

        return padding + bar

    def __init__(
        self, name: str, onVerbosityThresholdChange: Callable[[int], None] | None = None
    ):
        self.name = name
        self.lastErrorMsg: str | None = None
        self.onVerbosityThresholdChange = onVerbosityThresholdChange
        self.kindCounts = {}
        self.printThreshold = self.MsgKind_WARNING

        # |x|sys.stderr.write(f"⚠️  self.printThreshold ={self.printThreshold}\n")

    def setVerbosity(
        self, setValue: None | bool | int | str, silentOnFailure: bool = False
    ) -> int:
        if setValue is not None:
            oldThreshold = self.printThreshold
            # |x| sys.stderr.write(f"⚠️  setVerbosity({json.dumps(setValue)}): From {oldThreshold}\n")
            if isinstance(setValue, bool):
                self.printThreshold = (
                    self.MsgKind_DETAIL if setValue else self.MsgKind_INFO
                )
            elif isinstance(setValue, str):
                if setValue == "quiet":
                    self.printThreshold = self.MsgKind_WARNING
                elif setValue == "info":
                    self.printThreshold = self.MsgKind_INFO
                elif setValue == "details":
                    self.printThreshold = self.MsgKind_DETAIL
                elif setValue == "all":
                    self.printThreshold = self.MsgKind_TEDIOUS
                elif not silentOnFailure:
                    sys.stderr.write(
                        f"⚠️  setVerbosity({json.dumps(setValue)}): Invalid value\n"
                    )
            if (
                oldThreshold != self.printThreshold
                and self.onVerbosityThresholdChange is not None
            ):
                try:
                    self.onVerbosityThresholdChange(self.printThreshold)
                except Exception:
                    pass  # < Swallow any exceptions from the callback to avoid interfering with the main app
        return self.printThreshold

    def isVerbose(self):
        return self.printThreshold >= self.MsgKind_DETAIL

    ##########
    #
    def print_infoOrVerbose(self, message: Any | None, isInfo: bool = True):
        self.doPrintEntry(self.MsgKind_INFO if isInfo else self.MsgKind_DETAIL, message)

    def print_info(self, message: Any | None) -> None | str:
        return self.doPrintEntry(self.MsgKind_INFO, message)

    def print_warning(self, message: Any | None) -> None | str:
        return self.doPrintEntry(self.MsgKind_WARNING, message)

    def print_verbose(self, message: Any | None) -> None | str:
        return self.doPrintEntry(self.MsgKind_DETAIL, message)

    def print_tediousDetail(self, message: Any | None) -> None | str:
        return self.doPrintEntry(self.MsgKind_TEDIOUS, message)

    def print_error(
        self,
        message: str,
        isFatal: bool = False,
        noPrefix: bool = False,
        dest: TextIO | None = None,
    ) -> None | str:
        """Print an error message to stderr with a prefix.  Avoids printing the same message multiple times.
        :param message: The error message to print
        :return: None (if not printed) or the prefix to use on the next line if continuing this message
        """
        if self.lastErrorMsg == message:
            if isFatal:
                exit(1)
            return None

        self.lastErrorMsg = message
        msg = message.strip().removeprefix("❌").strip()
        prefix = "Error: "
        if msg.startswith("["):
            endPos = msg.find(":")
            if endPos > 0:
                prefix = msg[0:endPos]
                if not ("error" in prefix.lower()):
                    prefix += ".Error"
                prefix += ": "
                msg = msg[endPos + 1 :].strip()
            else:
                prefix = "Error: "
        elif msg.startswith("Error:"):
            prefix = "Error: "
            msg = msg.removeprefix("Error:").strip()
        elif msg.startswith("Error"):
            prefix = ""

        printPrefixToUseOrNone = self.doPrintEntry(
            self.MsgKind_ERROR, msg, noPrefix=noPrefix, dest=dest
        )

        if isFatal:
            exit(1)

        return printPrefixToUseOrNone

    @staticmethod
    def asPrintable(message: Any | None) -> str:
        if message is None:
            return ""
        if isinstance(message, list) or isinstance(message, tuple):
            return "\n".join([SimpleLogger.asPrintable(m) for m in message])
        return str(message)

    def _print_exception_(
        self,
        isError: bool,
        e: BaseException,
        action: str | None = None,
        alwaysTraceback: bool = False,
    ):

        if isinstance(e, IOError) and (e.errno == errno.EPIPE):
            if action is not None:
                txt = f"{action} -"
            else:
                txt = ""
            txt += "Piping output - Halted"
            emsgSuffix = ""
        elif not isinstance(e, HandledException):
            emsgSuffix = f"Unhandled[{e}]"
        else:
            emsgSuffix = f" {e}"

        txt = "" if action is None else str(action)
        if (txt != "") and (emsgSuffix != ""):
            txt += " -- "
        txt += emsgSuffix

        if alwaysTraceback or self.isVerbose():
            txt += "\nTraceback:\n" + traceback.format_exc()
        else:
            txt += "\n -- Use '--verbosity=details' for more information"

        if isError:
            self.print_error(txt, isFatal=False)
        else:
            self.print_warning(txt)

    def print_error_withException(
        self, e: BaseException, action: str | None = None, alwaysTraceback: bool = False
    ):
        """
        :param e: The exception that occurred
        :param action: Custom error message to display
        """
        self._print_exception_(True, e, action, alwaysTraceback)

    def print_warning_withException(
        self, e: BaseException, action: str | None = None, alwaysTraceback: bool = False
    ):
        """
        :param e: The exception that occurred
        :param action: Custo error message to display
        """
        self._print_exception_(False, e, action, alwaysTraceback)

    def had_error(self) -> bool:
        return self.lastErrorMsg is not None


MsgKind.add(SimpleLogger.MsgKind_ERROR, "Error", "❌", "quiet", isDefaultLevel=True)
MsgKind.add(SimpleLogger.MsgKind_WARNING, "Warning", "⚠️", "")
MsgKind.add(SimpleLogger.MsgKind_INFO, "Info", "ℹ️", "info")
MsgKind.add(SimpleLogger.MsgKind_DETAIL, "Detail", "Ⓜ️", "details")
MsgKind.add(SimpleLogger.MsgKind_TEDIOUS, "Tedious", "🔍", "all")
