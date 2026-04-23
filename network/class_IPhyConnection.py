import sys, struct
from typing import Union
import os

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import Utils as Utils
from ukko_pylibs.basic.appSupport import appLog

#
################################################################################


class IPhyConnection:
    """Abstract class for physical connection  (eg: Tcp Connection, serialConnection etc)
    These need to be implemented by subclasses:
     * def _getTextName(self) -> str:
     * def _doClose(self) -> None:
     * def _doSetTimeout_seconds(self, timeout_seconds: float):
     * def _getIsConnected(self)->bool:
     * def _doSendAllBytes_orException(self, data: bytes):
     * def _doReadAllBytes(self, length: int, timeout_ms: int | None = None) -> bytes:
     * def _doReadLine(self, timeout_ms: int | None = None) -> str:
    """

    @staticmethod
    def isOrNone(connection) -> Union["IPhyConnection", None]:
        try:
            if connection is not None and isinstance(connection, IPhyConnection):
                return connection
        except Exception:
            pass
        appLog.print_warning(
            f"IPhyConnection.isOrNone({type(connection)})- Not an IPhyConnection"
        )
        return None

    """Represents a physical connection, which can be either a TCP socket or a serial port. Provides common methods for sending and receiving data over the connection."""

    def __init__(self, infoText: str | None):
        self.infoText = infoText
        self.needsReconnecting = False
        appLog.print_verbose(f"{self}: Created[{self.infoText}]")

    def className(self):
        return self.__class__.__name__

    def _getTextName(self) -> str:
        raise NotImplementedError(
            f"{self.className()}._getTextName: Should be implemented by subclasses"
        )

    def _doClose(self) -> None:
        raise NotImplementedError(
            f"{self.className()}._doClose: Should be implemented by subclasses"
        )

    def _doSetTimeout_seconds(self, timeout_seconds: float):
        raise NotImplementedError(
            f"{self.className()}._doSetTimeout_seconds: Should be implemented by subclasses"
        )

    def _getIsConnected(self) -> bool:
        raise NotImplementedError(
            f"{self.className()}._getIsConnected: Should be implemented by subclasses"
        )

    def _doSendAllBytes_orException(self, data: bytes):
        raise NotImplementedError(
            f"{self.className()}._doSendAllBytes_orException: Should be implemented by subclasses"
        )

    def _doReadAllBytes(self, length: int, timeout_ms: int | None = None) -> bytes:
        raise NotImplementedError(
            f"{self.className()}._doReadAllBytes: Should be implemented by subclasses"
        )

    def _doReadLine(self, timeout_ms: int | None = None) -> str:
        raise NotImplementedError(
            f"{self.className()}._doReadLine: Should be implemented by subclasses"
        )

    def printWarning(self, part: str, msg: str):
        appLog.print_warning(f"{self}.{part}: {msg}")

    def printInfo(self, msg: str):
        appLog.print_info(f"{self}: {msg}")

    def printError(self, part: str, msg: str, withException: Exception | None = None):
        if withException:
            appLog.print_error(f"{self}.{part}: {msg} - Exception: {withException}")
        else:
            appLog.print_error(f"{self}.{part}: {msg}")

    #####################
    #
    # Use the private overloadable methods to implement the public interface, with error handling and type checking.
    #
    def readLine(self, timeout_ms: int | None = None) -> str:
        try:
            return self._doReadLine(timeout_ms)
        except Exception as e:
            self.printError("readLine", "Unexpected error", e)
            self.needsReconnecting = True
            raise e

    def isConnected(self) -> bool:
        try:
            return self._getIsConnected()
        except Exception as e:
            sys.stderr.write(
                f"{self}.Error checking connection: {e} - False will be returned\n"
            )
        return False

    def doClose(self):
        try:
            self._doClose()
        except Exception as e:
            self.printError("doClose", "Error closing connection", e)

    def sendAllBytes_orException(self, data: bytes):
        try:
            self._doSendAllBytes_orException(data)
        except Exception as e:
            self.printError("sendAllBytes_orException", "Error sending data", e)
            raise e

    def read_Bytes(self, length: int, timeout_ms: int | None = None) -> bytes:
        """Read a fixed number of bytes from the stream."""

        if length < 0:
            self.printError("read_Bytes", f"Invalid length {length}")
            return b""
        else:
            return self._doReadAllBytes(length, timeout_ms)

    def __str__(self) -> str:
        try:
            return self._getTextName()
        except Exception as e:
            return f"ExceptionLink[{e}]"

    def setTimeout_seconds(self, timeout_seconds: float):
        try:
            self._doSetTimeout_seconds(timeout_seconds)
        except Exception as e:
            self.printError("setTimeout_seconds", "Error setting timeout", e)

    ###################################################################################
    #
    # Additional helper methods for common patterns, such as reading a size header followed by a payload, or reading/writing protobuf messages.
    #
    def readSizeHeader_numBytes(self, timeout_ms: int | None = 5000) -> int | None:
        data = self.read_Bytes(4, timeout_ms)  # Receive data
        if not data:
            return None
        if len(data) != 4:
            self.printError(
                "readSizeHeader_numBytes",
                f"Invalid data size header length: expected 4 bytes, got {len(data)} bytes",
            )
            return -1
        data_size = struct.unpack(">I", data)[0] if (len(data) == 4) else 0

        if (data_size < 2) or (data_size > 1024 * 1024 * 1024):
            self.printError(
                "readSizeHeader_numBytes",
                f"Invalid data size header received: 0x{data.hex()}",
            )
            return -2
        return data_size

    ##################################################################
    #
    # Additional methods for reading/writing protobuf messages,
    # using the underlying connection to send/receive data as needed.
    #
    def protobuf_read_varInt(
        self,
        noteOnEmpty: bool = True,
        initialByte: int = -1,
        timeout_ms: int | None = None,
    ) -> int | None:
        """Read a variable-length integer from the stream."""
        value = 0
        shift = 0
        while True:
            if initialByte >= 0:
                bytesIn = bytes([initialByte])
                initialByte = -1
            else:
                bytesIn = self.read_Bytes(1, timeout_ms)
            if len(bytesIn) != 1:
                if shift != 0:
                    self.printError(
                        "protobuf_read_varInt",
                        f"Connection closed or error after {shift} bits",
                    )
                elif noteOnEmpty:
                    self.printError("protobuf_read_varInt", "No data received")

                return None  # Connection closed or error
            byte = bytesIn[0]
            value |= (byte & 0x7F) << shift
            if not (byte & 0x80):
                break
            shift += 7
            if shift > 28:
                self.printError(
                    "protobuf_read_varInt", f"Varint too long at {shift} bits"
                )
                return None  # Invalid varint

        return value

    def protobuf_read_field(
        self,
        noteOnEmpty: bool = True,
        timeout_initial_ms: int | None = None,
    ) -> tuple[int, bytes | int] | bool:
        """Read (fieldNumber, data) element from the socket."""

        tag = self.protobuf_read_varInt(
            noteOnEmpty=noteOnEmpty, timeout_ms=timeout_initial_ms
        )

        if tag is None:
            return False

        fieldNumber = (tag >> 3) & 0x1FFFFFFF
        wireType = tag & 0x7

        value: bytes | int = b""
        errMsg = None
        if wireType == 0:  # Varint
            valueOrNone = self.protobuf_read_varInt(noteOnEmpty=noteOnEmpty)
            if valueOrNone is None:
                errMsg = "Expected varint, got None"
            else:
                value = valueOrNone
        else:
            length: int | None = None
            if wireType == 1:  # Fixed64
                length = 8
            elif wireType == 2:  # Length-delimited
                # Read the length of the value
                length = self.protobuf_read_varInt(noteOnEmpty=noteOnEmpty)
            elif wireType == 5:  # Fixed32
                length = 4
            else:
                errMsg = f"Unknown wire type {wireType}"

            if errMsg is None:
                if (
                    length is None or length < 0 or length > 50 * 1024 * 1024
                ):  # Arbitrary limit for length
                    errMsg = f"Invalid length {length}"
                elif length == 0:
                    value = b""
                else:
                    value = self.read_Bytes(length)

                    if len(value) < length:
                        errMsg = f"Expected {length} bytes, got {len(value)}"

        if errMsg is not None:
            self.printError(
                "protobuf_read_field_type_data",
                f"field: {fieldNumber}, wireType:{wireType} -> {errMsg}",
            )
            return True

        return (fieldNumber, value)

    def phyConnection_protobuf_read_field(
        self,
        noteOnEmpty: bool = True,
        timeout_initial_ms: int | None = None,
    ) -> tuple[int, bytes | int] | bool:
        """Read (fieldNumber, data) element from the socket."""

        tag = self.protobuf_read_varInt(
            noteOnEmpty=noteOnEmpty, timeout_ms=timeout_initial_ms
        )

        if tag is None:
            return False

        fieldNumber = (tag >> 3) & 0x1FFFFFFF
        wireType = tag & 0x7

        value: bytes | int = b""
        errMsg = None
        if wireType == 0:  # Varint
            valueOrNone = self.protobuf_read_varInt(noteOnEmpty=noteOnEmpty)
            if valueOrNone is None:
                errMsg = "Expected varint, got None"
            else:
                value = valueOrNone
        else:
            length: int | None = None
            if wireType == 1:  # Fixed64
                length = 8
            elif wireType == 2:  # Length-delimited
                # Read the length of the value
                length = self.protobuf_read_varInt(noteOnEmpty=noteOnEmpty)
            elif wireType == 5:  # Fixed32
                length = 4
            else:
                errMsg = f"Unknown wire type {wireType}"

            if errMsg is None:
                if (
                    length is None or length < 0 or length > 50 * 1024 * 1024
                ):  # Arbitrary limit for length
                    errMsg = f"Invalid length {length}"
                elif length == 0:
                    value = b""
                else:
                    value = self.read_Bytes(length)

                    if len(value) < length:
                        errMsg = f"Expected {length} bytes, got {len(value)}"

        if errMsg is not None:
            self.printError(
                "protobuf_read_field_type_data",
                f"field: {fieldNumber}, wireType:{wireType} -> {errMsg}",
            )
            return True

        return (fieldNumber, value)
