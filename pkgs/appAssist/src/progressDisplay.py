import time

from appLogging import appLog
from ukkoUtils import ProgressMsg

##################################################
#


class ProgressDisplay:
    def __init__(self, thumbnails):
        self.thumbnails = thumbnails
        self.pos = 0
        self.last_show_time: float | None = None

        self.lastPrintedMsgs: str = ""

    def printUpdate(self, msgs: list[ProgressMsg], refreshRate_seconds=2):
        now_seconds = time.monotonic()

        if self.last_show_time is None:
            self.last_show_time = now_seconds
            return

        newMsgs = "\n".join([x.msg for x in msgs])

        if (newMsgs == self.lastPrintedMsgs) and (
            (now_seconds - self.last_show_time) < refreshRate_seconds
        ):
            return

        self.lastPrintedMsgs = newMsgs
        self.last_show_time = now_seconds

        self.pos += 1
        if (self.pos >= len(self.thumbnails)) or (self.pos < 0):
            self.pos = 0

        appLog.print_progress(
            "  "
            + self.thumbnails[self.pos]
            + "  "
            + (" | ".join([x.asText() for x in msgs]))
        )


_progressDisplay = ProgressDisplay("◐◓◑◒")


def doUpdate(msgs: list[ProgressMsg], refreshRate_seconds=2):
    _progressDisplay.printUpdate(msgs, refreshRate_seconds)
