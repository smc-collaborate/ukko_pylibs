import errno
from inspect import getmembers, isfunction

import socket, os
import traceback
import threading
import time
from pathlib import Path
import sys
from typing import Any


################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

import ukko_pylibs.app.appSupport as app
from ukko_pylibs.basic.simpleUtils import Utils as Utils
from ukko_pylibs.transferableData.class_ITransferableData import ITransferableData
from ukko_pylibs.network.class_DataLink_ import DataLink
from ukko_pylibs.app.appSupport import appLog

#
################################################################################


def doProcessCommand(
    connection: DataLink,
    data: ITransferableData | None,
    commands: dict[str, dict[str, Any]],
) -> bool:
    if data is None:
        return False

    json_dict = data.dict_annotations
    binary_data = data.bitstream_data

    cmd = json_dict.get("cmd", None)
    if cmd is None or not isinstance(cmd, str):
        return connection.sendError("error", "PDI-01", "Invalid or missing cmd")

    response_json = None
    response_binary = None
    if cmd not in commands:
        print(f"❌  Unknown command '{cmd}'")
        return connection.sendError(
            "error",
            "PDI-04",
            f"Unknown command '{cmd}'",
            {"chosenCmd": cmd, "validCommands": list(commands.keys())},
        )

    try:
        kind = commands[cmd]["type"]
        func = commands[cmd]["func"]
        params = json_dict.get("params", {})
        if kind == "queued":
            # For queued actions, we add the request to the processing queue
            actionId = json_dict.get("action_id", None)
            if actionId is None or not isinstance(actionId, str):
                return connection.sendError(
                    "error",
                    "PDI-02",
                    "Invalid or missing action_id",
                    {"chosenCmd": cmd, "action_id": actionId},
                )

            print(
                f"ℹ️  Sending queued command '{cmd}' with actionId {actionId} -- {func.__doc__}"
            )

            response_json, response_binary = func(actionId, params, binary_data)
        else:
            print(f"ℹ️  Processing {kind} command '{cmd}' -- {func.__doc__}")
            response_json, response_binary = func(params, binary_data)

        return connection.createAndSend(
            "reply", {"chosenCmd": cmd, "response": response_json}, response_binary
        )

    except Exception as e:
        print(f"❌  Error processing command '{cmd}': {e}")
        return connection.sendError("error", "PDI-03", str(e), {"chosenCmd": cmd})


class ICmdServer:

    def print_info(self, msg: str):
        appLog.print_info(f"{self.dataType.__name__}: {msg}")

    def print_error(self, msg: str):
        appLog.print_error(f"{self.dataType.__name__}: {msg}")

    def print_warning(self, msg: str):
        appLog.print_warning(f"{self.dataType.__name__}: {msg}")

    def print_verbose(self, msg: str):
        appLog.print_verbose(f"{self.dataType.__name__}: {msg}")

    def isRunning(self) -> bool:
        return app.isRunning()

    def __init__(
        self, dataType: type[ITransferableData], commands: dict[str, Any] | str
    ):
        self.dataType = dataType

        if isinstance(commands, str):
            self.commands = {}
            for x in getmembers(sys.modules[commands], isfunction):
                if x[0].startswith("doDirectCommand_"):
                    action_name = x[0][len("doDirectCommand_") :]
                    action_name = ".".join(action_name.split("_", 1))

                    self.commands[action_name] = {"type": "direct", "func": x[1]}
                    self.print_info(
                        f"Registered direct command   : {action_name:<26} | {x[1].__doc__}"
                    )
                elif x[0].startswith("doActionsAdd_"):
                    action_name = "actions.add" + x[0][len("doActionsAdd_") :]
                    self.commands[action_name] = {"type": "queued", "func": x[1]}
                    self.print_info(
                        f"Registered add queued action: {action_name:<26} | {x[1].__doc__}"
                    )
        else:
            self.commands = commands

    def serverDoProcessCommand(
        self, dataLink: DataLink, data: ITransferableData | None
    ) -> bool:
        if not data is None:
            try:
                return doProcessCommand(dataLink, data, self.commands)
            # |x|except HandledException as ee:
            # |x|    pass
            except Exception as e:
                self.print_error(f"Error processing data: {e}")

                traceback.print_exc()

        return False


from ukko_pylibs.network.class_PhyConnection_Tcp import PhyConnection_Tcp


class CmdServer_Tcp(ICmdServer):
    def runInBackground(self, tcpPort: int | None):

        if tcpPort is not None:
            threading.Thread(target=self.server_tcp_run, args=(tcpPort,)).start()

    def server_tcp_run(self, tcpPort: int):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_address = ("0.0.0.0", tcpPort)  # Listen on all interfaces

        while True:
            try:
                server_socket.bind(server_address)
                break
            except OSError as e:
                if e.errno != 98:
                    self.print_error(f"Error binding to port {tcpPort}: {e}")
                self.print_warning(
                    f"Port {tcpPort} is already in use .. waiting for it to be available ..."
                )
                time.sleep(2)
        server_socket.listen(1)
        self.print_info(f"Server listening on {server_address}")

        while self.isRunning():
            connection = None
            try:
                self.print_info("Waiting for a client connection ...")
                connection, client_address = server_socket.accept()
                dataLink = DataLink[self.dataType](
                    PhyConnection_Tcp(connection, f"from {client_address}")
                )
                self.print_info(f"Connection from: {client_address}")
                data = dataLink.readDataObjectFromStream(timeout_ms=5000)
                if data == True:
                    self.print_info(
                        "No data received (e.g. timeout) but connection is still alive"
                    )
                elif data == False:
                    print(" No data received and connection appears to be closed")
                else:
                    print(f"📥 Processing: {data}")
                    self.serverDoProcessCommand(dataLink, data)
            except Exception as e:
                self.print_error(f"Server error: {e}")
            except KeyboardInterrupt:
                app.doHalt("stopped by user")

            if connection is not None:
                connection.close()

        print(" TCP Server closing")
        server_socket.close()


from ukko_pylibs.network.class_PhyConnection_Serial import PhyConnection_Serial


class CmdServer_Serial(ICmdServer):
    def runInBackground(self, link_via: str | None):

        if link_via is not None:
            threading.Thread(target=self.server_serial_run, args=(link_via,)).start()

    def server_serial_run(self, link_via: str):
        import serial, time

        if link_via.startswith("~/"):
            link_via = os.path.expanduser(link_via)
        link_via = link_via

        serialPort = None
        needsReconnecting = False
        while self.isRunning():

            ############################################################################################
            #
            # Step 1 - Connect to serial port
            #
            while self.isRunning() and ((serialPort is None) or needsReconnecting):
                if needsReconnecting:
                    if serialPort is not None:
                        self.print_info(
                            f"Disconnecting from serial port: {serialPort.name}"
                        )

                        serialPort.close()
                        serialPort = None
                time.sleep(2)  # Wait before trying to reconnect

                if serialPort is None:
                    try:

                        self.print_info(
                            f"Connecting to serial port: {link_via} with BaudRate 230400"
                        )
                        serialPort = serial.Serial(link_via, baudrate=230400, timeout=1)
                        self.print_info(f"Connected  to serial port: {serialPort.name}")

                    except serial.SerialException as e:
                        self.print_error(
                            f"Unable to connect to serial port '{link_via}'\n{e}"
                        )
                    except Exception as e:
                        self.print_error(
                            f"Unexpected error while connecting to serial port '{link_via}': {e}"
                        )
            if serialPort is None:
                continue
            ############################################################################################
            #
            # Step 2 - We have a connection - Get incoming packet
            #
            phyConnection = PhyConnection_Serial(
                serialPort, f"Serial[{serialPort.name}]"
            )
            dataLink = DataLink[self.dataType](phyConnection)
            request: ITransferableData | None = None
            while (
                self.isRunning()
                and not (phyConnection.needsReconnecting)
                and (request is None)
                and phyConnection.isConnected()
            ):
                request_ = dataLink.readDataObjectFromStream(timeout_ms=5000)
                if request_ == True:
                    self.print_info(
                        "No data received (e.g. timeout) but connection is still alive"
                    )
                elif request_ == False:
                    self.print_info(
                        "No data received and connection appears to be closed"
                    )
                    phyConnection.needsReconnecting = True
                else:
                    request = request_
            ############################################################################################
            #
            # Step 3 - Process incoming packet
            #
            if (request is not None) and self.isRunning():
                try:
                    self.print_info(f"Processing: {request}")
                    try:
                        self.serverDoProcessCommand(dataLink, request)
                    except Exception as e:
                        self.print_error(f"Error processing data[c1]: {e}")
                        traceback.print_exc()

                except OSError as e:
                    if e.errno == errno.EBADF:
                        self.print_info(f"Connection closed by client")
                        phyConnection.needsReconnecting = True
                        break
                    else:
                        self.print_warning(f"Connection closed : errno:{e.errno} {e}")
                        phyConnection.needsReconnecting = True
                        break

        if serialPort is not None:
            self.print_verbose(f"Disconnected from serial port: {serialPort.name}")
            serialPort.close()
