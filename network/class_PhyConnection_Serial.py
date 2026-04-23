import sys
import serial
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


class PhyConnection_Serial(IPhyConnection):
    """SerialConnection:
    These need to be implemented:
     * def _getTextName(self) -> str:
     * def _doClose(self) -> None:
     * def _doSetTimeout_seconds(self, timeout_seconds: float):
     * def _getIsConnected(self)->bool:
     * def _doSendAllBytes_orException(self, data: bytes):
     * def _doReadAllBytes(self, length: int, timeout_ms: int | None = None) -> bytes:
     * def _doReadLine(self, timeout_ms: int | None = None) -> str:
    """

    def __init__(self, connection: serial.Serial, infoText: str | None):
        super().__init__(infoText)
        self.connection = connection

    def _getTextName(self) -> str:
        txt = f"{self.infoText if self.infoText else self.connection.name}"
        if not (txt.startswith("Serial[") or txt.startswith("SerialLink[")):
            txt = f"SerialLink[{txt}]"

        return txt

    def _doClose(self):
        self.connection.close()

    def _doSetTimeout_seconds(self, timeout_seconds: float):
        self.connection.timeout = timeout_seconds

    def _getIsConnected(self) -> bool:
        return self.connection.is_open

    def _doSendAllBytes_orException(self, data: bytes):
        self.connection.write(data)

    def _doReadAllBytes(self, length: int, timeout_ms: int | None = None) -> bytes:
        """Read a fixed number of bytes from the stream."""
        old_timeout = None
        if timeout_ms is not None:
            old_timeout = self.connection.timeout
            self.connection.timeout = timeout_ms / 1000
        try:
            data = self.connection.read(length)
        finally:
            if old_timeout is not None:
                self.setTimeout_seconds(old_timeout)

        return data

    def _doReadLine(self, timeout_ms: int | None = None) -> str:
        """Read the stream up to '\n' - Including the '\n'."""
        old_timeout = None
        if timeout_ms is not None:
            old_timeout = self.connection.timeout
            self.setTimeout_seconds(timeout_ms / 1000)
        try:
            return self.connection.readline().decode("utf-8", errors="replace")
        finally:
            if old_timeout is not None:
                self.setTimeout_seconds(old_timeout)
