import copy
import io
import sys
import json
from typing import Any, Tuple, Union
import os

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import Utils as Utils
from ukko_pylibs.basic.simpleUtils import DictUtils as DictUtils
import ukko_pylibs.basic.simpleUtils as simpleUtils
from ukko_pylibs.basic.class_HandledException import (
    HandledException as HandledException,
)
import ukko_pylibs.basic.appSupport as app
from ukko_pylibs.basic.appSupport import appLog

#
################################################################################


def _noteValue(
    jsonDict: dict[str, Any], key: str, value: Any, prevNotes: list[Tuple[str, Any]]
) -> None:
    if jsonDict.get(key, None) == value:
        return
    if key in jsonDict:
        prevNotes.append((key, jsonDict[key]))

    if value is not None:
        jsonDict[key] = value
    elif key in jsonDict:
        del jsonDict[key]


class ITransferableData:
    """Abstract class for TransferableData  (eg: AnnotatedData  etc)
    These need to be implemented by subclasses:
     * def toBytes(self, withStreamWrapping: bool = True) -> bytes | None:
     * def export_orHandledException(self,filename_in: str, exportFormat: str | None = None)->Tuple[str, str | None]:  #< Look for an invalid marker for failure
     * def create_fromKindWithDict(msgKind:str, json_dict:dict[str, Any], bitstream_data: bytes | None = None) -> ITransferableData:
     * def create_readFromStream(cls,connection, timeout_ms: int | None)->Union["ITransferableData",bool]:
     * def create_fromBytes(cls,data:bytes, extraNoteOnError: str = "", sourceNote: str | None = None)->"ITransferableData":  #< Look for an invalid marker for failure
    """

    def dumpToStdOut_jsonPlus(self):
        self.export_orHandledException("-", "json:files+")

    def export_orHandledException(
        self, filename_in: str, exportFormat: str | None = None
    ) -> Tuple[str, str | None]:
        """Exports the annotatedData to a file in the specified format, or raises a HandledException on failure
        Returns: (filename_used, json_out) where:
            - filename_used: The actual filename used for export (which may differ from filename_in if the format requires a different extension)
            - json_out: The JSON string output if the export format is a JSON format, otherwise None
        """
        raise NotImplementedError(
            f"{self.className()}.export_orHandledException: Should be implemented by subclasses"
        )

    def exportToMultipleFormats_orHandledException(self) -> None:
        filename_forced = (
            "file"
            if (self.sourceNote is None)
            or (self.sourceNote == "-")
            or (self.sourceNote.startswith("/dev/"))
            else ""
        )

        # |Extras| self.export_orHandledException(filename_forced,'json:base64+')
        self.export_orHandledException(filename_forced, "json:summary")
        dest, json_txt = self.export_orHandledException(filename_forced, "json:files+")
        if (dest != "/dev/stdout") and (json_txt is not None):
            sys.stdout.write(json_txt)

    def __init__(
        self, dict_or_str: dict[str, Any] | str, bitstream_data: bytes | None = None
    ):
        self.bitstream_data = bitstream_data
        self.invalidReason: str | None = None
        self.dict_annotations: dict[str, Any] = {}
        if isinstance(dict_or_str, str):
            try:
                self.dict_annotations: dict[str, Any] = json.loads(dict_or_str)
            except Exception:
                self.invalidReason = f"Invalid JSON annotations `{dict_or_str}`"
        elif isinstance(dict_or_str, dict):
            self.dict_annotations: dict[str, Any] = dict_or_str
        else:
            appLog.print_error(
                f"Invalid annotations type: {type(dict_or_str)} - must be a dict"
            )
        if bitstream_data is not None and not isinstance(bitstream_data, bytes):
            appLog.print_error(
                f"Invalid bitstream_data type: {type(bitstream_data)} - must be bytes"
            )
            bitstream_data = None
        self.bitstream_data = bitstream_data
        self.sourceNote: str | None = None

    def toBytes(self, withStreamWrapping: bool = True) -> bytes | None:
        raise NotImplementedError(
            f"{self.className()}.toBytes: Should be implemented by subclasses"
        )

    @classmethod
    def create_fromKindWithDict(
        cls,
        msgKind: str,
        json_dict: dict[str, Any],
        bitstream_data: bytes | None = None,
    ) -> "ITransferableData":
        raise NotImplementedError(
            f"{cls.__name__}.create_fromKindWithDict: Should be implemented by subclasses"
        )

    @classmethod
    def create_readFromStream(
        cls, connection, timeout_ms: int | None
    ) -> Union["ITransferableData", bool]:
        """Read ITransferableData from a socket or serial connection
        Returns: (ITransferableData) or 'isStillConnected'=true/false"""
        from libs_network.class_IPhyConnection import (  # pyright: ignore[reportMissingImports]
            IPhyConnection,
        )

        if not (isinstance(connection, IPhyConnection)):
            return False

        raise NotImplementedError(
            f"{cls.__name__}.create_readFromStream: Should be implemented by subclasses"
        )

    @classmethod
    def create_fromBytes(
        cls, data: bytes, extraNoteOnError: str = "", sourceNote: str | None = None
    ) -> "ITransferableData":
        """Read ITransferableData from a socket or serial connection
        Returns: (ITransferableData) or 'isStillConnected'=true/false"""
        raise NotImplementedError(
            f"{cls.__name__}.create_fromBytes: Should be implemented by subclasses"
        )

    #######################################################
    #
    # Create classmethods for common cases (invalid, error) that can be used by subclasses
    #
    @classmethod
    def create_invalid(
        cls, errMsg: str, withPrint: bool = True, sourceNote: str | None = None
    ):
        return cls.create_invalidKind("invalid", errMsg, withPrint, sourceNote)

    @classmethod
    def create_invalidKind(
        cls,
        kind: str,
        errMsg: str,
        withPrint: bool = True,
        sourceNote: str | None = None,
    ) -> "ITransferableData":
        result = cls.create_fromKindWithDict(kind, {})
        result.sourceNote = sourceNote
        if withPrint:
            appLog.print_error(errMsg)
        result.invalidReason = errMsg
        return result

    @classmethod
    def create_error(
        cls,
        msgKind: str,
        errCode: str,
        errMsg: str,
        extras: dict[str, Any] | None = None,
    ) -> "ITransferableData":
        json_dict = {} if extras is None else dict(extras)
        if app.getValue("includeErrorCodesInResponses", True) and (errCode != ""):
            json_dict["errCode"] = errCode
            prefix = f"[{errCode}]"
        else:
            prefix = ""
        json_dict["error"] = errMsg

        sys.stderr.write(f"⚠️ Creating error{prefix}: {Utils.asJsonStr(json_dict)}\n")
        return cls.create_fromKindWithDict(msgKind, json_dict)

    def className(self):
        return self.__class__.__name__

    def getAnnotation(
        self, keys: str | list[str], defaultIfNotFound: Any = None
    ) -> Any | None:
        try:
            iterateList = keys.split("/") if isinstance(keys, str) else keys

            obj = self.dict_annotations
            for k in iterateList:
                if k != "":  # < Skip empty keys (eg from leading/trailing slashes)
                    if isinstance(obj, dict) and (k in obj):
                        obj = obj[k]
                    elif isinstance(obj, list):
                        obj = obj[int(k)]
                    else:
                        return defaultIfNotFound

            return obj

        except Exception:
            return defaultIfNotFound

    def getErrorTextIfAny(self) -> str | None:
        if self.isInvalid():
            return f"[Invalid]: {self.invalidReason}"

        errDetails_dict = copy.deepcopy(self.dict_annotations)
        while isinstance(errDetails_dict, dict):
            err_msg = errDetails_dict.pop("error", None)
            err_code = errDetails_dict.pop("errCode", None)

            if (err_msg is None) and (err_code is None):
                errDetails_dict = errDetails_dict.get("response", None)
            else:
                errTxt = ""
                if err_code is not None:
                    errTxt += f"[{err_code}]"

                if err_msg is not None:
                    if err_code is not None:
                        errTxt += ": "
                    errTxt += f"{err_msg}"

                if len(errDetails_dict) > 0:
                    errTxt += f" | Details: {Utils.asJsonStr(errDetails_dict)}"
                return errTxt
        return None

    def hasBitstreamData(self, includeEmpty: bool = False) -> bool:
        return (self.bitstream_data is not None) and (
            (len(self.bitstream_data) > 0) or includeEmpty
        )

    def appendWarnings(self, warningsList: list | None) -> None:
        if warningsList is not None and len(warningsList) > 0:
            DictUtils.extend(self.dict_annotations, {"warnings": warningsList})

    def appendErrors(self, errorsList: list | None) -> None:
        if errorsList is not None and len(errorsList) > 0:
            DictUtils.extend(self.dict_annotations, {"errors": errorsList})

    def appendAnnotations(self, extraValues: dict[str, Any] | None) -> None:
        DictUtils.extend(self.dict_annotations, extraValues)

    def changeAnnotation(
        self, key: str, newValueOrNone: Any = None
    ) -> Tuple[bool, str]:
        logMsg = ""
        hasChanged = False
        if newValueOrNone is None:
            if key in self.dict_annotations:
                logMsg = (
                    f"Remove annotation: {key}  (Was: {self.dict_annotations[key]})"
                )
                del self.dict_annotations[key]
                hasChanged = True
            else:
                logMsg = f"Confirmed annotation removed: {key}"
        else:
            if self.getAnnotation(key) == newValueOrNone:
                logMsg = f"Confirmed annotation: {key}={newValueOrNone}"
            else:
                logMsg = f"Set annotation: {key}={newValueOrNone}"
                self.dict_annotations[key] = newValueOrNone
                hasChanged = True

        return hasChanged, logMsg

    def changeAnnotations(self, changes: dict[str, Any]) -> bool:
        overallChanged = False
        for key, newValueOrNone in changes.items():
            hasChanged, logMsg = self.changeAnnotation(key, newValueOrNone)
            if hasChanged:
                appLog.print_verbose(f"Change: {logMsg}")
                overallChanged = True
            else:
                appLog.print_verbose(f"No change: {logMsg}")
        return overallChanged

    def isInvalid(self) -> bool:
        return (self.invalidReason is not None) and (self.invalidReason != "")

    def isValid(self) -> bool:
        return not self.isInvalid()

    def getInvalidReason(self) -> str | None:
        if self.isInvalid():
            return str(self.invalidReason)
        else:
            return None

    def getAttrOrNone(self, attrName: str) -> Any | None:
        return getattr(self, attrName, None)

    def getJsonWithExtras(self) -> dict[str, Any]:

        json_dict = (
            self.dict_annotations.copy()
        )  # Create a copy to avoid modifying the original
        prev = []
        if self.isInvalid():
            _noteValue(json_dict, "invalidReason", self.invalidReason, prev)
        timestamp_or_zero = self.getAttrOrNone("timestamp_utc_ns")
        if timestamp_or_zero is not None and timestamp_or_zero > 0:
            _noteValue(
                json_dict,
                "timestamp",
                simpleUtils.timestampObj_from_ns(timestamp_or_zero),
                prev,
            )

        if len(prev) > 0:
            json_dict["__modified_previous"] = prev

        return json_dict

    @staticmethod
    def getClassIfUsable(dataType: type) -> Union["type[ITransferableData]", None]:
        try:
            if (dataType is not None) and issubclass(dataType, ITransferableData):
                return dataType
        except Exception as e:
            pass
        appLog.print_warning(
            f"Expected  {dataType} to be a subclass of ITransferableData - it is not usable"
        )
        return None

    def imageGetFormat(
        self, withSizeEtc: bool = False, withRawPrefix: bool = False
    ) -> str | None:
        imgData = self.getAnnotation(["imageData"], None)
        if (imgData is None) or not (isinstance(imgData, dict)):
            return None
        img_format__ = imgData.get("format", None)
        if (img_format__ is None) or not (isinstance(img_format__, str)):
            return None

        img_format = img_format__.lower()

        stdFormatOrNone = simpleUtils.asStandardImageFormatOrNone(img_format)
        if stdFormatOrNone is not None:
            return stdFormatOrNone

        img_width = imgData.get("width", None)
        img_height = imgData.get("height", None)
        if (img_width is None) or not (isinstance(img_width, int)) or (img_width <= 0):
            return None
        if (
            (img_height is None)
            or not (isinstance(img_height, int))
            or (img_height <= 0)
        ):
            return None

        if withSizeEtc:
            from ukko_pylibs.imageProcessing.rawimgProcess import RawImg

            img_format += f"_{img_width}x{img_height}"
            if imgData.get("offset", 0) != 0:
                img_format += f"+{imgData.get('offset', 0)}"

            img_format += RawImg.conversionEntry_asTextSuffix(
                imgData.get("conversion", None)
            )
            if withRawPrefix:
                img_format = "raw_" + img_format
        return img_format

    def isImage(self) -> bool:
        return self.imageGetFormat() is not None

    def toPng(self) -> bytes | None:

        if self.bitstream_data is None:
            return None

        if not self.isImage():
            return None

        if self.imageGetFormat() == "png":
            return self.bitstream_data
        else:
            streamOut = io.BytesIO()
            self.toRawImg().exportAsPng(streamOut)
            return streamOut.getvalue()

    def _toImgUncached_orHandledException(self) -> Any:  #    -> RawImg:
        try:
            import png
            from ukko_pylibs.imageProcessing.class_PixelFormatData import PIXEL_FORMATS
            from ukko_pylibs.imageProcessing.rawimgProcess import RawImg

            pixelFormat = self.imageGetFormat()
            if pixelFormat is None:
                raise HandledException(
                    f"Cannot create RawImg from non-image AnnotatedData: {self}"
                )

            if pixelFormat.lower() == "png":
                try:
                    reader = png.Reader(bytes=self.bitstream_data)
                    return RawImg.create_fromPngReader(
                        reader, PIXEL_FORMATS[pixelFormat], src=None
                    )

                except BaseException as e:
                    raise HandledException(
                        f"Reading from Png Image in AnnotatedData: {e}"
                    )
            else:
                formatInfo = PIXEL_FORMATS.get(pixelFormat.lower(), None)
                if formatInfo is None:
                    raise HandledException(
                        f"Invalid image format:{pixelFormat} - must be one of [{','.join(PIXEL_FORMATS.keys())}]"
                    )
                binData = self.bitstream_data
                if (binData is None) or (len(binData) == 0):
                    raise HandledException(
                        f"Cannot create RawImg from AnnotatedData with no binary data: {self}"
                    )
                width = self.getAnnotation(["imageData", "width"])
                height = self.getAnnotation(["imageData", "height"])
                offset = self.getAnnotation(["imageData", "offset"], 0)

                rawImg = RawImg(width, height, formatInfo)
                if isinstance(offset, int):
                    rawImg.skipRawBytes = offset
                rawImg.formattingExtras = self.getAnnotation("imageData", {})
                rawImg.loadImageData_fromRawStream(io.BytesIO(binData))
                return rawImg
        except BaseException as e:
            raise HandledException(f"create_fromAnnotatedData(): {e}")

    def toRawImg(self) -> Any:
        if hasattr(self, "internalImage_cached"):
            cached = self.internalImage_cached
            if cached is not None:
                appLog.print_info("Using cached InternalImage: Time Saved")
                return cached

        appLog.print_info("Generating & caching InternalImage")
        self.internalImage_cached = self._toImgUncached_orHandledException()

        return self.internalImage_cached

    def bitstreamData_getInfo(
        self, formatIfUnknown: str | None = "Unknown"
    ) -> dict[str, Any]:
        """
        Returns the format of the bitstream data
        Expand this with new (common) formats
          ['numBytes', 'md5', 'included','format', 'isImage', 'image.format','isStandardFormat','ext']
        """
        result = {}
        if self.bitstream_data is None:
            return result

        result["included"] = True
        result["numBytes"] = len(self.bitstream_data)
        result["ext"] = DictUtils.get(
            self.getAttrOrNone("customFormatDefinition"),
            "suggested_file_ext_raw",
            ".raw",
        )
        imageFormat = self.imageGetFormat(withSizeEtc=True, withRawPrefix=True)
        result["isStandardFormat"] = False
        if imageFormat is None:
            result["format"] = formatIfUnknown
        else:
            result["format"] = "image/" + imageFormat
            result["image.format"] = imageFormat.removeprefix("raw_")
            result["isImage"] = True
            asStandardImageFormat = simpleUtils.asStandardImageFormatOrNone(imageFormat)
            if asStandardImageFormat is not None:
                result["isStandardFormat"] = True
                result["ext"] = f".{asStandardImageFormat}"
            elif result["ext"] == ".raw" and imageFormat.startswith("raw_"):
                result["ext"] = f".{imageFormat}"
        return result
