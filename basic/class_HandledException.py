import sys

################################################################################
#
# Shared Libraries
#
import os
import traceback
from typing import Tuple
from pathlib import Path


shared_dir = os.path.abspath(f"{Path(__file__).parent}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)


#
################################################################################


class HandledException(Exception):
    """An exception that is expected to occur in normal operation - simply look at 'msg'"""

    def __init__(self, msg: str | list, srcException: Exception | None = None):
        if isinstance(msg, str):
            msgText = msg
        elif isinstance(msg, list):
            msgText = "\n".join([str(m) for m in msg])
        else:
            msgText = str(msg)

        self.origMsg = msgText

        if (srcException is not None) and (str(srcException) != ""):
            msgText += (
                "\n" + getPrettyExceptionInfo(srcException, caption="Caused by: ")[0]
            )
        self.msg = msgText
        from ukko_pylibs.basic.logger import appLog

        if appLog.isVerbose():
            sys.stderr.write(f"⚠️  CreatedHandledException: {msgText}\n")
        self.srcException = srcException
        super().__init__(msgText)


def getPrettyExceptionInfo(
    e: BaseException, caption: str = "Unexpected Error "
) -> Tuple[str, list[str]]:
    """summaryText,TraceLines"""

    from ukko_pylibs.basic import styling
    from ukko_pylibs.basic.simpleUtils import PrettyText

    traceLines = (
        "\n".join(traceback.format_exception(type(e), e, e.__traceback__))
    ).split(
        "\n"
    )  # < Some of the lines already have newlines, so we split them into separate lines

    summary = []
    for _line in traceLines:
        line = _line.strip()
        if line.startswith('File "'):
            summary = [line]
        elif line:
            summary.append(_line)

    sourceLeft = []
    if len(summary) >= 3:
        kind = summary[-1]
        _untrimmed = summary[1].rstrip()

        source = _untrimmed.lstrip()
        prefixToStrip = _untrimmed[: (len(_untrimmed) - len(source))]
        for x in summary[2:-1]:
            sourceLeft.append(x.removeprefix(prefixToStrip))
        traceLines.insert(0, styling.asBold(summary[0].strip()))
        traceLines.insert(1, "")
    else:
        kind = str(e)
        source = ""

    msg = f"{caption}`{styling.asError(kind)}`"
    if source:
        msg += " from `"
        prefix = PrettyText.asSpaces(msg)
        msg += styling.asError(source) + "`"

        for x in sourceLeft:
            msg += "\n" + prefix + styling.asError(x)

    return msg, traceLines[:-3]
