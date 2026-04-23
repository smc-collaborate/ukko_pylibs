import errno
import sys
import traceback
from typing import Any, TextIO
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
    def __init__(self, name: str):
        self.name = name
        self.isVerbose_ = False
        self.lastErrorMsg: str | None = None

    def isVerbose(self, setValue: bool | None = None):
        if setValue is not None:
            self.isVerbose_ = setValue
        return self.isVerbose_

    def print_info(self, message: Any | None):
        self._prefix_print(message, icon="ℹ️")

    def print_warning(self, message: Any | None):
        self._prefix_print(message, icon="⚠️")

    def print_verbose(self, message: Any | None):
        if self.isVerbose():
            self._prefix_print(message, icon="Ⓜ️")  # ▶️")

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
