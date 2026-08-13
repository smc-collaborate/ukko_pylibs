import subprocess
import threading
import time
from typing import Any, Tuple
from ukkoUtils import asJsonStr, ProgressMsg, asUtf8orBytesOrNone


class IAsyncAction_Interface:

    def asProgressMarker(self) -> ProgressMsg:
        return ProgressMsg(self.caption, self.getTimeLeft_seconds())

    def __init__(
        self, caption: str, request: dict[str, Any], timeoutSeconds: float | None = 20
    ):
        self.caption = caption
        self.timeoutSeconds = timeoutSeconds
        self.completionAcknowledged = False
        self.request = request
        self.runResults: Any | None = None
        self.owner: Any | None = None
        self.startTime = time.monotonic()

    def getTimeLeft_seconds(self) -> float | None:
        if self.isComplete() or self.timeoutSeconds is None:
            return None
        else:
            return (self.startTime + self.timeoutSeconds) - time.monotonic()

    def acknowledgeCompletion(self) -> bool:
        if not self.isComplete():
            return False
        if self.completionAcknowledged:
            return False
        self.completionAcknowledged = True
        return True

    def getFullResults(self, runResultsToInclude: Any | None = None) -> dict[str, Any]:
        result = {
            "caption": self.caption,
            "timeout_secs": self.timeoutSeconds,
            "request": self.request,
            "runResults": (
                runResultsToInclude
                if (runResultsToInclude is not None)
                else self.runResults
            ),
        }
        result.update(self.getInfo())
        return result

    def getNewResult(self) -> None | dict[str, Any]:
        if not self.acknowledgeCompletion():
            return None
        return self.getFullResults()

    def _setRunResults(self, runResults: Any | None):
        self.runResults = runResults

    ###########################################################
    # Override these + __init__() : Start the process
    #
    def getInfo(self) -> dict[str, Any]:
        return {}

    def isComplete(self) -> bool:
        return False


def bytesToReadable(src: bytes | None) -> list[str] | str | bytes | None:

    result = asUtf8orBytesOrNone(src)
    if isinstance(result, str):
        lines = result.splitlines()
        if len(lines) > 1:
            result = lines
    return result


def setElementIfNonNull(obj: dict[str, Any], key: str, value: Any | None):
    if value is not None:
        obj[key] = value


def setElement_asReadableBytes(obj: dict[str, Any], key: str, src: bytes | None):
    setElementIfNonNull(obj, key, bytesToReadable(src))


class ThreadedCommandRunner(IAsyncAction_Interface):
    """Runs as a daemon so will automatically be killed on exit"""

    def __init__(
        self,
        caption: str,
        runThis: list[str],
        timeoutSeconds: float | None = 20,
        additional: Any | None = None,
        expectedReturnCode: int | None = 0,
        expectedStdErrOut: str | None = None,
    ):

        request: dict[str, Any] = {"runThis": runThis}
        if additional is not None:
            request["additional"] = additional

        super().__init__(caption, request, timeoutSeconds)
        self.expectedReturnCode: int | None = expectedReturnCode
        self.expectedStdErrOut: str | None = expectedStdErrOut
        self.thread = threading.Thread(
            target=self._doRunCmd, args=[runThis], daemon=True
        )
        self.thread.start()

    def isComplete(self):
        return not self.thread.is_alive()

    def _doRunCmd(self, runThis: list[str]):

        print(f"doRunCmd: {runThis}")

        # runThis=["rclone","copy",link,destPath,"--no-traverse"]

        ##########################
        #
        # Load runResults
        #
        runResults: dict[str, Any] = {}

        try:
            runOutputs: subprocess.CompletedProcess[bytes] = subprocess.run(
                runThis,
                capture_output=True,
                timeout=self.timeoutSeconds,
            )
            runResults["return_code"] = runOutputs.returncode
            setElement_asReadableBytes(runResults, "stdout", runOutputs.stdout)
            setElement_asReadableBytes(runResults, "stderr", runOutputs.stderr)

        except subprocess.CalledProcessError as ex:
            runResults["return_code"] = ex.returncode
            setElement_asReadableBytes(runResults, "stdout", ex.stdout)
            setElement_asReadableBytes(runResults, "stderr", ex.stderr)
            runResults["exception"] = f"CalledProcessError({ex})"

        except subprocess.TimeoutExpired as ex:
            runResults["exception"] = f"TimeoutExpired ({ex.timeout} seconds)"
            setElement_asReadableBytes(runResults, "stdout", ex.stdout)
            setElement_asReadableBytes(runResults, "stderr", ex.stderr)
        except FileNotFoundError:
            runResults["exception"] = "CommandNotFound" + (
                "" if len(runThis) == 0 else f"[{runThis[0]}]"
            )
        except Exception as ex:
            runResults["exception"] = f"Unexpected exception: {ex}"

        errMsg = runResults.get("exception")
        if (
            errMsg is None
            and self.expectedReturnCode is not None
            and (runResults["return_code"] != self.expectedReturnCode)
        ):
            errMsg = f"Returned {runResults["return_code"]}"

        if self.expectedStdErrOut is not None:
            _stderr = runResults.get("stderr")
            if _stderr is not None:
                if str(_stderr) != self.expectedStdErrOut:
                    errMsg = f"Gave stderr: {asJsonStr(_stderr)}"

        if errMsg is not None:
            runResults["errMsg"] = errMsg

        self._setRunResults(self.onCompletion(runResults))

    ###########################################################
    # Override these + __init__() : Start the process
    #
    def getInfo(self) -> dict[str, Any]:
        info: dict[str, Any] = {"kind": "ThreadedCommandRunner"}
        if self.expectedReturnCode is not None:
            info["expectedReturnCode"] = self.expectedReturnCode
        if self.expectedStdErrOut is not None:
            info["expectedStdErrOut"] = self.expectedStdErrOut

        return info

    def onCompletion(self, initialRunResults: dict[str, Any]) -> dict[str, Any]:
        print(initialRunResults)
        return initialRunResults


class AsyncActionList:
    def __init__(self):
        self.entries: list[IAsyncAction_Interface] = []

    def appendNew(self, runner: IAsyncAction_Interface):
        runner.owner = self
        self.entries.append(runner)

    def doReview(
        self,
    ) -> Tuple[list[IAsyncAction_Interface], list[IAsyncAction_Interface]]:
        """Returns incompleteList, freshlyCompleted List"""
        freshlyCompleted: list[IAsyncAction_Interface] = []
        incomplete: list[IAsyncAction_Interface] = []

        for x in self.entries:
            if not x.isComplete():
                incomplete.append(x)
            elif x.acknowledgeCompletion():
                freshlyCompleted.append(x)

        return incomplete, freshlyCompleted
