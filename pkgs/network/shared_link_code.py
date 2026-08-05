import os
import socket

import serial


from typing import Any, NoReturn


import ukkoUtils
from ukkoUtils import HandledException
from appLogging import appLog
from transferableData import ITransferableData
from network import IPhyConnection, PhyConnection_Tcp, PhyConnection_Serial
from schemaHandling import schemaProcessing

#
################################################################################

VALID_LINK_TYPES = ["tcp", "serial"]

from typing import TypeVar, Generic

T_LinkedDataType = TypeVar("T_LinkedDataType", bound=ITransferableData)


class LinkToDevice(Generic[T_LinkedDataType]):
    """Class to handle the link to the device."""

    def __init__(
        self,
        link_type: str,  # < "tcp" or "serial"
        link_via: str,
        link_annotatedKindText: str = "",
    ):
        self.configValues = {
            "serialBaud": 230400,
        }
        ####
        self.phyConnection: IPhyConnection | None = None
        self.linkType_PhysicalLayer = link_type.lower()  # tcp or serial
        self.linkType_asText = link_type + ":" + T_LinkedDataType.__name__

        self.link_via = link_via.removeprefix(link_type + ":")
        self.link_kindTextWithSuffix = (
            ""
            if link_annotatedKindText == ""
            else (link_annotatedKindText.removesuffix("/") + "/")
        )
        self.errMsgCount = 0

    def doConnect(self):
        """Connect to the device based on the link type."""
        self.phyConnection = None
        if self.physicalLinkTypeIs("tcp"):
            self._connect_tcpServer()
            if self._tcp_client_socket is not None:
                self.phyConnection = PhyConnection_Tcp(
                    self._tcp_client_socket, self.link_via
                )
        elif self.physicalLinkTypeIs("serial"):
            self._connect_serial(True)
            if hasattr(self, "serial_port"):
                self.phyConnection = PhyConnection_Serial(
                    self.serial_port, self.link_via
                )
        else:
            self.throw_error(
                "doConnect",
                f"Unable to connect[Invalid link linkPhysicalLayer '{self.linkType_PhysicalLayer}' -- must be 'tcp' or 'serial']",
            )

    def getPhysicalLinkType(self) -> str:
        return self.linkType_PhysicalLayer

    def physicalLinkTypeIs(self, phyToMatch: str) -> bool:
        return self.getPhysicalLinkType() == phyToMatch.lower()

    def doSend(self, data: T_LinkedDataType) -> str | NoReturn:
        if (data is None) or (type(data) is not T_LinkedDataType):
            errmsg = f"Invalid object ({type(data)}) provided for transfer"
            return self._transfer_failure(errmsg)
        if self.phyConnection is None:
            errmsg = f"Not connected to any device - unable to transfer data"
            return self._transfer_failure(errmsg)

        packed_bytes = data.toBytes(withStreamWrapping=True)
        if packed_bytes is None:
            return self._transfer_failure("Invalid packed data")

        txtOut = ukkoUtils.asJsonStr(data.dict_annotations)
        txtOut = ""

        appLog.print_verbose(
            f"Transferring to {self.linkType_asText} device: {ukkoUtils.toHex(packed_bytes)} …"
        )
        try:
            self.phyConnection.sendAllBytes_orException(packed_bytes)  # Send data
        except Exception as e:
            return self._transfer_failure(
                f"Unable to send data {len(packed_bytes)} bytes: {e}"
            )

        appLog.print_verbose(
            f"Data sent to        {self.linkType_asText.replace('TransferableData_','')} device: {data} …"
        )

        return txtOut

    def getSuffixedKind(self, suffix: str) -> str:
        return self.link_kindTextWithSuffix + suffix.removeprefix("/")

    @staticmethod
    def getType() -> type[ITransferableData]:

        if T_LinkedDataType is ITransferableData:
            return T_LinkedDataType
        raise HandledException(
            f"LinkToDevice.getType[ITransferableData]: InvalidDataType {T_LinkedDataType}"
        )

    @staticmethod
    def toLinkedDataType(obj) -> T_LinkedDataType:

        if type(T_LinkedDataType) is T_LinkedDataType:
            return obj
        raise HandledException(
            f"LinkToDevice.toLinkedDataType({type(obj)}): InvalidDataType for {T_LinkedDataType}"
        )

    def doReceive(
        self, txtOut_ifSerial: str = "", timeout_ms: int | None = None
    ) -> T_LinkedDataType | bool:
        """Reads from out connection  Returns: (ITransferableData) or 'isStillConnected'=true/false"""
        if self.phyConnection is None:
            errmsg = f"Not connected to any device - unable to ReceiveData"
            return self._transfer_failure(errmsg)
        return self.toLinkedDataType(
            self.getType().create_readFromStream(self.phyConnection, timeout_ms)
        )

    #####################################
    #
    # Internal only - don't look at these
    def _connect_serial(self, isConnect: bool):
        """Connect to /Disconnect from a serial port."""
        if hasattr(self, "serial_port"):
            appLog.print_verbose(
                f"Disconnected from serial port: {self.serial_port.name}"
            )
            self.serial_port.close()
            del self.serial_port

        if isConnect:
            try:
                fullName = self.link_via
                if fullName.startswith("~/"):
                    fullName = os.path.expanduser(self.link_via)
                self.serial_port = serial.Serial(
                    fullName, baudrate=self.configValues["serialBaud"], timeout=1
                )
            except serial.SerialException as e:
                self.throw_error(
                    "_connect_serial",
                    f"Unable to connect to serial port '{self.link_via}'",
                    e,
                )
            appLog.print_verbose(
                f"Connected to serial port: {self.serial_port.name} [Baud {self.configValues['serialBaud']}]"
            )

    def doDisconnect(self):
        """Disconnect the the device based on the link type."""
        if self.phyConnection is not None:
            self.phyConnection.doClose()

    def _connect_tcpServer(self):
        """Connect to a TCP server."""
        self._tcp_client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Enable TCP keep-alives
        self._tcp_client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self._tcp_client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
        self._tcp_client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
        self._tcp_client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 100)

        if not (":" in self.link_via):

            from appAssist import (
                app,
            )  # <--- Import here to avoid circular import issues

            DEFAULT_PORT_NUMBER = app.appGetValue("DEFAULT_PORT", 12302)
            appLog.print_verbose(
                f"No port specified in link_via '{self.link_via}', using default port {DEFAULT_PORT_NUMBER}"
            )
            self.link_via += f":{DEFAULT_PORT_NUMBER}"

        _address = self.link_via.split(":")
        if len(_address) != 2:
            self.throw_error(
                "_connect_tcpServer", f"Invalid server address:'{self.link_via}'"
            )
        else:
            try:
                self.tcp_server_address = (_address[0], int(_address[1]))
            except ValueError:
                self.throw_error(
                    "_connect_tcpServer", f"Invalid port number '{_address[1]}'"
                )

        try:
            self._tcp_client_socket.connect(self.tcp_server_address)
        except Exception as ee:
            if isinstance(ee, ConnectionRefusedError) and (
                (_address[0] == "localhost")
            ):
                suggestedAppName = self.link_kindTextWithSuffix.removesuffix(
                    "/"
                ).replace("/", "-")

                self.throw_error(
                    "_connect_tcpServer",
                    f"Connection to server '{self.link_via}' was refused\n"
                    + f"Please ensure that 'do-run-simulated-{suggestedAppName}.sh' is running in another window",
                )
            else:
                self.throw_error(
                    "_connect_tcpServer",
                    f"Unable to connect to server '{self.link_via}': {ee}",
                    ee,
                )
            self._tcp_client_socket = None

    def _transfer_failure(self, msg: str) -> NoReturn:
        self.throw_error(
            "_transfer_failure",
            f"Unable to transfer {self.linkType_asText} data[{msg}]",
        )
        # Or Change to return an error string instead of exiting, if you want to handle it differently

    def print_error(self, method: str, msg: str, ee: Exception | None = None) -> str:
        asPrinted = f"{self.linkType_asText}.{method}: {msg}"
        if ee is not None:
            asPrinted += f" - {ee}"
        appLog.print_error(asPrinted)
        return asPrinted

    def throw_error(
        self, method: str, msg: str, ee: Exception | None = None
    ) -> NoReturn:
        raise Exception(self.print_error(method, msg, ee))

    def stream_dataKind(self):
        return T_LinkedDataType

    ##############################################
    #
    # From here it is all query handling
    #
    def doTransfer(self, data: T_LinkedDataType) -> T_LinkedDataType:
        """Transfer data to the device."""

        txtOut = self.doSend(data)
        result = self.doReceive(txtOut)
        if result is True:
            result = self.getType().create_invalidKind(
                self.getSuffixedKind("reply"),
                "No response received",
            )
        elif result is False:
            result = self.getType().create_invalidKind(
                self.getSuffixedKind("reply"),
                "No response received (Connection closed)",
            )
        else:
            appLog.print_verbose(
                f"Received reply from {self.linkType_asText.replace('TransferableData_','')} device: {result}"
            )

        return self.toLinkedDataType(result)

    def doQuery(self, cmdIfKnown: str, request: T_LinkedDataType) -> T_LinkedDataType:
        appLog.print_verbose(f"Sending: {request}")

        schemaProcessing.Schema(f"{cmdIfKnown}", "request").doValidate(request)
        self.doConnect()
        appLog.print_verbose("Connected to device")

        try:
            reply = self.doTransfer(request)
            fatalError = reply.getInvalidReason()

            if fatalError:
                appLog.print_error(fatalError)
            else:
                cmdReplyToReview = str(reply.getAnnotation("chosenCmd", cmdIfKnown))

                schemaProcessing.Schema(f"{cmdReplyToReview}", "reply").doValidate(
                    reply
                )

                errTxt = reply.getErrorTextIfAny()
                if errTxt is not None:
                    appLog.print_error(f"Reply from device={errTxt}")
                    self.errMsgCount += 1
            return reply

        finally:
            self.doDisconnect()

    def doQuery_cmd(
        self,
        cmd: str,
        params: dict | None = None,
        binaryData: bytes | None = None,
        actionId: str | None = None,
    ) -> ITransferableData:
        jsonDataRequest: dict[str, Any] = {"cmd": cmd}
        if params is not None:
            jsonDataRequest["params"] = params
        if (actionId is not None) and (actionId != ""):
            jsonDataRequest["action_id"] = actionId_generator(actionId)

        request = self.getType().create_fromKindWithDict(
            self.getSuffixedKind("/request"), jsonDataRequest, binaryData
        )

        return self.doQuery(cmd, self.toLinkedDataType(request))

    def doQuery_cmdGetResponseElement(
        self,
        cmd: str,
        element_path: str,
        params: dict[str, Any] | None = None,
        binaryData: bytes | None = None,
    ) -> Any | None:
        reply = self.doQuery_cmd(cmd, params, binaryData)
        return reply.getAnnotation(f"response/{element_path}", None)

    def doQuery_cmdGetResponseElement_int(
        self,
        cmd: str,
        element_path: str,
        params: dict[str, Any] | None = None,
        binaryData: bytes | None = None,
    ) -> int:
        reply = self.doQuery_cmd(cmd, params, binaryData)
        value = reply.getAnnotation(f"response/{element_path}", None)
        if value is None:
            raise HandledException(
                f"Link[{cmd}].Response[{element_path}] not found in {reply}"
            )
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except Exception:
                pass
        raise HandledException(
            f"Link[{cmd}].Response[{element_path}] expected to be integer, got {type(value)}"
        )

    def doQuery_cmdGetResponseDict(
        self,
        cmd: str,
        params: dict | None = None,
        binaryData: bytes | None = None,
    ) -> dict[str, Any]:
        response = self.doQuery_cmdGetResponseElement(cmd, "", params, binaryData)
        if not isinstance(response, dict):
            appLog.print_error(
                f"Link[{cmd}].Response expected to be dict, got {type(response)}"
            )
            response = {}

        return response


def actionId_generator(actionId: str = "_auto_") -> str:
    """Generate a unique action ID."""
    if (actionId is None) or (actionId == "_auto_"):
        # Generate a unique request ID using UUID and process ID
        import os
        import uuid

        return f"{str(uuid.uuid4())}_{os.getpid()}"
    else:
        return str(actionId)
