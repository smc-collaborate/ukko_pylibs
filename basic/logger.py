import errno
import sys
import traceback
from typing import Any, Callable, TextIO
import os


################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.class_HandledException import HandledException
from ukko_pylibs.basic.simpleUtils import Utils as Utils

#
################################################################################


def UniLen_approx(s: str) -> int:
    # A simple approximation of the display width of a string, treating wide characters as 2 and narrow as 1
    # This is not perfect but should work reasonably well for most cases
    width = 0
    for ch in s:
        if ch in ["🔒", "❌", "✅", "⚠️", "ℹ️", "❓", "⭐"]:
            width += 2
        else:
            width += 1
    return width


class SimpleLogger:

    VERBOSITY_ERRORS_ONLY = 0
    VERBOSITY_WARNINGS = 1
    VERBOSITY_INFO = 2
    VERBOSITY_INFO_DETAILED = 3

    VERBOSITY_ALL = 4

    def __init__(
        self, name: str, onVerbosityThresholdChange: Callable[[int], None] | None = None
    ):
        self.name = name
        self.lastErrorMsg: str | None = None
        self.onVerbosityThresholdChange = onVerbosityThresholdChange
        self.detailCount = 0
        self.infoCount = 0
        self.warningCount = 0
        self.errorCount = 0
        self.printThreshold = -1  # < To trigger a 'change event'
        self.setVerbosity(self.VERBOSITY_INFO)

    def amPrinting(self, level: int):
        return level >= self.printThreshold

    amPrintingInfo = lambda self: self.amPrinting(self.VERBOSITY_INFO)
    amPrintingDetailed = lambda self: self.amPrinting(self.VERBOSITY_INFO_DETAILED)
    amPrintingAll = lambda self: self.amPrinting(self.VERBOSITY_ALL)

    def setVerbosity(self, setValue: bool | int) -> int:
        oldThreshold = self.printThreshold
        if isinstance(setValue, bool):
            self.printThreshold = (
                self.VERBOSITY_ALL if setValue else self.VERBOSITY_INFO
            )
        else:
            self.printThreshold = setValue

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
        return self.printThreshold >= self.VERBOSITY_INFO_DETAILED

    def print_infoOrVerbose(self, message: Any | None, isInfo: bool = True):
        if message is None:
            return
        if isInfo:
            self.print_info(message)
        else:
            self.print_verbose(message)

    def print_info(self, message: Any | None):
        if message is None:
            return
        self.infoCount += 1
        self._prefix_print(message, icon="ℹ️")

    def print_warning(self, message: Any | None):
        if message is None:
            return
        self.warningCount += 1
        self._prefix_print(message, icon="⚠️")

    def print_verbose(self, message: Any | None):
        if message is None:
            return
        self.detailCount += 1
        if self.isVerbose():
            self._prefix_print("Verbose|" + message, icon="Ⓜ️")

    @staticmethod
    def asPrintable(message: Any | None) -> str:
        if message is None:
            return ""
        if isinstance(message, list) or isinstance(message, tuple):
            return "\n".join([SimpleLogger.asPrintable(m) for m in message])
        return str(message)

    def _prefix_print(
        self,
        msg: Any | None,
        icon: str = "ℹ️",
        noPrefix: bool = False,
        dest: TextIO | None = None,
    ):
        msg_text = self.asPrintable(msg)
        if msg_text == "":
            return

        if dest is None:
            textOut = sys.stderr
        else:
            textOut = dest

        lines = msg_text.split("\n")
        topLine = lines.pop(0).strip().removeprefix(icon).strip()

        prefix = icon
        bar = " "
        if not noPrefix and self.name != "":
            if prefix != "":
                prefix += "  "
            prefix += f"{self.name}"
            bar = " | "

        textOut.write(f"{prefix}{bar}{topLine}\n")
        padding = " " * UniLen_approx(prefix)
        for line in lines:
            textOut.write(f"{padding}{bar}{line}\n")

    def print_error(
        self,
        msg: str,
        isFatal: bool = False,
        noPrefix: bool = False,
        dest: TextIO | None = None,
    ):
        """Print an error message to stderr with a prefix.  Avoids printing the same message multiple times.
        :param msg: The error message to print
        :return: The length of the gap for the next line
        """
        if self.lastErrorMsg == msg:
            if isFatal:
                exit(1)
            return 0

        self.errorCount += 1
        self.lastErrorMsg = msg

        msg = msg.strip().removeprefix("❌").strip()
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

        self._prefix_print(msg, ("❌ " + prefix).strip(), noPrefix=noPrefix, dest=dest)

        if isFatal:
            exit(1)

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
            txt += "\n -- Use '--verbose' for more information"

        if isError:
            self.print_error(txt, isFatal=False)
        else:
            self.print_warning(txt)

    def print_error_withException(
        self, e: BaseException, action: str | None = None, alwaysTraceback: bool = False
    ):
        """
        :param e: The exception that occurred
        :param action: Custo error message to display
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
