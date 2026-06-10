import json
import json
import os
import sys
from typing import Any, NoReturn, Tuple
import tempfile

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)


from ukko_pylibs.basic.simpleUtils import Utils
from ukko_pylibs.basic.simpleUtils import DictUtils
from ukko_pylibs.basic.simpleUtils import PrettyText
from ukko_pylibs.basic.simpleUtils import EscapeMgr

import ukko_pylibs.basic.simpleUtils as simpleUtils
from ukko_pylibs.basic.class_HandledException import HandledException


#
################################################################################

CLIP_LENGTH = 80


class DataContents:
    def __init__(
        self,
        value: Any,
        formatIn: str = "default",
        optionalNameSuggestion: str | None = None,
        srcDirect: str | None = None,
    ):
        self.optionalName = optionalNameSuggestion or ""
        self.nameSuggestedPrefix = (
            (optionalNameSuggestion + "_") if optionalNameSuggestion else "data_"
        )
        self._srcDirect = srcDirect
        self.warning: str | None = None
        if isinstance(value, DataContents):
            self.asProvided: Any = value.asProvided
            self.asData: Any = value.asData
            self.fname: str = value.fname
            self.fileIsTempCreated: bool | None = value.fileIsTempCreated
            self.interpretAs: str = value.interpretAs
            self.asObj: Any | None = value.asObj

            if formatIn == "default":
                self.format = value.format
                self.asFormatted: Any = value.asFormatted
            else:
                self.format = formatIn
                self.asFormatted: Any = self._doFormatContents()
        else:
            self.asProvided: Any = value
            self.asData: Any = (
                (value) if srcDirect else EscapeMgr.fromEscapedText(value)
            )
            self.fname: str = ""
            self.fileIsTempCreated: bool | None = None
            self.interpretAs: str = ""
            self.asObj: Any | None = None
            self.format = formatIn
            self._doLoadExtendedData()  # < Can modify .interpretAs & .format
            self.asFormatted: Any = self._doFormatContents()

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
        else:
            resultTxt = "⚠️" + str(self.asProvided)
            simpleUtils.print_warning(
                f"DataContents.asParamText(): {self.asData} (type: {type(self.asData)})"
            )
            simpleUtils.print_info("-----")
            simpleUtils.print_info(f"asParamTxt: {resultTxt}")
            simpleUtils.print_info(f"asProvided: {self.asProvided}")
            simpleUtils.print_info("-----")

        return resultTxt

    def asDict(self) -> dict[str, Any]:
        out = {
            "warning": self.warning,
            "asProvided": self.asProvided,
            "asFormatted": self.asFormatted,
            "asObj": self.asObj,
            "asData": self.asData,
            "interpretAs": self.interpretAs,
            "format": self.format,
            "fname": self.fname,
        }

        cleaned = DictUtils.getWithDefaultValuesRemoved(
            out,
            {
                "warning": None,
                "interpretAs": "",
                "format": "default",
                "fname": "",
                "fileIsTempCreated": None,
                "asObj": None,
                "asFormatted": self.asData,
                "asProvided": self.asData,
            },
        )

        return cleaned

    def getFormat(self, default: str = "default") -> str:
        return self.format if self.format != "default" else default

    def isTextFormat(self):
        return self.getFormat() in ["txt", "json"]

    def asTextLines(self) -> list[str]:
        if isinstance(self.asFormatted, str):
            return self.asFormatted.splitlines()
        elif isinstance(self.asFormatted, list):
            out = []

            for x in self.asFormatted:
                out += str(x).splitlines()
            return out
        else:
            return [f"[{type(self.asFormatted)}]{self.asFormatted}"]

    def getDisplayText(self, name: str) -> str:

        _paramText = str(self.asProvided)
        if self.asProvided != "" and isinstance(self.asProvided, str):
            _prefix, _fname = self.getProvidedFilenamePlus()

            if _fname != "":
                _paramText = _prefix + Utils.pathDisplay(_fname)

        if _paramText == "":
            return name
        else:
            return f"{name}:{PrettyText.asClipped(_paramText, CLIP_LENGTH, formatter=EscapeMgr.asEscapedText)}"

    def isEmpty(self) -> bool:
        return (
            self.asData == ""
            or self.asData == []
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

        if not self.fname:
            pass
        elif summaryTxt:
            summaryTxt = self.fname + "  " + summaryTxt
        else:
            summaryTxt = self.fname

        return self.format + ": " + summaryTxt

    def _doFormatContents(self):

        outData = self.asData
        if self.format == "json":
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
        return str(outData).split("\n")

    def getSuggestedFormat(self) -> str:
        fname_suffix = self.fname.lower().removesuffix(".ref")
        if fname_suffix.endswith(".md") or fname_suffix.endswith(".txt"):
            return "txt"
        elif fname_suffix.endswith(".json"):
            return "json"
        elif fname_suffix.endswith(".bin"):
            return "bin"
        else:
            return "default"

    def _loadFromFile(self, fname: str, caption: str) -> Any:
        self.fname = fname
        self.fileIsTempCreated = False

        if self.format == "default":
            self.format = self.getSuggestedFormat()
        try:
            with open(fname, "r+b") as f:
                self.asData = f.read()
        except Exception as e:
            raise HandledException(f"Error reading file {fname}", e)

    def doErrorExit(self, msg: str, e: Exception | None = None) -> NoReturn:
        import ukko_pylibs.app.appSupport as app

        msg = f"DataContents -- {msg}"
        if e is not None:
            app.error_exit(msg, e)
        else:
            app.error_exit(msg)

    def asBytes(self) -> bytes:
        if isinstance(self.asData, bytes):
            return self.asData
        elif isinstance(self.asData, str):
            return self.asData.encode("utf-8")
        else:
            raise ValueError(
                f"Cannot convert asData of type {type(self.asData)} to bytes"
            )

    def exportToFileIfNeeded(self) -> bool:
        if self.fname:
            return True  # Already saved

        if self.asData is None:
            return False
        try:
            with tempfile.NamedTemporaryFile(
                mode="w+b",
                suffix="." + self.getFormat("output"),
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

    def getProvidedFilenamePlus(self) -> Tuple[str, str]:
        """Returns a tuple of (prefix, filename) if the asProvided value indicates a file reference, otherwise ['','']"""
        if isinstance(self.asProvided, str):
            prefixes = ["file:", "@"]
            for prefix in prefixes:
                if self.asProvided.startswith(prefix):
                    return prefix, self.asProvided.removeprefix(prefix)
        return ("", "")

    def _doLoadExtendedData(
        self,
    ):
        """Can also update .format & .interpretAs based on the content of asProvided (e.g. if it starts with 'hex:')"""
        _txtToReview = None

        caption = PrettyText.asClipped(self.asProvided, 20)
        try:
            _prefix, _fname = self.getProvidedFilenamePlus()
            if _fname:
                self._loadFromFile(_fname, caption)

            if (isinstance(self.asData, bytes)) and self.format in [
                "default",
                "txt",
                "json",
            ]:
                _txtToReview = Utils.asUtf8orBytes(self.asData)
                if not isinstance(_txtToReview, str):
                    return

            elif isinstance(self.asData, str):
                _txtToReview = self.asData
                if self.format == "default":
                    self.format = "txt"

            if _txtToReview is None:
                return

            self.asData = _txtToReview
            if self.format == "default":
                self.format = "txt"
            elif self.format == "json":
                try:
                    self.asObj = json.loads(_txtToReview)
                except Exception as e:
                    self.warning = f"Unable to parse JSON: {e}"
                    self.format = "json-invalid"

            caption = PrettyText.asClipped(_txtToReview, 20)

            if _txtToReview.startswith("hex:"):
                hexStr = _txtToReview.removeprefix("hex:")
                try:
                    self.asData = bytes.fromhex(hexStr)
                    self.format = "bin"
                    self.interpretAs = "hex"
                except Exception as e:
                    self.warning = f"Unable to parse as hex data: {e}"

        except Exception as e:
            raise HandledException(
                f"DataContents[{self.optionalName}]: {e} processing {caption}", e
            )
