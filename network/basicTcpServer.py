import errno
import ipaddress
import os
import socket
import sys
import threading
from time import sleep
from typing import Tuple
import netifaces as ni

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic import simpleUtils
from ukko_pylibs.basic.simpleUtils import PrettyText
from ukko_pylibs.app.appSupport import appLog
from ukko_pylibs.basic.logger import SimpleLogger
import ukko_pylibs.app.appSupport as app

################################################################################


##########################################################################################################
#
#
#
class Interface_BasicServerOut:
    """Basic interface for a server: asSimpleInfo() and doBroadcast()"""

    def doBroadcast(self, dataIn: bytes | str | None) -> int:
        """Broadcasts the data to all connected clients (TCP Only)
        Returns the number of connections the data was broadcasted to."""
        return 0

    def sendToNewConnections(self, dataIn: bytes | str) -> int:
        """Sends the data to all newly connected clients (TCP Only)
        Returns the number of connections the data was sent to."""
        return 0

    def __init__(self, name):
        self.NAME = name

    def _print_info(self, msg: str):
        appLog.print_info(f"{self.NAME}: {msg}")

    def _print_verbose(self, msg: str):
        appLog.print_verbose(f"{self.NAME}: {msg}")

    def asSimpleInfo(self):
        """Returns a simple dictionary with server info."""
        result = {"name": self.NAME}
        return result

    def connectionAddress(self) -> str:
        """Returns a string representation of the connection address.
        eg: "tcp://192.168.100.13:12345" or "/dev/serial/ttyUSB0"
        """
        return "<unknown>"


class BasicTcpServer(Interface_BasicServerOut):

    def __init__(self, name: str = "BasicTcpServer", tcpPort: int = 0):
        Interface_BasicServerOut.__init__(self, name)
        self.tcpConnections: list["BasicTcpServer.BasicTcpServerConnection"] = []
        self.tcpPort = tcpPort
        self.thread = threading.Thread(target=self._tcp_connection_run)
        self.thread.start()

    def connectionAddresses(
        self, withPrefix: bool = False, withSuffix: bool = False
    ) -> list[str]:
        """Returns a list of string representations of the connection addresses.
        eg: ["tcp://192.168.100.13:12345"]
        """
        results: list[str] = []
        prefix = "tcp://" if withPrefix else ""
        for interface in ni.interfaces():
            if interface == "lo":
                continue
            ip_txt = "<IP Address>"
            try:
                entries = ni.ifaddresses(interface)
                if ni.AF_INET in entries:
                    for _ip in entries[ni.AF_INET]:
                        ip_txt = _ip["addr"]
                        if not ipaddress.IPv4Address(ip_txt).is_loopback:
                            suffix = f" [{interface}]" if withSuffix else ""
                            results.append(f"{prefix}{ip_txt}:{self.tcpPort}{suffix}")
            except Exception as e:
                appLog.print_warning(
                    f"Interface[{interface}]: Unable to get local IP address: {e}"
                )

        if results == []:
            results.append(f"{prefix}localhost:{self.tcpPort}")
        return results

    def _tcp_connection_run(self):
        self.tcpServer_address = ("0.0.0.0", self.tcpPort)  # Listen on all interfaces
        self.tcpServer_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcpServer_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        ############################################################################################
        #
        # Step 1 - Bind and start listening
        #
        while app.isRunning():
            try:
                self.tcpServer_socket.bind(self.tcpServer_address)
                break
            except OSError as e:
                if e.errno != 98:
                    appLog.print_error(f"Error binding to port {self.tcpPort}: {e}")
                appLog.print_warning(
                    f"Port {self.tcpPort} is already in use .. waiting for it to be available ..."
                )
                sleep(2)
            except KeyboardInterrupt:
                app.doHalt("By user [a]")

        if not app.isRunning():
            self._print_info("Server exiting  [a]")

        self.tcpServer_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        self.tcpServer_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 5)
        self.tcpServer_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 5)
        self.tcpServer_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 100)

        self.tcpServer_socket.listen(1)
        self._print_verbose(f"Server listening on tcpPort: {self.tcpPort}")

        ############################################################################################
        #
        # Step 2 - Accept all connections and add to list
        #
        connectionId = 0
        infoChanged = True
        while app.isRunning():
            try:
                if infoChanged:
                    self._print_verbose("Waiting for a client connection ...")
                    infoChanged = False

                try:
                    self.tcpServer_socket.settimeout(1.0)  # Set a timeout for accept()
                    connection, client_address = self.tcpServer_socket.accept()
                except socket.timeout:
                    continue
                except:
                    raise

                connectionId += 1
                self._print_info(f"Connection[{connectionId}] from: {client_address}")
                infoChanged = True
                # Create a new thread for each client connection
                BasicTcpServer.BasicTcpServerConnection.doThreadedRun_tcp(
                    f"TcpPort({self.tcpPort}).[{connectionId}]",
                    connection,
                    client_address,
                    self,
                )
            except KeyboardInterrupt:
                app.doHalt("By user [c]")

        self._print_info("Server closing")

        for conn in list(self.tcpConnections):
            try:
                self._print_info(f"Closing connection to {conn.name}")
                conn.close()
            except Exception:
                pass

        self.tcpServer_socket.close()
        self.tcpConnections = []

    def connections_getCount(self):
        """Returns the number of active connections."""
        return len(self.tcpConnections)

    def hasConnections(self) -> bool:
        return self.connections_getCount() > 0

    def doSendToConnectionAndCloseIfDone(
        self,
        connection: "BasicTcpServer.BasicTcpServerConnection",
        dataIn: bytes | str | None,
    ) -> int:
        numBytesSent = 0
        if dataIn is not None and connection is not None:
            try:
                numBytesSent = connection.sendAll(dataIn)
            except Exception as e:
                if isinstance(e, OSError) and e.errno == errno.EPIPE:
                    connection.print_warning(f"Connection is disconnected")
                elif isinstance(e, OSError) and e.errno == errno.ECONNRESET:
                    connection.print_warning(f"Connection is disconnected by remote")
                else:
                    connection.print_error(f"Unable to send data to socket: {e}")
                connection.close()

        return numBytesSent

    def sendToNewConnections(self, dataIn: bytes | str) -> int:
        """Sends the bytes to all newly connection clients
        Returns the number of connections the data was sent to."""
        sentCount = 0
        numBytesSentPerConnection = 0
        for linkOut in list(self.tcpConnections):
            if linkOut.sendCount == 0:
                numBytesSentPerConnection = self.doSendToConnectionAndCloseIfDone(
                    linkOut, dataIn
                )
                sentCount += 1

        if sentCount > 0:
            appLog.print_info(
                f"Sent to {PrettyText.pluralize(sentCount, 'connection')}: {PrettyText.pluralize(numBytesSentPerConnection, 'byte')}"
            )

        return sentCount

    def doBroadcast(self, dataIn: bytes | str | None) -> int:
        sentCount = 0
        """Broadcasts the bytes to all connected clients (TCP Only)
           Returns the number of connections the data was broadcasted to."""
        if dataIn is None:
            appLog.print_info(
                f"Broadcasting to {len(self.tcpConnections)} connections: <None>"
            )
            return sentCount

        numBytesSentPerConnection = 0

        for linkOut in list(self.tcpConnections):
            numBytesSentPerConnection = self.doSendToConnectionAndCloseIfDone(
                linkOut, dataIn
            )
            sentCount += 1

        if sentCount > 0:
            appLog.print_verbose("No connections to broadcast to")
        else:
            appLog.print_verbose(
                f"Broadcasted to {PrettyText.pluralize(sentCount, 'connection')}: {PrettyText.pluralize(numBytesSentPerConnection, 'byte')}"
            )

        return sentCount

    def asSimpleInfo(self):
        """Returns a simple dictionary with server info."""
        result = Interface_BasicServerOut.asSimpleInfo(self)
        if self.tcpPort is not None:
            result["tcpPort"] = self.tcpPort

        nCount = len(self.tcpConnections)
        # if (nCount > 0):
        result["networkConnections"] = nCount

        return result

    def tcpConnections_add(self, connection: "BasicTcpServer.BasicTcpServerConnection"):
        """Adds a new connection to the list."""
        self.tcpConnections.append(connection)

    def tcpConnections_remove(
        self, connection: "BasicTcpServer.BasicTcpServerConnection"
    ):
        """Removes a connection from the list."""
        if connection in self.tcpConnections:
            self.tcpConnections.remove(connection)

    class BasicTcpServerConnection(SimpleLogger):
        @staticmethod
        def doThreadedRun_tcp(
            loggingPrefix: str,
            client_socket: socket.socket,
            client_address: Tuple[str, int],
            owner: "BasicTcpServer",
        ):
            connection = BasicTcpServer.BasicTcpServerConnection(
                loggingPrefix, client_socket, client_address, owner
            )
            owner.tcpConnections_add(connection)
            if connection.handlerModule is not None:
                connection.startThreadedRun()
            return connection

        def startThreadedRun(self):
            client_handler = threading.Thread(target=self.run)
            client_handler.start()

        def __init__(
            self,
            name: str,
            connection: socket.socket,
            client_address: Tuple[str, int],
            owner: "BasicTcpServer",
            dataType: type | None = None,
        ):
            super().__init__(name)
            self.name = name
            self.client_connection = connection
            self.client_address = client_address
            self.owner: BasicTcpServer = owner
            self.handlerModule = None
            self.dataType = dataType
            self.sendCount = 0

        def sendAll(self, dataIn: bytes | str | None) -> int:
            if dataIn is None:
                return 0

            self.sendCount += 1
            if isinstance(dataIn, str):
                dataBytes = (dataIn.removesuffix("\n") + "\n").encode("utf-8")
            else:
                dataBytes = dataIn
            self.client_connection.sendall(dataBytes)  # Send data
            return len(dataBytes)

        def close(self):
            try:
                self.owner.tcpConnections_remove(self)
                self.print_info(
                    f"Connection with {self.client_address} closed : New connection count is {self.owner.connections_getCount()}"
                )
                self.client_connection.close()
            except Exception as e:
                self.print_warning(f"Error closing connection: {e}")

        def run(self):
            self.print_info(
                f"Monitorng connection from {self.client_address} : For commands"
            )
            try:
                while app.isRunning():
                    try:
                        self.print_info("Client checking ...")
                        data = self.client_connection.recv(1024)
                        if data is None:
                            self.print_info("Client disconnected(a)")
                            break
                        elif len(data) == 0:
                            self.print_info("Client disconnected(b)")
                            break
                        elif self.handlerModule is None:
                            self.print_warning(
                                f"Discarding Received from client: {len(data)} bytes - No handler provided"
                            )
                        else:
                            self.print_warning(
                                f"Discarding Received from client: {len(data)} bytes - Handler not tested"
                            )
                    except OSError as e:
                        if e.errno == errno.EBADF:
                            self.print_info(f"Connection closed by client")
                            break
                        elif (isinstance(e, socket.timeout)) or (str(e) == "timed out"):
                            self.print_info(f"Waiting for command ...")
                        else:
                            self.print_warning(
                                f"Connection closed : errno:{e.errno} {e}"
                            )
                            break

                    except Exception as e:
                        app.doHalt(f"❌  Server error[c]: {e}")
                    except KeyboardInterrupt:
                        self.print_info("Server stopped by user  [c]")
            except Exception as e:
                self.print_warning(f"Error during connection handling: {e}")
            finally:
                self.close()
