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
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.class_HandledException import HandledException
from ukko_pylibs.basic.simpleUtils import Utils
from ukko_pylibs.basic.simpleUtils import PrettyText

#
################################################################################


class SimpleLogger:

    VERBOSITY_ERRORS_ONLY = 0
    VERBOSITY_WARNINGS = 1
    VERBOSITY_INFO = 2
    VERBOSITY_INFO_VERBOSE = 3
    VERBOSITY_TEDIOUS_DETAIL = 4
    VERBOSITY_MAX = 4

    def _getLevelIconAndPrefix(self, level: int) -> Tuple[str, str]:
        if level == self.VERBOSITY_ERRORS_ONLY:
            return "❌", "Error"
        elif level == self.VERBOSITY_WARNINGS:
            return "⚠️", "Warning"
        elif level == self.VERBOSITY_INFO:
            return "ℹ️", "Info"
        elif level == self.VERBOSITY_INFO_VERBOSE:
            return "Ⓜ️", "Verbose"
        elif level == self.VERBOSITY_TEDIOUS_DETAIL:
            return "🔍", "Detailed"
        else:
            return "❓", f"[Level {level}]"

    def amPrinting(self, level: int):
        return level <= self.printThreshold

    def doPrintEntry(
        self,
        level: int,
        message: Any | None,
        noPrefix: bool = False,
        dest: TextIO | None = None,
    ) -> bool:

        if message is None or not self.amPrinting(level):
            return False

        iconPrefix, txtPrefix = self._getLevelIconAndPrefix(level)

        self.kindCounts[txtPrefix] = self.kindCounts.get(txtPrefix, 0) + 1

        if noPrefix:
            txtPrefix = ""

        msg_text = self.asPrintable(message)
        if msg_text == "":
            return False

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

        return True

    def __init__(
        self, name: str, onVerbosityThresholdChange: Callable[[int], None] | None = None
    ):
        self.name = name
        self.lastErrorMsg: str | None = None
        self.onVerbosityThresholdChange = onVerbosityThresholdChange
        self.kindCounts = {}
        self.printThreshold = self.VERBOSITY_WARNINGS

        # Ensures we get the detailed logging during parameter review
        for x in sys.argv[1:]:
            if x == "--":
                break
            if x.startswith("--verbosity="):
                self.setVerbosity(x.split("=", 1)[1], silentOnFailure=True)
                break

        # |x|sys.stderr.write(f"⚠️  self.printThreshold ={self.printThreshold}\n")

    def setVerbosity(
        self, setValue: bool | int | str, silentOnFailure: bool = False
    ) -> int:
        oldThreshold = self.printThreshold
        # |x| sys.stderr.write(f"⚠️  setVerbosity({json.dumps(setValue)}): From {oldThreshold}\n")
        if isinstance(setValue, bool):
            self.printThreshold = (
                self.VERBOSITY_INFO_VERBOSE if setValue else self.VERBOSITY_INFO
            )
        elif isinstance(setValue, str):
            if setValue == "quiet":
                self.printThreshold = self.VERBOSITY_WARNINGS
            elif setValue == "info":
                self.printThreshold = self.VERBOSITY_INFO
            elif setValue == "verbose":
                self.printThreshold = self.VERBOSITY_INFO_VERBOSE
            elif setValue == "all":
                self.printThreshold = self.VERBOSITY_TEDIOUS_DETAIL
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
        return self.printThreshold >= self.VERBOSITY_INFO_VERBOSE

    ##########
    #
    def print_infoOrVerbose(self, message: Any | None, isInfo: bool = True):
        self.doPrintEntry(
            self.VERBOSITY_INFO if isInfo else self.VERBOSITY_INFO_VERBOSE, message
        )

    def print_info(self, message: Any | None):
        self.doPrintEntry(self.VERBOSITY_INFO, message)

    def print_warning(self, message: Any | None):
        self.doPrintEntry(self.VERBOSITY_WARNINGS, message)

    def print_verbose(self, message: Any | None):
        self.doPrintEntry(self.VERBOSITY_INFO_VERBOSE, message)

    def print_tediousDetail(self, message: Any | None):
        self.doPrintEntry(self.VERBOSITY_TEDIOUS_DETAIL, message)

    def print_error(
        self,
        message: str,
        isFatal: bool = False,
        noPrefix: bool = False,
        dest: TextIO | None = None,
    ):
        """Print an error message to stderr with a prefix.  Avoids printing the same message multiple times.
        :param message: The error message to print
        :return: The length of the gap for the next line
        """
        if self.lastErrorMsg == message:
            if isFatal:
                exit(1)
            return False

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

        self.doPrintEntry(self.VERBOSITY_ERRORS_ONLY, msg, noPrefix=noPrefix, dest=dest)

        if isFatal:
            exit(1)

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
            txt += "\n -- Use '--verbosity=verbose' for more information"

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
