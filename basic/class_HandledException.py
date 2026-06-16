import sys

################################################################################
#
# Shared Libraries
#
import os

shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

#
################################################################################


class HandledException(Exception):
    """An exception that is expected to occur in normal operation - simply look at 'msg'"""

    def __init__(self, msg: str | list, srcException: Exception | None = None):
        if msg is str:
            msgText = msg
        elif isinstance(msg, list):
            msgText = "\n".join([str(m) for m in msg])
        else:
            msgText = str(msg)

        from ukko_pylibs.app.appSupport import appLog

        self.origMsg = msgText

        if (srcException is not None) and (str(srcException) != ""):
            msgText += f"\nCaused by: {str(srcException)}"
        self.msg = msgText
        if appLog.isVerbose():
            sys.stderr.write(f"⚠️  CreatedHandledException: {msgText}\n")
        self.srcException = srcException
        super().__init__(msgText)
