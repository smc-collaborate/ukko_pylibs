##########################
# Sample App to use this:
# +--------------------------------------------------------------------------------------------------------
# | from ukko_pylibs.appTemplates.jsonLineStreaming import jsonLineStreamingApp_doRun, IJsonLineStreamerSpec
# |
# | def main():
# |     #| Stream data via TCP in JSON format, one JSON object per line.
# |     #| This is a simple format that can be easily consumed by many tools
# |     #| (e.g. 'jq' on the command line, or Python's json library, etc)
# |     #|
# |     class DataMonitor_Multicomp(IJsonLineStreamerSpec):
# |         DATA_KIND="Multicomp"
# |         DEFAULT_STREAMING_PORT=12306    # < Must be greater than 1024 to avoid requiring 'sudo'
# |
# |         ADDITIONAL_APP_PARAMETERS={"serialPort": {"default": "_auto_"}}
# |
# |         @staticmethod
# |         def getCollectionObject(params:dict[str,Any]):
# |             from equipmentAccess.powerSupplies import PowerSupply_MulticompMP710083
# |             return PowerSupply_MulticompMP710083(params['serialPort'], params.get('isVerbose', False))
# |
# |         @staticmethod
# |         def doCollectSample(collectionObject,includeEmptyValues: bool)->Tuple[str, dict[str,Any]]:
# |             return ('piuPower', collectionObject.power_getAllStatuses(removeEmptyValues=not includeEmptyValues))
# |
# |     jsonLineStreamingApp_doRun(DataMonitor_Multicomp())
# +--------------------------------------------------------------------------------------------------------


import time
import os
import sys
from datetime import datetime


from typing import Any, Tuple

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic import simpleUtils
import ukko_pylibs.basic.appSupport as app
from ukko_pylibs.network.basicTcpServer import BasicTcpServer
from ukko_pylibs.basic.appSupport import appLog
from ukko_pylibs.basic.simpleUtils import Utils

#
################################################################################


class IJsonLineStreamerSpec:
    DATA_KIND = "???"  # < Override in subclass
    DEFAULT_STREAMING_PORT = 12301  # < Override in subclass
    APP_VERSION = "0.0.1"
    APP_AUTHOR: str = ""
    ADDITIONAL_APP_PARAMETERS: dict[str, Any] | list[dict[str, Any]] | None = None

    @staticmethod
    def getCollectionObject(params: dict[str, Any]) -> Any:
        return (
            dict()
        )  # < This is optional - some implementations may not need a persistent object

    @staticmethod
    def doCollectSample(
        collectionObject, includeEmptyValues: bool
    ) -> Tuple[str, dict[str, Any]]:
        raise NotImplementedError("Override in subclass")


##################################################
#
# Everything else here is internal
#

#########################################################################
#
# Add 'common' path
#
#
common_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../common")
if common_dir not in sys.path:
    sys.path.append(common_dir)

################################################################################
#
# Add ukko libraries
#
ukko_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../common/ukko_libs")
if ukko_dir not in sys.path:
    sys.path.append(ukko_dir)

import ukko_pylibs.basic.appSupport as app

#
################################################################################


def jsonLineStreamingApp_doRun(spec: IJsonLineStreamerSpec):
    try:

        def parseAppDefinition(kind: str, defaultPort: int) -> dict[str, Any]:
            app_definition = {
                "version": spec.APP_VERSION,
                "description": f"{kind} Monitor Streamer",
                "options": [
                    {
                        "name": "tcpPort",
                        "default": defaultPort,  # Port to listen on (non-privileged ports are > 1023)
                    },
                    {
                        "name": "interval_ms",
                        "default": 1000,  # Interval in milliseconds between data points
                    },
                    {"name": "include-empty-values"},
                    {"name": "include-iso-date"},
                ],
            }

            if spec.APP_AUTHOR.strip():
                app_definition["author"] = spec.APP_AUTHOR.strip()

            appending_list: list[dict[str, Any]] = []
            if isinstance(spec.ADDITIONAL_APP_PARAMETERS, list):
                appending_list = spec.ADDITIONAL_APP_PARAMETERS
            elif isinstance(spec.ADDITIONAL_APP_PARAMETERS, dict):
                for paramName, paramInfo in spec.ADDITIONAL_APP_PARAMETERS.items():
                    obj = {"name": paramName}
                    obj.update(paramInfo)
                    appending_list.append(obj)
            elif spec.ADDITIONAL_APP_PARAMETERS is not None:
                raise ValueError("ADDITIONAL_APP_PARAMETERS must be a list or dict")

            for obj in appending_list:
                app_definition["options"].append(obj)

            return app.Define(app_definition).parseParams(sys.argv[1:])

        params = parseAppDefinition(spec.DATA_KIND, spec.DEFAULT_STREAMING_PORT)

        dataStreamer = BasicTcpServer(
            f"MonitorStreamingServer[{spec.DATA_KIND}]", params["tcpPort"]
        )

        option_includeIsoDate: bool = params["include-iso-date"]
        option_includeEmptyValues: bool = params["include-empty-values"]
        option_interval_seconds: float = params["interval_ms"] / 1000.0
        option_tcpPort: int = params["tcpPort"]

        while app.isRunning():
            print(f"📡  Ready to stream {spec.DATA_KIND} via TCP port {option_tcpPort}")
            print(
                "    Hints:\n"
                f"     • Type 'nc localhost {option_tcpPort}'  in another window to make a connection\n"
            )

            print(
                f"📡  Waiting for TCP connection to {' -or- '.join(dataStreamer.connectionAddresses(withSuffix=True))}",
                flush=True,
            )

            while not dataStreamer.hasConnections():
                time.sleep(1)

            print(
                f"📡  Connection made - Begin Collection & broadcast  (Every {option_interval_seconds} sec) -- {'Including empty values' if option_includeEmptyValues else 'Excluding empty values'}",
                flush=True,
            )

            with spec.getCollectionObject(params) as collectionObject:

                sample_epoch = time.time()
                runIndex = 0
                while dataStreamer.hasConnections():
                    dataStreamer.sendToNewConnections(
                        f"# Generated by: {app.appInfo_get('runBasics')}"
                    )
                    now_seconds = time.time()

                    full_wait_seconds = sample_epoch - now_seconds
                    if full_wait_seconds > 1:
                        time.sleep(
                            1
                        )  # Sleep in shorter intervals to be responsive to disconnections
                        continue

                    if full_wait_seconds > 0:
                        time.sleep(full_wait_seconds)
                        now_seconds = time.time()

                    sample_epoch += option_interval_seconds  # Schedule next sample time
                    if sample_epoch < time.time():
                        sample_epoch = (
                            int(
                                (time.time() + option_interval_seconds)
                                / option_interval_seconds
                            )
                            * option_interval_seconds
                        )  # Skip missed intervals if we're behind schedule

                    ####################################################################################
                    # Now ready to take a new sample
                    #

                    timestamp_obj: dict[str, Any] = {"epoch [sec]": now_seconds}
                    if option_includeIsoDate:
                        timestamp_obj["ISO"] = (
                            f"{str(datetime.fromtimestamp(now_seconds)).removesuffix('Z')}Z"
                        )

                    data: dict[str, Any] = {
                        "Timestamp": timestamp_obj,
                        "runIndex": runIndex,
                    }
                    runIndex += 1

                    name, obj = spec.doCollectSample(
                        collectionObject, option_includeEmptyValues
                    )

                    data[name] = (
                        obj  # @todo: Make smarter and overwrite timestamps if needed
                    )

                    appLog.print_verbose(
                        f"Reviewed data: {Utils.asJsonStr(data,indent=2)}"
                    )
                    sentCount = dataStreamer.doBroadcast(Utils.asJsonStr(data))

                    if sentCount > 0:
                        appLog.print_info(
                            f"Sent to {simpleUtils.pluralize(sentCount, 'connection')}"
                        )
                    else:
                        appLog.print_warning("Not sent to any connections")

                appLog.print_warning(
                    f"No more connections - ending {spec.DATA_KIND} Monitoring"
                )

            print(f"📡  End collection & broadcasting")

        app.doHalt("App finished normally")
    except BaseException as e:
        app.exitOnException(e)
