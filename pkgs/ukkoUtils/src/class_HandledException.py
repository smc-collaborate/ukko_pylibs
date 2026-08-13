import sys


import traceback
from typing import Any, Tuple


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
        from appLogging import appLog

        if appLog.isVerbose():
            sys.stderr.write(f"⚠️  CreatedHandledException: {msgText}\n")
        self.srcException = srcException
        super().__init__(msgText)


def _getExceptionParts(e: BaseException) -> Tuple[str, list[str], list[str]]:
    """kind,srcEntries,TraceLines"""

    from ukkoStyling import styling

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

    sourceEntries = []
    if len(summary) >= 3:
        kind = summary[-1]
        _untrimmed = summary[1].rstrip()

        source = _untrimmed.lstrip()
        prefixToStrip = _untrimmed[: (len(_untrimmed) - len(source))]
        sourceEntries = [source]
        for x in summary[2:-1]:
            sourceEntries.append(x.removeprefix(prefixToStrip))
        traceLines.insert(0, styling.asBold(summary[0].strip()))
        traceLines.insert(1, "")
    else:
        kind = str(e)

    return kind, sourceEntries, traceLines[:-3]


def getPrettyExceptionInfo(
    e: BaseException, caption: str = "Unexpected Error "
) -> Tuple[str, list[str]]:
    """summaryText,TraceLines"""

    from ukkoStyling import styling
    import prettyText

    kind, sourceEntries, traceLines = _getExceptionParts(e)
    msg = f"{caption}`{styling.asError(kind)}`"

    if sourceEntries:
        msg += " from `"
        prefix = prettyText.asSpaces(msg)
        msg += styling.asError(sourceEntries.pop(0)) + "`"

        for x in sourceEntries:
            msg += "\n" + prefix + styling.asError(x)

    return msg, traceLines[:-3]


def getExceptionAsDict(
    e: BaseException, includeTraceLines: bool = False
) -> dict[str, Any]:
    kind, sourceEntries, traceLines = _getExceptionParts(e)

    result = {"kind": kind, "source": sourceEntries}

    if includeTraceLines:
        result["trace"] = traceLines
    return result
