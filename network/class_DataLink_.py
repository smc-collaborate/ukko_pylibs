import sys
from typing import Any
import os

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import Utils as Utils
from ukko_pylibs.transferableData.class_ITransferableData import ITransferableData
from ukko_pylibs.network.class_IPhyConnection import IPhyConnection

#
################################################################################


class DataLink[dataType]:
    """The Phylayer can't be extracted totally because how it is used really depends on what type of data it is.
    Some datatypes support streaming, others are just a fixed header+payload."""

    def __init__(self, phyConnection: IPhyConnection):
        _dataTypeToUse = ITransferableData.getClassIfUsable(
            dataType  # pyright: ignore[reportArgumentType]
        )
        if _dataTypeToUse is None:
            raise Exception(f"DataLink[{dataType}]: Invalid data type: {dataType}")
        self.dataType = _dataTypeToUse
        self.phyConnection = phyConnection

    def __str__(self):
        return f"{self.dataType.__name__}.{self.phyConnection}"

    def PhyLayer_sendAllBytes_orException(self, packedBytes: bytes) -> None:
        self.phyConnection.sendAllBytes_orException(packedBytes)

    def sendToStream(
        self,
        dataToSend: ITransferableData,
        isVerbose: bool = False,
    ) -> bool:

        packedBytes = dataToSend.toBytes(withStreamWrapping=True)
        if packedBytes is None:
            return False

        if isVerbose:
            sys.stderr.write(f"ℹ️  [out]={dataToSend}\n")
        try:
            self.phyConnection.sendAllBytes_orException(packedBytes)
            return True
        except Exception as e:
            sys.stderr.write(f"❌  Unable to send data to {self.phyConnection}: {e}\n")
            return False

    def readDataObjectFromStream(
        self, timeout_ms: int | None = None
    ) -> ITransferableData | bool:
        return self.dataType.create_readFromStream(
            self.phyConnection, timeout_ms=timeout_ms
        )

    def sendError(
        self,
        msgKind: str,
        errCode: str,
        errMsg: str,
        extras: dict[str, Any] | None = None,
    ) -> bool:
        obj: ITransferableData = self.dataType.create_error(
            msgKind, errCode, errMsg, extras
        )
        sys.stderr.write(
            f"⚠️ Responding with error[{errCode}]: {Utils.asJsonStr(obj.dict_annotations)}\n"
        )
        return self.sendToStream(obj)

    def createAndSend(
        self,
        msgKind: str,
        dict_annotations: dict[str, Any],
        bitstream_data: bytes | None = None,
        isVerbose: bool = False,
    ) -> bool:

        try:
            dataToSend = self.dataType.create_fromKindWithDict(
                msgKind, dict_annotations, bitstream_data
            )
            return self.sendToStream(dataToSend, isVerbose)
        except Exception as e:
            sys.stderr.write(f"❌  Error creating or sending data: {e}\n")
            return False
