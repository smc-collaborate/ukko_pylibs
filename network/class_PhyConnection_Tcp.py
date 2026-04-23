import socket
import time
import sys
import os

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import Utils as Utils
from ukko_pylibs.basic.class_HandledException import (
    HandledException as HandledException,
)
from ukko_pylibs.network.class_IPhyConnection import IPhyConnection

#
################################################################################


class PhyConnection_Tcp(IPhyConnection):
    """TcpConnection:
    These need to be implemented:
     * def _getTextName(self) -> str:
     * def _doClose(self) -> None:
     * def _doSetTimeout_seconds(self, timeout_seconds: float):
     * def _getIsConnected(self)->bool:
     * def _doSendAllBytes_orException(self, data: bytes):
     * def _doReadARllBytes(self, length: int, timeout_ms: int | None = None) -> bytes:
     * def _doReadLine(self, timeout_ms: int | None = None) -> str:
    """

    def __init__(self, connection: socket.socket, infoText: str | None):
        super().__init__(infoText)
        self.connection = connection

    def _getTextName(self) -> str:
        return f"TcpLink[{self.infoText if self.infoText else self.connection.getsockname()}]"

    def _doClose(self):
        self.connection.close()

    def _doSetTimeout_seconds(self, timeout_seconds: float):
        self.connection.settimeout(timeout_seconds)

    def _getIsConnected(self) -> bool:
        try:
            # Check if the socket is still connected by sending a zero-byte message
            self.connection.send(b"")
            return True
        except OSError as e:
            return False

    def _doSendAllBytes_orException(self, data: bytes):
        self.connection.sendall(data)

    def _doReadAllBytes(self, length: int, timeout_ms: int | None = 5000) -> bytes:
        """Read a fixed number of bytes from the stream."""
        oldTimeout = self.connection.gettimeout()
        try:
            deadline = None if timeout_ms is None else time.time() + (timeout_ms / 1000)

            readBytes = b""
            while len(readBytes) < length:
                if deadline is not None:
                    now = time.time()
                    if now >= deadline:
                        self.printWarning(
                            "_doReadAllBytes", f"Timeout exceeded after {timeout_ms} ms"
                        )
                        break
                    self.connection.settimeout(
                        deadline - now
                    )  # Adjust the timeout for each iteration

                newBytes = self.connection.recv(length - len(readBytes))
                if (newBytes is None) or (len(newBytes) == 0):
                    self.printWarning(
                        "_doReadAllBytes",
                        f"Stopped after {len(readBytes)}/{length} bytes",
                    )
                    return readBytes

                readBytes += newBytes

            if len(readBytes) < length:
                self.printWarning(
                    "_doReadAllBytes", f"Total {len(readBytes)}/{length} bytes"
                )
            return readBytes
        finally:
            self.connection.settimeout(oldTimeout)

    def _doReadLine(self, timeout_ms: int | None = 5000) -> str:
        """Read the stream up to '\n' - Including the '\n'."""

        oldTimeout = self.connection.gettimeout()
        deadline = None if timeout_ms is None else time.time() + (timeout_ms / 1000)

        newBytes = b""
        readBytes = b""
        while newBytes != b"\n":
            if deadline is not None:
                now = time.time()
                if now >= deadline:
                    self.printWarning(
                        "_doReadLine", f"Timeout exceeded after {timeout_ms} ms"
                    )
                    break
                self.connection.settimeout(
                    deadline - now
                )  # Adjust the timeout for each iteration

            newBytes = self.connection.recv(1)
            if (newBytes is None) or (len(newBytes) == 0):
                self.printWarning(
                    "_doReadLine", f"Stopped after {len(readBytes)} bytes"
                )
                break
            readBytes += newBytes

        self.connection.settimeout(oldTimeout)

        return readBytes.decode("utf-8", errors="replace")
