from copy import deepcopy
from enum import Enum
import json
import json
import math
import os
import sys
from typing import Any, NoReturn, Tuple, Union
import tempfile

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)


from ukko_pylibs.basic import styling
from ukko_pylibs.basic.simpleUtils import Utils, DictUtils, PrettyText, EscapeMgr
from ukko_pylibs.basic.logger import appLog
from ukko_pylibs.basic.class_HandledException import HandledException
from ukko_pylibs._external.parseProtoBuf import decodeProtobuf_binToDict


#
################################################################################


class IOneOf_Interface[Kind]:

    def __init__(
        self,
        validValues_defaultFirst: list[Kind],
        thisValue: Kind,
        name: str = "",
        extras: dict[str, Any] | None = None,
    ):
        self.validValues = validValues_defaultFirst
        self.default = self.validValues[0]
        self.thisValue = thisValue
        self.extras: dict = extras or {}
        self.name: str = name or self.__class__.__name__.lower().removesuffix("type")

        if not self.isValid():
            appLog.print_warning("Created -- " + self.getWarning())

    def getExtra(self, part: str, defaultValue: Any) -> Any:
        return self.extras.get(part, defaultValue)

    def isValid(self) -> bool:
        return self.isEmpty() or (self.thisValue in self.validValues)

    def asValueOrDefault(self) -> Kind:
        return self.asValueOr(self.default)

    def asValueOr(self, defaultValue: Kind) -> Kind:
        return defaultValue if self.isEmpty() else self.thisValue

    def asDisplayText(self) -> str:
        if self.isEmpty():
            result = str(self.default)
        elif self.isValid():
            result = str(self.thisValue)
        else:
            result = str(self.thisValue) + "❓"

        if self.extras:
            result += str(self.extras).replace('"', "")

        return result

    def isDefault(self) -> bool:
        return self.isEmpty() or self.thisValue == self.default

    def isValue(self, compareTo: Kind) -> bool:
        return self.thisValue == compareTo

    def isEmpty(self) -> bool:
        return self.thisValue == ""

    def asDict(self, isVerbose: bool = True) -> dict[str, Any] | Kind:
        if not isVerbose:
            return self.thisValue
        else:
            result: dict[str, Any] = {
                "value": self.thisValue,
                "possible_values": self.validValues,
            }

            if self.isEmpty():
                result["isEmpty"] = self.isEmpty()
            if self.isDefault():
                result["isDefault"] = self.isDefault()

            if self.asValueOrDefault() != self.thisValue:
                result["asValue"] = self.asValueOrDefault()
            if self.asDisplayText() != self.asValueOrDefault():
                result["asText"] = self.asDisplayText()

            if self.extras:
                result["extras"] = self.extras
        return result

    def getWarning(self):
        if self.isValid():
            return ""
        else:
            return f"Invalid {self.name} of `{styling.asError(self.thisValue)}`.  Valid options are to omit or use one of {styling.asSuggestionList(self.validValues)}"

    def appendWarning(self, errList: list[str]):
        msg = self.getWarning()
        if msg:
            errList.append(msg)

    def wouldBeValidValue(self, possibleValue):
        return possibleValue == "" or (possibleValue in self.validValues)


class SourceType(IOneOf_Interface[str]):
    def __init__(self, thisValue: str = ""):
        super().__init__(["direct", "file", "hex"], thisValue, "source")


class ContentType(IOneOf_Interface[str]):
    def __init__(self, thisValue: str = "", extras: dict | None = None):
        super().__init__(
            ["auto", "text", "json", "bin", "protobuf"], thisValue, "content", extras
        )  # @todo: Image etc...

    def isTextType(self):
        return self.asValueOrDefault() in ["text", "json"]

    def isJson(self):
        return self.asValueOrDefault() in ["json"]


CLIP_LENGTH = 80


class DataSourceWithInfo:
    """Can use a prefix such as 'file:xxx', 'file[json]:'  ,'hex[protobuf]:' etc
    If none is provided it will default to 'direct[auto]'.
    Prefix is of the format SourceType[ContentType]:
    """

    def getNewPrefix(self) -> str:
        if not isinstance(self.asProvidedAfterPrefix, str):
            return ""

        _prefix: str = ""
        if not self.sourceType.isDefault():
            _prefix = self.sourceType.asValueOrDefault()
        elif ":" in self.asProvidedAfterPrefix:
            _prefix = self.sourceType.default

        if not self.contentType.isDefault():
            if _prefix == "":
                _prefix = self.contentType.asValueOrDefault()
            else:
                _prefix += "[" + self.contentType.asValueOrDefault() + "]"

        if _prefix != "":
            _prefix += ":"
        return _prefix

    def asShouldBeProvided(self) -> Any:
        if not isinstance(self.asProvidedAfterPrefix, str):
            return self.asProvidedAfterPrefix
        else:
            return self.getNewPrefix() + self.asProvidedAfterPrefix

    def isEmpty(self) -> bool:
        return (
            self.sourceType.isEmpty()
            and self.contentType.isEmpty()
            and self.prefix == ""
            and (
                (self.asProvidedAfterPrefix is None)
                or (self.asProvidedAfterPrefix == "")
            )
        )

    def __init__(self, interpretPrefix: bool, src: Any | None, formatIn: str = ""):
        if isinstance(src, DataContents):
            raise ValueError("DataSourceWithInfo(DataSourceWithInfo) is not supported")

        #    self.additionalOptions={}
        #    self.formatExtrasObj={}

        self.asProvidedOrig = src

        #####################################################################
        #
        self.sourceType = SourceType("")
        self.contentType = ContentType(formatIn)
        self.asProvidedAfterPrefix = src
        self.prefixIssues: list[str] = []
        self.prefix = ""

        if not src or not isinstance(src, str):

            return

        if not interpretPrefix:
            if src.strip().startswith("{") and self.sourceType.isEmpty():
                try:
                    self.asProvidedAfterPrefix = json.loads(src)
                    self.contentType = ContentType("json")
                except:
                    pass

        if not interpretPrefix:
            return

        if src.startswith("@"):
            src = "file:" + src.removeprefix("@")  # <- Support deprecated format
            self.asProvidedOrig = (
                src  # < Use the new style to enforce not using deprecated format
            )

        ####################################################################
        #
        # Can use a prefix such as 'file:xxx', 'file[json]:'  ,'hex[protobuf]:' etc
        # If none is provided it will default to 'direct[auto]'.
        # Prefix is of the format SourceType[ContentType]:
        #
        # src to:
        #  * self.asProvidedAfterPrefix
        #  * self.sourceType
        #  * self.contentType
        #  * self.prefixIssues
        #  * self.prefix
        if src.strip().startswith("{"):
            self.contentType = ContentType("json")
            return

        n = src.find(":")
        if n <= 0:
            return

        rangeToReview = (
            math.ceil(
                (
                    max(
                        len(n)
                        for n in (
                            self.sourceType.validValues + self.contentType.validValues
                        )
                    )
                    + 2
                )
                / 20
            )
            * 20
        )

        if n > rangeToReview:
            appLog.print_warning(
                f"Provided text `{styling.asError(PrettyText.asClipped(src,min(50,n+2)))}` has colon at location {n}.\nEven though we are only reviewing the first {rangeToReview} characters, you should consider prefixing with `{styling.asSuggestion('text:')}` to avoid any accidental format interpretation in the future"
            )
            return

        _prefix = src[:n]
        _parts = _prefix.split("[", 1)
        _issues: list[str] = []

        self.sourceType = SourceType(_parts[0])

        if len(_parts) == 2:
            if _parts[1].endswith("]"):
                self.contentType = ContentType(_parts[1].removesuffix("]"))
            else:
                self.prefixIssues.append(
                    "Expected content type to be omitted, or of the form '[xxx]'.  Missing closing ']'"
                )

        self.contentType.appendWarning(self.prefixIssues)
        self.sourceType.appendWarning(self.prefixIssues)

        if self.prefixIssues:
            appLog.print_warning(
                f"The provided argument has the prefix `{styling.asError(_prefix)}:` which is not valid:"
            )
            for _issue in self.prefixIssues:
                appLog.print_warning(f" • {_issue}")

            return

        self.prefix = _prefix + ":"
        self.asProvidedAfterPrefix = src[n + 1 :]
        if self.contentType.isEmpty():
            self.contentType = self.getSuggestedContentType()

        if formatIn:
            if not self.contentType.isDefault() and not self.contentType.isValue(
                formatIn
            ):
                appLog.print_warning(
                    f"Forced content type '{formatIn}' over calculated format type '{self.contentType.asDisplayText()}'"
                )

            self.contentType.thisValue = formatIn

    def asDict(self) -> dict[str, Any] | str:
        result: dict[str, Any] = {}

        if type(self.asProvidedOrig) is str and self.prefix:
            result["prefix"] = self.prefix
            result["asProvidedAfterPrefix"] = self.asProvidedAfterPrefix
            result["self.sourceType"] = self.sourceType.asDict()
            result["self.contentType"] = self.contentType.asDict()
        else:
            result["contents"] = Utils.typeOfAsStr(self.asProvidedOrig)

        if self.prefixIssues:
            result["prefixIssues"] = styling.asStylingRemoved(self.prefixIssues)

        if self.getFilename():
            result["filename"] = self.getFilename()

        result["asShouldBeProvided"] = self.asShouldBeProvided()
        return result

    def getFilename(self) -> str | None:
        return (
            str(self.asProvidedAfterPrefix) if self.sourceType.isValue("file") else None
        )

    def asCaption(self, clipLen: int | None = None) -> str:
        txt = self.asShouldBeProvided()
        if clipLen:
            txt = PrettyText.asClipped(txt, clipLen)
        return txt

    def getSuggestedContentType(self) -> ContentType:

        fname = self.getFilename()
        if not fname:
            return ContentType("")

        _formatExtras = {}
        fname_suffix = fname.lower().removesuffix(".ref")
        if fname_suffix.endswith(".subst"):
            fname_suffix = fname_suffix.removesuffix(".subst")
            _formatExtras["permitSubstitutions"] = True

        if fname_suffix.endswith(".md") or fname_suffix.endswith(".txt"):
            _formatBase = "text"
        elif fname_suffix.endswith(".json"):
            _formatBase = "json"
        elif fname_suffix.endswith(".bin"):
            _formatBase = "bin"
        elif (
            fname_suffix.endswith("+")
            or fname_suffix.endswith(".proto")
            or fname_suffix.endswith(".b")
        ):
            _formatBase = "protobuf"
        else:
            _formatBase = "auto"

        return ContentType(_formatBase, _formatExtras)

    def getBaseContentFormat(self, default: str = "auto") -> str:
        return self.contentType.thisValue

    def getFormattingInfoAsDisplayText(self) -> str:
        return self.contentType.asDisplayText()

    def setBaseFormatIfAuto(
        self, baseFormat: str, extrasAppend: dict[str, Any] | None = None
    ) -> bool:
        if not self.contentType.isDefault():
            return False

        self.contentType.thisValue = baseFormat
        if extrasAppend:
            self.contentType.extras.update(extrasAppend)

        return True


class DataContents(DataSourceWithInfo):
    """General DataContents for storage and comparison"""

    def __init__(
        self,
        _value: Any,
        intrepretAsCommandLineEntry: bool = False,
        formatIn: str = "",
        optionalNameSuggestion: str | None = None,
        optionalSubstitutions: dict[str, Any] | None = None,
    ):

        super().__init__(intrepretAsCommandLineEntry, _value, formatIn)
        self.optionalName = optionalNameSuggestion or ""
        self.nameSuggestedPrefix = (
            (optionalNameSuggestion + "_") if optionalNameSuggestion else "data_"
        )
        self._warning: str | None = None

        if intrepretAsCommandLineEntry and isinstance(self.asProvidedAfterPrefix, str):
            self.asData: Any = EscapeMgr.fromEscapedText(self.asProvidedAfterPrefix)
        else:
            self.asData = self.asProvidedAfterPrefix

        self.fname: str = ""
        self.fileIsTempCreated: bool | None = None
        self.interpretAs: str = ""
        self.asObj: Any | None = None
        self.optionalSubstitutions: dict[str, Any] | None = deepcopy(
            optionalSubstitutions
        )
        self._doLoadExtendedData()  # < Can modify .interpretAs & .format
        self.asFormatted: Any = self._doFormatContents()

    def getWarnings(self) -> list[str]:
        warnings: list[str] = []
        if self._warning:
            warnings.append(self._warning)
        warnings.extend(self.prefixIssues)

        return warnings

    def asParamTxt(self) -> str:
        resultTxt = "<None>"
        if self.asData is None:
            resultTxt = "<None>"
        elif self.fname and self.fileIsTempCreated == False:
            resultTxt = f"file:{self.fname}"
        elif isinstance(self.asData, str):
            resultTxt = self.asData
        elif isinstance(self.asData, bytes):
            resultTxt = "hex:" + self.asData.hex()
        elif isinstance(self.asData, int):
            resultTxt = str(self.asData)
        else:
            try:
                resultTxt = Utils.asJsonRStr(self.asData, sortKeys=True)
            except Exception as e:
                resultTxt = "⚠️  " + str(self.asProvidedAfterPrefix)
                appLog.print_warning(
                    f"DataContents.asParamText(): {self.asData} (type: {type(self.asData)})"
                )
                appLog.print_info("-----")
                appLog.print_info(f"asParamTxt: {resultTxt}")

                appLog.print_info(
                    f"asProvidedAfterPrefix: {self.asProvidedAfterPrefix}"
                )
                appLog.print_info("-----")

        return resultTxt

    def asDict(self, isFull: bool = True) -> dict[str, Any] | str:
        out: dict[str, Any] = {
            "warnings": self.getWarnings(),
            "asData": self.asData,
            "interpretAs": self.interpretAs,
            "fname": self.fname,
        }

        if isFull:
            out.update(
                {
                    "dataSource": super().asDict(),
                    "asFormatted": self.asFormatted,
                    "asObj": self.asObj,
                }
            )

        cleaned = DictUtils.getWithDefaultValuesRemoved(
            out,
            {
                "warnings": [],
                "interpretAs": "",
                "format": "auto",
                "formatExtras": {},
                "fname": "",
                "fileIsTempCreated": None,
                "asObj": None,
                "asFormatted": self.asData,
                "asProvided": self.asData,
            },
        )

        if (
            len(cleaned) == 1
            and "asData" in cleaned
            and isinstance(cleaned["asData"], str)
        ):
            return cleaned["asData"]
        return cleaned

    def isTextFormat(self):
        return self.contentType.isTextType()

    def asTextLines(self) -> list[str]:
        try:
            if hasattr(self.asFormatted, "asTextLines") and callable(
                getattr(self.asFormatted, "asTextLines")
            ):
                return self.asFormatted.asTextLines()
        except Exception:
            pass

        if self.contentType.isValue("protobuf"):
            try:
                decoded_message = decodeProtobuf_binToDict(self.asBytes())
                return Utils.asJsonStr(decoded_message, indent=2).splitlines()
            except Exception as e:
                self.warning = f"Unable to convert protobuf to tags: {e}"
                return [f"[protobuf:{type(self.asFormatted)}] {str(self.asFormatted)}"]
        elif isinstance(self.asFormatted, str):
            return self.asFormatted.splitlines()
        elif isinstance(self.asFormatted, list):
            out = []

            for x in self.asFormatted:
                out += str(x).splitlines()
            return out
        else:
            return [f"[{type(self.asFormatted)}]{self.asFormatted}"]

    def getAsDisplay(self, clipLen: int = CLIP_LENGTH) -> str:

        _paramText = " ".join(str(self.asProvidedAfterPrefix).split())

        if self.asProvidedAfterPrefix != "" and isinstance(
            self.asProvidedAfterPrefix, str
        ):
            _fname = self.getFilename()
            if _fname:
                _paramText = self.prefix + Utils.pathAsDisplay(_fname)

        return PrettyText.asClipped(_paramText, clipLen)

    def __str__(self) -> str:
        return self.getAsDisplay()

    def getDisplayText(self, name: str) -> str:

        _paramText = self.getAsDisplay()
        if _paramText == "":
            return name
        else:
            return f"{name}:{_paramText}"

    def isEmpty(self) -> bool:
        return (
            self.asData == ""
            or self.asData == []
            or self.asData == [""]
            or self.asData == {}
            or self.asData is None
        )

    def asContentsSummary(self, valueIfEmpty="«Empty»") -> str:
        if self.isEmpty():
            return " " + valueIfEmpty

        if isinstance(self.asData, bytes):
            summaryTxt = PrettyText.asClipped(
                "hex:" + self.asData.hex(),
                maxLen=40,
                suffix=f"… ({len(self.asData)} bytes)",
            )
        elif isinstance(self.asData, str):
            _asLines = self.asData.splitlines()
            lineCount = len(_asLines)
            if lineCount > 1:
                summaryTxt = (
                    PrettyText.asClipped(_asLines[0], maxLen=40, suffix="")
                    + " … "
                    + PrettyText.pluralize(lineCount, "line")
                )
            else:
                summaryTxt = PrettyText.asClipped(
                    self.asData,
                    maxLen=40,
                    suffix=f'… ({PrettyText.pluralize(len(self.asData), "char")})',
                )
        else:
            summaryTxt = ""

        summaryTxt = summaryTxt.strip().replace("\\\\", "\\")
        if not self.fname:
            pass
        elif summaryTxt:
            summaryTxt = self.fname + "  " + summaryTxt
        else:
            summaryTxt = self.fname

        if not self.contentType.isEmpty():
            summaryTxt = self.contentType.asDisplayText() + ": " + summaryTxt

        return summaryTxt

    def _doFormatContents(
        self,
    ) -> list[str]:

        outData = self.asData
        if self.contentType.isJson():
            try:
                outData = json.dumps(
                    self.asObj,
                    sort_keys=True,
                    indent=2,
                    skipkeys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                )
            except Exception as e:
                self.warning = f"Unable to convert to JSON: {e}"

        if self.contentType.getExtra("permitSubstitutions", False) and (
            self.optionalSubstitutions is not None
        ):
            outData = PrettyText.withSubstitutions(
                str(outData), self.optionalSubstitutions, "$[", "]"
            )

        _lines = str(outData).split("\n")

        return _lines

    def _loadFromFile(self, fname: str, caption: str) -> Any:
        self.fname = fname
        self.fileIsTempCreated = False

        if not os.path.isfile(fname):
            raise HandledException(f"File not found: {json.dumps(fname)}")
        try:
            with open(fname, "rb") as f:
                self.asData = f.read()
        except Exception as e:
            raise HandledException(f"Error reading file {json.dumps(fname)}", e)

    def doErrorExit(self, msg: str, e: Exception | None = None) -> NoReturn:
        from ukko_pylibs.appAssist.appSupport import (
            error_msg_exit,
        )  # < Not permitted to be imported at module-level

        error_msg_exit(f"DataContents -- {msg}", e)

    def asBytes(self) -> bytes:
        if isinstance(self.asData, bytes):
            return self.asData
        elif isinstance(self.asData, str):
            return self.asData.encode("utf-8")
        elif isinstance(self.asData, dict):
            return Utils.asJsonStr(self.asData).encode("utf-8")
        else:
            raise ValueError(
                f"Cannot convert asData of type {type(self.asData)} to bytes"
            )

    def exportToFileIfNeeded(self) -> bool:
        if self.fname:
            return True  # Already saved

        if self.asData is None:
            return False
        if self.isEmpty():
            return False
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                suffix="."
                + (
                    "output"
                    if self.contentType.isEmpty()
                    else self.contentType.thisValue
                ),
                prefix=self.nameSuggestedPrefix,
                delete=False,
            ) as temp_file:
                temp_file.write(self.asBytes())
                temp_file.flush()  # Ensure data is written to disk
                self.fname = temp_file.name
                self.fileIsTempCreated = True
                return True
        except Exception as e:
            raise HandledException(f"Error _saveToFile()", e)

    def _doLoadExtendedData(
        self,
    ):
        """Can also update .formatting & .interpretAs based on the content of asProvided (e.g. if it starts with 'hex:')"""
        _txtToReview = None

        caption = self.asCaption(20)
        try:
            _fname = self.getFilename()
            if _fname:
                self._loadFromFile(_fname, caption)

            if (
                (isinstance(self.asData, bytes))
                and self.contentType.isDefault()
                or self.contentType.isTextType()
            ):
                _txtToReview = Utils.asUtf8orBytes(self.asData)

                if not isinstance(_txtToReview, str):
                    return

            elif isinstance(self.asData, str):
                _txtToReview = self.asData
                self.setBaseFormatIfAuto("text")

            if _txtToReview is None:
                return

            self.asData = _txtToReview
            if self.contentType.isDefault():
                self.setBaseFormatIfAuto("text")
            elif self.contentType.isJson():
                try:
                    self.asData = json.loads(_txtToReview)
                except Exception as e:
                    self.warning = f"Unable to parse JSON: {e}"
                    self.contentType.extras["invalid"] = True

            caption = PrettyText.asClipped(_txtToReview, 20)

            if self.sourceType.isValue("hex"):
                hexStr = str(self.asProvidedAfterPrefix)
                try:
                    self.asData = bytes.fromhex(hexStr)
                    self.interpretAs = "hex"
                except Exception as e:
                    self.warning = f"Unable to parse as hex data: {e}"

        except Exception as e:
            errmsg = str(e)
            if not (caption.removeprefix("file:").removesuffix("…") in errmsg):
                errmsg += f" while processing {caption}"
            raise HandledException(f"DataContents[{self.optionalName}]: {errmsg}", e)

    def asBashParam(self) -> str:
        return EscapeMgr.asBashParam(self.asParamTxt(), name_optional=self.optionalName)

    def print_info(self, msg: str):
        appLog.print_info(f"DataContents[{self.optionalName}]: {msg}")

    def print_verbose(self, msg: str):
        appLog.print_verbose(f"DataContents[{self.optionalName}]: {msg}")

    def doReformat(
        self,
        newContentBase: str | None,
        newOptionalSubstitutions: dict[str, Any] | None = None,
    ) -> bool:
        modified = False
        if (
            newOptionalSubstitutions is not None
            and newOptionalSubstitutions != self.optionalSubstitutions
        ):
            if appLog.isVerbose():
                msgOld = deepcopy(self.optionalSubstitutions) or {}
                msgOld.pop("[warning_format]", None)

                msgNew = deepcopy(newOptionalSubstitutions) or {}
                msgNew.pop("[warning_format]", None)

                self.print_verbose(
                    "Reformatting Data contents: Substitutions : "
                    + Utils.asJsonRStr(msgOld)
                    + " → "
                    + Utils.asJsonRStr(msgNew)
                )

            modified = True
            self.optionalSubstitutions = newOptionalSubstitutions

        if (newContentBase) and self.contentType.isValue(newContentBase):

            oldFormatStyle = self.contentType.asDisplayText()
            self.contentType.thisValue = newContentBase
            self.print_verbose(
                f"Reformatting Data contents: Formatting: {oldFormatStyle} -> {self.contentType.asDisplayText()}"
            )
            modified = True

        if not modified:
            self.print_info(f"Reformatting Data contents: Not needed")
            return False
        else:
            self.asFormatted = self._doFormatContents()
            return True

    @staticmethod
    def getComparisonKind(src: Union["DataContents", None]) -> str:
        if src is None:
            return "None"
        elif src.isEmpty():
            return "Empty"
        else:
            return src.contentType.asValueOrDefault()
