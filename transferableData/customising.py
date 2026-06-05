import io
import struct
import os, sys

import traceback
from typing import Any, Tuple
import parse

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
import ukko_pylibs.basic.fileUtils as fileUtils
from ukko_pylibs.imageProcessing.class_PixelFormatData import PIXEL_FORMATS


#
################################################################################


CUSTOM_FORMAT_SUFFIXES_TO_IGNORE = [
    "/reply",
    "/request",
    "/stream/start",
    "/stream/stop",
    "/stream",
    "/image",
]  # Suffixes for custom formats that should not trigger a warning if no specific format definition is found (e.g. because they are more generic formats that are handled in a more flexible way)

CUSTOM_FORMAT_SUFFIXES_TO_IGNORE = [
    "/reply",
    "/request",
    "/stream/start",
    "/stream/stop",
    "/stream",
    "/image",
]  # Suffixes for custom formats that should not trigger a warning if no specific format definition is found (e.g. because they are more generic formats that are handled in a more flexible way)


class CustomisedContents:

    def __init__(self, name: str, headerFormat: "DataHeaderFormat", rawData: bytes):
        self.headerFormat = headerFormat
        # self.totalMinSizeBeforeReview_bytes:int|None=headerFormat.getTotalMinSizeBeforeReview_bytes()
        self.name = name
        self.headerFormatText = ""

        self.attributes = {}  # attributes

        self._warnings = {}
        self._errors = {}

        if rawData is not None:
            self._parseAttributesFromRawData(rawData)

    def _parseAttributesFromRawData(self, rawData: bytes) -> bool:
        """No validation of prefix - caller must ensure that the rawData is valid for this header format."""

        self.headerFormatText = self.headerFormat.name()

        self.attributes: dict[str, Any] = {}

        values = self.headerFormat.loadHeaderFromBytes(rawData)
        if isinstance(values, str):
            appLog.print_warning(
                f"Loading header from raw data[{rawData[:32].hex()}]...->⚠️  {Utils.asJsonStr(values,indent=2)}"
            )
            self.addError(values)
        else:
            self.attributes.update(values)

            self.doValidate()

        return self.isValid()

    def getAttribute(self, attrName: str, defaultValueOrNone: Any = None) -> Any:
        result = DictUtils.get(self.attributes, attrName, defaultValueOrNone)
        if result is None:
            appLog.print_warning(f"Missing attribute '{attrName}' in {self.name}")
        return result

    def getAttribute_int(self, attrName: str, defaultValue: int) -> int:
        return DictUtils.getInt(self.attributes, attrName, defaultValue)

    def getAttribute_intOrNone(self, attrName: str) -> int | None:
        return DictUtils.getIntOrNone(self.attributes, attrName)

    def getAttribute_str(self, attrName: str, defaultValue: str) -> str:
        return DictUtils.getStr(self.attributes, attrName, defaultValue)

    ################################
    #
    # Helpers for common attributes
    #
    #  • annotations/imageData/format
    #  • annotations/imageData/width
    #  • annotations/imageData/height
    #  • annotations/imageData/offset
    #  • .payloadSize_bytes
    #  • .header.extraHex
    #  • .rawFormat.headerKind

    def getAnnotationImage_pixelFormat(self) -> str:
        return self.getAttribute_str("annotations/imageData/format", "")

    def getAnnotationImage_width(self) -> int:
        return self.getAttribute_int("annotations/imageData/width", 0)

    def getAnnotationImage_height(self) -> int:
        return self.getAttribute_int("annotations/imageData/height", 0)

    def getAnnotationImage_offset(self) -> int:
        return self.getAttribute_int("annotations/imageData/offset", 0)

    def getAttr_imageSize_bytesOrNone(self) -> int | None:
        return self.getAttribute_intOrNone(".payloadSize_bytes")

    def getAttr_frameNum(self) -> int | None:
        return self.getAttribute_intOrNone("frameNum")

    def getAttr_timestamp_ns(self) -> int:
        return self.getAttribute_int(
            "timeStamp_ns", self.getAttribute_int("timeStamp_us", 0) * 1000
        )

    def asImageData(self) -> dict[str, Any]:
        return self.getAttribute("annotations/imageData", {})

    def getFullSize_bytes(self) -> int | None:
        n1 = self.getAttribute_intOrNone(".payloadSize_bytes")
        n2 = self.getAttribute_intOrNone(".prePayloadSize_bytes")

        if (n1 is None) or (n2 is None):
            return None
        else:
            return n1 + n2 + self.getAttribute_int(".postPayloadSize_bytes", 0)

    def expectImageData(self) -> bool:
        return self.headerFormat.expectImageData()

    #############
    # Errors
    def errors(self) -> list[str]:
        return list(self._errors.keys())

    def errorMsgs(self, separator: str = "\n") -> str:
        return separator.join(self.errors())

    def hasErrors(self) -> bool:
        return len(self._errors) > 0

    def addError(self, text: str) -> "CustomisedContents":
        self._errors[text] = self._errors.get(text, 0) + 1
        return self

    def isValid(self) -> bool:
        return not self.hasErrors()

    #############
    # Warnings
    def warnings(self) -> list[str]:
        return list(self._warnings.keys())

    def warningMsgs(self) -> str:
        return "\n".join(self.warnings())

    def hasWarning(self) -> bool:
        return len(self._warnings) > 0

    def addWarning(self, text: str):
        self._warnings[text] = self._warnings.get(text, 0) + 1

    ###########
    #
    def getExpectedImageSize(self) -> int | None:

        if self.getAnnotationImage_pixelFormat() == "mono8":
            return self.getAnnotationImage_width() * self.getAnnotationImage_height()
        elif self.getAnnotationImage_pixelFormat() == "mono16":
            return (
                self.getAnnotationImage_width() * self.getAnnotationImage_height() * 2
            )
        else:
            return None

    def doValidate(self) -> bool:

        if self.hasErrors():
            appLog.print_warning(
                f"Validating {self.name}({self.headerFormatText}): Errors Found: {self.errorMsgs()}"
            )
        else:
            appLog.print_verbose(f"Validating {self.name}({self.headerFormatText})")

            if self.expectImageData():
                _imageSize_bytesOrNone = self.getAttr_imageSize_bytesOrNone()
                if (
                    self.getAnnotationImage_width() < 1
                    or self.getAnnotationImage_width() > 8192
                    or self.getAnnotationImage_height() < 1
                    or self.getAnnotationImage_height() > 5460
                ):
                    self.addError(
                        f"Invalid image dimensions: {self.getAnnotationImage_width()}x{self.getAnnotationImage_height()} - must be between 1x1 and 8192x5460 pixels"
                    )
                elif not self.getAnnotationImage_pixelFormat() in PIXEL_FORMATS.keys():
                    self.addError(
                        f"Invalid pixel format: {self.getAnnotationImage_pixelFormat()} - must be in {PIXEL_FORMATS.keys()}"
                    )
                elif (
                    _imageSize_bytesOrNone is not None
                ) and _imageSize_bytesOrNone < 3:
                    self.addError(
                        f"Invalid image size: {_imageSize_bytesOrNone} bytes - must be at least 3 bytes long"
                    )
                else:
                    if (_imageSize_bytesOrNone is not None) and (
                        _imageSize_bytesOrNone != self.getExpectedImageSize()
                    ):
                        self.addWarning(
                            f"Image size mismatch: {_imageSize_bytesOrNone} != {self.getExpectedImageSize()} bytes"
                        )

        if not self.hasErrors():
            # |Logging| appLog.print_info(f"{self.name}: {self}")
            return True
        else:
            appLog.print_error(f"{self.name}: {self.errorMsgs(' | ')}")
            return False

    def __str__(self):
        if not self.hasErrors():
            return f"{self.name}({self.headerFormatText})=\n{Utils.asJsonStr(self.attributes)}"
        else:
            return f"{self.name}({self.headerFormatText})=⚠️ {self.errorMsgs(' | ')} ⚠️ {Utils.asJsonStr(self.attributes)}"


def CustomisedContents_CreateFromHeaderFormat(
    name: str, headerFormat: "DataHeaderFormat", rawData: bytes
) -> CustomisedContents | None:
    """
    Create a CustomisedContents instance from a header format and raw data.
    """

    if headerFormat.headerPrefixMatches(rawData):
        return CustomisedContents(name, headerFormat, rawData)
    else:
        return None


class DataHeaderFormat:

    def __init__(
        self, headerInfo: dict[str, Any], overallFormatDefinition: dict[str, Any]
    ):
        self.HEADER_INFO = headerInfo
        self.overallFormatDefinition = overallFormatDefinition
        self.setup()

    def setup(self):
        pass
        # Override this method to set up any additional properties or configurations needed for the header format
        # self.HEADER_DATA_LOAD_FORMAT=""

    def headerPrefixMatches(self, headerBytes: bytes | None) -> bool:
        if headerBytes is None:
            return False

        headerPrefixHex = self.HEADER_INFO.get("PREFIX_HEX", "")

        numBytes = len(headerPrefixHex) // 2

        prefixBytesHex = headerBytes[:numBytes].hex()

        appLog.print_verbose(
            f"Checking data header prefix(0x{headerPrefixHex}) against {self.name()}: 0x{prefixBytesHex}"
        )

        return headerPrefixHex == prefixBytesHex

    def getTotalMinSizeBeforeReview_bytes(self) -> int | None:
        return self.overallFormatDefinition.get("minTotalSize_bytes", None)

    def expectImageData(self) -> bool:
        includes = self.overallFormatDefinition.get("includes", {})
        if isinstance(includes, dict) and includes.get("image", False):
            return True
        if self.overallFormatDefinition.get("kind", "").endswith("/image"):
            appLog.print_warning(
                "Assuming image data based on kind ending with '/image' - but 'image' is not listed in 'includes'"
            )
            return True

        return False

    def fromHeaderTuple(self, dest: CustomisedContents, tuple_data):
        pass

    def toHeaderBytes(self, src: CustomisedContents) -> bytes:
        return b""

    def name(self) -> str:
        return self.HEADER_INFO.get("PREFIX.asText", "<unnamed>")

    def loadConversionFromBytes(
        self, definition: list[dict[str, Any]], rawDataStream: io.BytesIO
    ) -> dict[str, Any]:
        """Returns: {'value':..., 'isEmpty':...} | {'errmsg':...}"""
        pos: int = rawDataStream.tell()

        funcResult: dict[str, Any] = {"value": {}, "isEmpty": True}
        defLookup: dict[str, Any] = self.HEADER_INFO

        for conversionEntry in definition:
            try:
                pos = rawDataStream.tell()
                code = conversionEntry.get("code", "?")

                entry_attr = conversionEntry.get("attr", "?")
                entry_skip = False
                entry_printSuffix = code
                entry_value = None
                entry_numBytes = 0
                entry_bytes = b""
                entry_isEmpty: bool | None = None  # None means 'do from entry_numBytes'
                if code == "verifyHex":
                    # Verify a constant value
                    entry_value = conversionEntry.get("value", "")
                    if entry_value is None:
                        return {
                            "errmsg": f"Missing 'value' for 'verifyHex' code in {entry_attr}"
                        }
                    entry_value = bytes.fromhex(entry_value)
                    entry_numBytes = len(entry_value)
                    entry_bytes = rawDataStream.read(entry_numBytes)
                    entry_value = entry_bytes.hex()
                    # entry_printSuffix='verifyHex'
                elif code == "=":
                    # Load a constant
                    entry_numBytes = 0
                    entry_bytes = b""
                    entry_value = conversionEntry.get("value", False)
                    entry_printSuffix = "FIXED"
                elif code == "zeroPadding":
                    # Load Bytes (expect zero)
                    entry_numBytes = conversionEntry.get("numBytes", 1)
                    entry_bytes = rawDataStream.read(entry_numBytes)
                    entry_value = entry_bytes.hex()
                    while entry_value.endswith("00"):
                        entry_value = entry_value.removesuffix("00")
                    if entry_value == "":
                        entry_skip = True
                elif (code + "[").startswith("text["):
                    entry_numBytes = conversionEntry.get("numBytes", 1)
                    entry_bytes = rawDataStream.read(entry_numBytes)
                    entry_value = entry_bytes.decode("utf-8", errors="replace")
                    if code == "text[format]":
                        extractFormat = str(conversionEntry.get("extractFormat", ""))

                        result = parse.parse(
                            extractFormat, str(entry_value)
                        )  # .format(**theDict)
                        if (
                            (result is None)
                            or not isinstance(result, parse.Result)
                            or (not result.named)
                        ):
                            DictUtils.set(
                                funcResult["value"],
                                entry_attr + ".error",
                                {
                                    "msg": "Unable to extract data",
                                    "extractionFormat": extractFormat,
                                    "textIn": entry_value,
                                    "result": result,
                                },
                            )
                        else:
                            if appLog.isVerbose():
                                DictUtils.set(
                                    funcResult["value"],
                                    entry_attr + ".note",
                                    {
                                        "msg": "Extracted",
                                        "extractionFormat": extractFormat,
                                        "textIn": entry_value,
                                        "contents": result.named,
                                    },
                                )
                            # resultOut={}

                            for xx in result.named.keys():
                                nameOut = xx
                                value = result.named[xx]
                                if xx.startswith("n."):
                                    nameOut = xx.removeprefix("n.").replace(".", "/")
                                    try:
                                        value = value.strip()
                                        value = int(value)
                                    except:  # ValueError:
                                        pass
                                DictUtils.set(funcResult["value"], nameOut, value)
                                # resultOut[nameOut]=value
                            # DictUtils.set(theHeaderValues, entry_attr+".result",resultOut)
                        # entry_value = entry_value.strip("\x00").strip(" \r\n\t")
                        entry_skip = True
                    elif code == "text[lines]":
                        entry_value = entry_value.splitlines()
                    else:
                        entry_value = entry_value.strip("\x00").strip(" \r\n\t")
                elif code.startswith("type:"):
                    typesLookupName = code.removeprefix("type:")
                    conversion = DictUtils.get(defLookup, typesLookupName, None)
                    if conversion is None:
                        return {
                            "errmsg": f"Unknown type '{typesLookupName}' in conversion definition for {entry_attr}"
                        }
                    arrayLength: int | None = conversionEntry.get("arrayLength", None)

                    if arrayLength is None:
                        converted = self.loadConversionFromBytes(
                            conversion, rawDataStream
                        )
                        errMsg = converted.get("errmsg", None)
                        if errMsg is not None:
                            return {
                                "errmsg": f"Error loading type '{typesLookupName}' in conversion definition for {entry_attr} : {errMsg}"
                            }
                        entry_isEmpty = converted.get("isEmpty", False)
                    else:
                        entry_isEmpty = True
                        entry_value = []
                        for ii in range(0, arrayLength):
                            converted = self.loadConversionFromBytes(
                                conversion, rawDataStream
                            )
                            errMsg = converted.get("errmsg", None)
                            if errMsg is not None:
                                return {
                                    "errmsg": f"Error loading type array '{typesLookupName}'[{ii}] in conversion definition for {entry_attr} : {errMsg}"
                                }

                            isEmpty = converted.get("isEmpty", False)
                            if (
                                not conversionEntry.get("skipIfAllZeros", False)
                                or not isEmpty
                            ):
                                entry_value.append(converted.get("value", None))

                        entry_isEmpty = len(entry_value) == 0

                else:  # elif code in "HQLBI":
                    entry_numBytes = struct.calcsize(code)
                    entry_bytes = rawDataStream.read(entry_numBytes)
                    entry_value = struct.unpack(code, entry_bytes)[0]

                    lookups = conversionEntry.get("lookup", None)
                    if (lookups is not None) and isinstance(lookups, dict):
                        if str(entry_value) in lookups:
                            entry_value = lookups[str(entry_value)]
                        else:
                            return {
                                "errmsg": f"Unknown value '{entry_value}' for {entry_attr} : not in lookup {lookups}"
                            }
                    entry_printSuffix = f"{code}"

                ###############################
                #
                if len(entry_bytes) != entry_numBytes:
                    raise Exception(
                        f"Requires {entry_numBytes} bytes, but only {len(entry_bytes)} bytes available"
                    )

                # if (entry_numBytes > 0):
                #    if (pos + entry_numBytes) >= len(rawData):

                #########################
                #
                # Append:  entry_attr, entry_value, entry_numBytes, entry_skip
                if entry_isEmpty is None:
                    entry_isEmpty = (entry_numBytes == 0) or all(
                        (b == 0 for b in entry_bytes)
                    )

                if not entry_isEmpty:
                    funcResult["isEmpty"] = False
                elif conversionEntry.get("skipIfEmpty", False):
                    entry_skip = True

                if not entry_skip:
                    DictUtils.set(funcResult["value"], entry_attr, entry_value)
                if entry_printSuffix is not None:
                    if entry_numBytes == 0:
                        txtSuffix = ""
                    elif entry_numBytes == 1:
                        txtSuffix = f"  1 byte"
                    else:
                        txtSuffix = f"{entry_numBytes:3} bytes"

                    pos: int = rawDataStream.tell() - len(entry_bytes)
                    appLog.print_verbose(
                        f"  • {entry_attr:<34}={str(entry_value):<24}  {entry_printSuffix:<12} {txtSuffix:<9} : {' '*(pos*2)}{entry_bytes.hex():<30}  {conversionEntry.get('lookup', '')}"
                    )

            except Exception as e:
                for x in traceback.format_exc().splitlines():
                    sys.stderr.write(f"    {conversionEntry}\n")
                return {
                    "errmsg": f"Error loading header data from raw bytes -- {conversionEntry} @{pos}: {e}"
                }

        return funcResult

    def loadHeaderFromBytes(self, rawData: bytes) -> dict[str, Any] | str:
        """Returns (headerDataTuple, extraHexData) | errorMessage
        Load header data from raw bytes and return a tuple of the data and any extra hex data.
        No validation of prefix - caller must ensure that the rawData is valid for this header format.

        The header is loaded:
           annotations/xxxx -> annotations
           timeStamp_ns     -> timestamp_ns
           timeStamp_us     -> timestamp_ns * 1000
        """
        theHeaderValues = {}

        appLog.print_verbose(f"Loading header  ({self.name()}) ")

        theHeaderValues[".format"] = self.overallFormatDefinition
        DictUtils.set(theHeaderValues, ".header/name", self.name())

        headerDataConversion = self.HEADER_INFO.get("HEADER_DATA_CONVERSION", []).copy()
        headerDataConversion.insert(
            0,
            {
                "code": "verifyHex",
                "attr": ".header/prefixHex",
                "value": bytes((ord("D"), ord("B"), 32)).hex(),
            },  # This is a constant, not loaded from the header
        )

        rawDataStream = io.BytesIO(rawData)
        converted = self.loadConversionFromBytes(
            headerDataConversion, rawDataStream
        )  # < Returns: {'value':..., 'isEmpty':...} | {'errmsg':...}

        errMsg = converted.get("errmsg", None)
        if errMsg is not None:
            return errMsg

        pos = rawDataStream.tell()
        theHeaderValues.update(converted.get("value", {}))

        DictUtils.set(theHeaderValues, ".header/numBytes", rawDataStream.tell())
        if DictUtils.get(
            theHeaderValues, "annotations/fileFormat"
        ) is not None or not self.HEADER_INFO.get("isDefaultHeaderFormat", False):
            DictUtils.set(
                theHeaderValues, "annotations/fileFormat/headerKind", self.name()
            )

        contents_dataConversion = self.HEADER_INFO.get("contents", None)

        if (contents_dataConversion is not None) and (pos is not None):

            result = self.loadConversionFromBytes(
                contents_dataConversion, rawDataStream
            )  # < Returns: {'value':..., 'isEmpty':...} | {'errmsg':...}
            errMsg = result.get("errmsg", None)
            if errMsg is not None:
                return errMsg

            value = result.get("value", {})
            if (value is not None) and isinstance(value, dict):
                for xx in value.keys():
                    DictUtils.set(theHeaderValues, "annotations/" + xx, value[xx])
            else:
                DictUtils.set(theHeaderValues, "annotations/contents", value)

        ############################################
        # Done
        #
        try:
            appLog.print_verbose(f"Final: {Utils.asJsonStr(theHeaderValues,indent=2)}")
        except Exception as e:
            appLog.print_warning(f"Error converting header values to JSON: {e}")
        return theHeaderValues


class CustomContentsFormatDefinition:

    def __str__(self):
        txt = f"{self.definitions}+supportsImage={self.supportsImage()}"

        return txt

    def includes(self, what: str) -> bool:
        defaultValue = self.KIND.split("/")[-1] == what
        return DictUtils.getBool(self.definitions, "includes/" + what, defaultValue)

    def supportsImage(self) -> bool:
        return self.includes("image")

    def definition(
        self, name: str | list[str], defaultValue: Any | None = None
    ) -> Any | None:
        return DictUtils.get(self.definitions, name, defaultValue)

    def getSummary(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for x in [
            "kind",
            "description",
            "version",
            "suggested_file_ext",
            "suggested_file_ext_raw",
        ]:
            result[x] = self.definition(x, None)
        return result

    def __init__(self, definitionDict: dict[str, Any], src: str = ""):
        self.definitions = dict(definitionDict)
        self.src = src
        self.headerFormatNames = []
        self.minTotalSize_bytes: int | None = definitionDict.get(
            "minTotalSize_bytes", None
        )
        for x in definitionDict.get("headerFormats", []):
            self.headerFormatNames.append(x.get("PREFIX.asText", "<unnamed>"))

        self.KIND = definitionDict.get("kind", "<kind:UNKNOWN>")
        self.DESCRIPTION = definitionDict.get(
            "description", "<No Description Available>"
        )
        self.FILE_EXT = definitionDict.get("suggested_file_ext", ".data+")

        self.VERSION = definitionDict.get("version", "0.0.1")

        self.headerFormatList: list[DataHeaderFormat] = []

        for x in definitionDict.get("headerFormats", []):
            self.headerFormatList.append(DataHeaderFormat(x, self.definitions))

    def matchBytesToFormats(self, dataIn: bytes | None) -> CustomisedContents | str:
        if len(self.headerFormatList) == 0:
            return f"{self.KIND}: No header formats defined"

        if dataIn is None:
            return f"{self.KIND}: Bitstream data missing"

        appLog.print_verbose(f"Checking header formats for {self.KIND}:")

        checkedList = []
        for headerFormat in self.headerFormatList:
            appLog.print_verbose(f" * Checking header format: {headerFormat.name()}")
            if headerFormat.headerPrefixMatches(dataIn):
                appLog.print_verbose(f"Found header format: {headerFormat.name()}")
                return CustomisedContents(self.KIND, headerFormat, dataIn)

            else:
                checkedList.append(headerFormat.name())

        appLog.print_verbose(
            f"Checked header formats: {', '.join(checkedList)} - No match found"
        )

        clip = self.minTotalSize_bytes
        return f"{self.KIND}: Expected one of {checkedList} headers.  Header=0x{dataIn[:16 if clip is None else clip].hex()}..."

    def ADD_STREAM_IN_HERE(self):
        pass  #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

    def suggestSampleFileName(self, suffix: str = "") -> str:
        txt = self.definition("suggested_file_prefix")
        if txt is None:
            if self.supportsImage():
                txt = "image"
            else:
                txt = "data"

        return f"{str(txt)}{suffix}{self.definition('suggested_file_ext_raw', self.FILE_EXT.removesuffix('+'))}"


# Example:
#
#    "kind":"argus/image",
#    "description":"Argus Image",
#    "suggested_file_ext_raw":".bin",
#    "suggested_file_ext":".argus+",
#    "suggested_file_prefix":"image",
#    "version":"0.0.2",
#    "commandSuffix":"ArgusImage",
#    "headerFormats":

#
#  * kind
#  * supportsImage
#  * input.raw
#  * raw bitstream
#  * .data+
#  * "raw bitstream (such as a .bin file)"


def customFormatDefinition_get(customFormatName: str | None) -> dict[str, Any] | None:
    customFormat = customFormat_get(customFormatName)
    if customFormat is None:
        return None
    return customFormat.definitions


def customFormat_findByRawData(
    rawData: bytes | None,
) -> CustomContentsFormatDefinition | None:
    formatLookup, _ = getCustomFormatInfo()

    for formatName in formatLookup.keys():
        customFormat = formatLookup[formatName]
        customisedOrErrMsg = customFormat.matchBytesToFormats(rawData)
        if not isinstance(customisedOrErrMsg, str):
            return customFormat

    return None


def customFormat_get(
    customFormatName: str | None, includeSpecialCases: bool = True
) -> CustomContentsFormatDefinition | None:
    formatLookup, _ = getCustomFormatInfo()

    customFormatName = "" if customFormatName is None else customFormatName.strip()
    result: CustomContentsFormatDefinition | None = formatLookup.get(
        customFormatName, None
    )
    if result is None:
        if customFormatName.startswith("image:") or (
            customFormatName.startswith("generic/")
            and customFormatName.endswith("/image")
        ):
            specStr = customFormatName.removeprefix("generic/").removesuffix("/image")
            specStr = customFormatName.removeprefix("image:")

            imageData = simpleUtils.imageFormatTextToSpec(specStr)

            definition: dict[str, Any] = {
                "kind": "generic/" + specStr + "/image",
                "description": "Image",
                "suggested_file_ext_raw": Utils.makeImageFormatExt(specStr),
                "suggested_file_ext": ".img+",
                "suggested_file_prefix": "image",
                "includes": {"image": True, "annotations": True},
                "annotations": {"imageData": imageData},
                "notes": {"builtFrom": f"image:{specStr}"},
            }

            appLog.print_verbose(
                f"Creating custom format for {customFormatName} -> {definition}"
            )

            result = CustomContentsFormatDefinition(definition)
        elif includeSpecialCases and (customFormatName == "image"):
            samples_dir = os.path.abspath(f"{project_root_dir}/samples")
            definition: dict[str, Any] = {
                "note": "Special case for creating a raster image from a .png file",
                "kind": "generic/image",
                "description": "PNG Image conversion",
                "suggested_file_ext_raw": ".rawimg",
                "suggested_file_ext": ".img+",
                "suggested_file_prefix": "image",
                "includes": {"image": True, "annotations": True},
                "import_function": "importFromPng",
                "examples": {
                    "import": [f"{samples_dir}/small_image.png"],
                    "annotatedData": [f"{samples_dir}/small_image.img+"],
                },
            }

            appLog.print_verbose(
                f"Creating custom format for {customFormatName} -> {definition}"
            )

            result = CustomContentsFormatDefinition(definition)

        elif (customFormatName != "") and not any(
            customFormatName.endswith(suffix)
            for suffix in CUSTOM_FORMAT_SUFFIXES_TO_IGNORE
        ):
            appLog.print_warning(
                f"No custom format found for {customFormatName}.  Options include {list(formatLookup.keys())+['image:mono12_1024x1024','image:mono8_640x480', ' …']}"
            )

    return result


def relPathOrDefault(path: Any, default: str) -> str:
    if (path == "") or (path is None) or (not isinstance(path, str)):
        return default
    else:
        return os.path.relpath(path)


def customFormat_getBasicInfo(
    src: CustomContentsFormatDefinition | None,
) -> dict[str, Any]:

    raw_type = "bitstream"
    raw_type_extra = " (such as a .bin file)"
    annotated_file_ext = ".data+"
    result: dict[str, Any] = {
        "kind": "",
        "includes": {"image": True, "bitstream": True},
        "known": (src is not None),
        "input.raw": "input.raw",
        "/path/to/sample.raw": "/path/to/input.raw",
        "/path/to/sample.data+": "/path/to/input.data+",
        ".raw": ".raw",
    }
    if src is not None:
        raw_type = str(src.definition("description", raw_type))
        annotated_file_ext = (
            str(src.definition("suggested_file_ext", ".data+")).removesuffix("+") + "+"
        )

        includes = src.definition("includes", {})
        if isinstance(includes, list):
            includes = {k: True for k in includes}
        result["includes"] = includes

        result["kind"] = src.KIND
        result["input.raw"] = src.suggestSampleFileName()
        result["/path/to/sample.raw"] = relPathOrDefault(
            src.definition("examples/bitstream/0"),
            "/path/to/" + src.suggestSampleFileName(),
        )
        result["/path/to/sample.data+"] = relPathOrDefault(
            src.definition("examples/annotatedData/0"),
            "/path/to/input" + annotated_file_ext,
        )

        result[".raw"] = src.definition("suggested_file_ext_raw", ".raw")
        raw_type_extra = ""

    result["raw bitstream"] = "raw " + raw_type.removeprefix("raw").strip()
    result["raw bitstream (such as a .bin file)"] = (
        result["raw bitstream"] + raw_type_extra
    )

    result[".data+"] = annotated_file_ext

    return result


this_dir = os.path.abspath(f"{os.path.dirname(__file__)}")
project_root_dir = os.path.abspath(f"{this_dir}/../")


def getCustomFormat_fromFile(fname: str) -> CustomContentsFormatDefinition | None:
    jsonData = fileUtils.loadJsonDictFromFile(
        fname, "annotatedData Custom Format Definition", exceptionOnError=False
    )

    dirname = os.path.dirname(fname)
    errorMsg = jsonData.get("error", None)
    if errorMsg is not None:
        appLog.print_error(f"Error loading custom format from {fname}: {errorMsg}")
        return None

    examples = jsonData.get("examples", None)
    if isinstance(examples, dict):
        jsonData["examples"] = {
            k: [os.path.abspath(v.replace("<definition_dir>", dirname)) for v in vs]
            for k, vs in examples.items()
        }
    return CustomContentsFormatDefinition(jsonData, fname)


g_defaultFormat: CustomContentsFormatDefinition | None = None
g_customFormatLookup: dict[str, CustomContentsFormatDefinition] | None = None
g_configuration: dict[str, Any] = {}


def _customFormatList_load() -> Tuple[
    dict[str, CustomContentsFormatDefinition],
    CustomContentsFormatDefinition | None,
    dict[str, Any],
]:
    def __getCustomFormatsInDir(
        dirToSearch: str, prefix: str = "", lookForDefaults: bool = False
    ) -> dict[str, CustomContentsFormatDefinition]:
        # |Logging| appLog.print_info(f"__getCustomFormatsInDir: Scanning directory: {dirToSearch}")

        results = {}
        if os.path.isdir(dirToSearch):
            for f in os.scandir(dirToSearch):
                if f.is_dir():
                    results.update(
                        __getCustomFormatsInDir(f.path, prefix + f.name + "/")
                    )
                elif f.is_file() and f.name.endswith(".json"):
                    format = getCustomFormat_fromFile(f.path)

                    if format is not None:
                        results[format.KIND] = format

        return results

    ##################################################################
    # Step 1 - Generate list of 'dataFormats' directories to review
    #
    pathMain = os.path.abspath(project_root_dir + "/dataFormats/")

    paths: list[str] = [pathMain]

    for f in os.scandir(project_root_dir + "/../"):
        if f.path.split("/")[-1].startswith("annotatedData_ext-"):
            tryThis = os.path.abspath(f.path + "/dataFormats")
            if f.is_dir() and os.path.isdir(tryThis) and not (tryThis in paths):
                paths.append(tryThis)

    ###################################################################
    #
    # Step 2 - Load all custom formats found in 'paths' into 'results'
    #
    results: dict[str, CustomContentsFormatDefinition] = {}
    for path in paths:
        appLog.print_verbose(f"Adding custom formats: {path}")
        results.update(__getCustomFormatsInDir(path))

    #
    # Step 3 - Load Configuration
    #
    configuration = fileUtils.jsonObjFromFileWithExtras(
        pathMain + "/defaults.json",
        "customFormat configuration (JSON)",
        giveWarningOnFileMissing=False,
    )

    #
    # Step 4 - Get Default from Configuration
    #

    defaultFormat: CustomContentsFormatDefinition | None = None
    defaultName = configuration.get("defaultFormat", None)

    customNames = list(results.keys())
    customNames.sort()
    if not isinstance(defaultName, str):
        defaultName = ""  # if len(customNames) < 1 else customNames[0]

    if defaultName != "":
        defaultFormat = results.get(defaultName, None)
        if defaultFormat is None:
            appLog.print_warning(
                f"Default format '{defaultName}' not found in format list: {customNames}"
            )
        else:
            defaultFormat = results[defaultName]

    return results, defaultFormat, configuration


def getDefaultFormat() -> CustomContentsFormatDefinition | None:
    global g_defaultFormat
    return g_defaultFormat


def getCustomConfiguration() -> dict[str, Any]:
    global g_configuration
    return g_configuration


def getCustomFormatInfo() -> (
    Tuple[
        dict[str, CustomContentsFormatDefinition], CustomContentsFormatDefinition | None
    ]
):
    global g_defaultFormat, g_customFormatLookup, g_configuration
    if g_customFormatLookup is None:
        g_customFormatLookup, g_defaultFormat, g_configuration = (
            _customFormatList_load()
        )

    return g_customFormatLookup, g_defaultFormat
