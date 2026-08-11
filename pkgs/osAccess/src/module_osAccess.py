import subprocess
import threading
from typing import Any


class ThreadedCommandRunner:
    """Runs as a daemon so will automatically be killed on exit"""

    def __init__(self, runThis: list[str], timeoutSeconds: float | None = 20):
        self.runThis = runThis
        self.timeoutSeconds = timeoutSeconds
        self.results: dict[str, Any] = {
            "runThis": runThis,
            "timeout_secs": timeoutSeconds,
        }
        self.thread = None

    def doRunCmd(self):
        print(f"doRunCmd: {self.runThis}")

        # runThis=["rclone","copy",link,destPath,"--no-traverse"]

        ##########################
        #
        # Load runResults
        #
        results: dict[str, Any] = {
            "runThis": self.runThis,
            "timeout_secs": self.timeoutSeconds,
        }

        try:
            runOutputs: subprocess.CompletedProcess[bytes] = subprocess.run(
                self.runThis,
                capture_output=True,
                timeout=self.timeoutSeconds,
            )
            results["return_code"] = runOutputs.returncode
            results["stdout"] = runOutputs.stdout
            results["stderr"] = runOutputs.stdout

        except subprocess.CalledProcessError as ex:
            results["return_code"] = ex.returncode
            results["stdout"] = ex.stdout
            results["stderr"] = ex.stdout
            results["exception"] = f"CalledProcessError({ex})"

        except subprocess.TimeoutExpired as ex:
            results["exception"] = f"TimeoutExpired ({ex.timeout} seconds)"
            results["stdout"] = ex.stdout
            results["stderr"] = ex.stdout
        except FileNotFoundError:
            results["exception"] = f"commandNotFound"
        except Exception as ex:
            results["exception"] = f"Unexpected exception: {ex}"

        print(results)
        self.results = results

    def doStart(self):
        self.thread = threading.Thread(target=self.doRunCmd, daemon=True)
        self.thread.start()

    def isComplete(self):
        return self.thread is not None and not self.thread.is_alive()

    def isRunning(self):
        return self.thread is not None and self.thread.is_alive()
