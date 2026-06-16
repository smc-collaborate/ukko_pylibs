import socket
import threading
import time
import os
import sys


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


from ukko_pylibs.network.class_PhyConnection_Tcp import PhyConnection_Tcp


class DataStreamer_Tcp[dataType: ITransferableData]:
    def name(self):
        return f"DataStreamer_Tcp[{dataType.__name__}]"

    def print_info(self, msg: str):
        appLog.print_info(f"{self.name()}: {msg}")

    def print_error(self, msg: str):
        appLog.print_error(f"{self.name()}: {msg}")

    def print_warning(self, msg: str):
        appLog.print_warning(f"{self.name()}: {msg}")

    def print_verbose(self, msg: str):
        appLog.print_verbose(f"{self.name()}: {msg}")

    def isRunning(self) -> bool:
        return app.isRunning()

    def runInBackground(self, tcpPort: int | None):

        if tcpPort is not None:
            threading.Thread(target=self._server_tcp_run, args=(tcpPort,)).start()

    def _server_tcp_run(self, tcpPort: int):
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
        server_socket.settimeout(1)  # Set a timeout for accepting connections
        self.print_info(f"Server listening on {server_address}")

        connectedList: list[PhyConnection_Tcp] = []
        while self.isRunning():
            connection = None
            try:
                self.print_info("Ready for a client connection ...")
                try:
                    connection, client_address = server_socket.accept()
                    self.print_info(f"Connection from: {client_address}")

                    thisConnection = PhyConnection_Tcp(
                        connection, f"from {client_address}"
                    )
                    connectedList.append(thisConnection)
                    dataLink = DataLink[dataType](thisConnection)
                except socket.timeout:
                    continue  # Loop back and check if we should keep running

                self.print_verbose(f"Connection Review ({len(connectedList)} total):")
                for c in list(connectedList):
                    if c.isConnected():
                        self.print_verbose(f"Connection alive: {c}")
                    else:
                        self.print_verbose(f"Connection closed: {c}")
                        c.doClose()
                        connectedList.remove(c)
            except Exception as e:
                self.print_error(f"Server error: {e}")
            except KeyboardInterrupt:
                app.doHalt("stopped by user")

        print(" TCP Server closing")
        for c in connectedList:
            c.doClose()

        server_socket.close()
