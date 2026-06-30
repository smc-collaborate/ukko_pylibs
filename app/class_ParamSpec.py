#########################################################################
#
# app.define- a helper class for command line applications
#             It basically is the 'app.definition'
#
import json
import os
import sys
from typing import Any, Tuple

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import PrettyText
from ukko_pylibs.basic.simpleUtils import EscapeMgr

from ukko_pylibs.basic.class_DataContents import DataContents

#
################################################################################


class ValueHelpSummary:

    def __init__(
        self,
        shortName: str,
        decoratedNamePlusExtras: str,
        defaultInfo: str = "",
        extraInfo: str = "",
        description: str = "",
    ):
        self.shortName = "" if not shortName else f"{shortName},"
        self.decoratedNamePlusExtras = decoratedNamePlusExtras
        self.defaultInfo = defaultInfo
        self.extraInfo = extraInfo
        self.description = "" if not description else f" • {description}"

    def asWrapped(self) -> Tuple[list[str], list[str], list[str], list[str], list[str]]:

        return (
            PrettyText.textWrapWithPrefixes(self.shortName),
            PrettyText.textWrapWithPrefixes(self.decoratedNamePlusExtras, 72),
            PrettyText.textWrapWithPrefixes(self.extraInfo, 72),
            PrettyText.textWrapWithPrefixes(self.defaultInfo),
            PrettyText.textWrapWithPrefixes(self.description, 72),
        )


class ValueHelpSummaries(list[ValueHelpSummary]):
    COLUMNS = range(5)
    MIN_COL0_WIDTH = 3

    def _doReview(self):
        self.maxWidths = [0, 0, 0, 0, 0]
        self.wrapped: list[
            Tuple[list[str], list[str], list[str], list[str], list[str]]
        ] = []

        for entry in self:
            wrappedEntry = entry.asWrapped()
            self.wrapped.append(wrappedEntry)

            for i in self.COLUMNS:
                self.maxWidths[i] = max(
                    self.maxWidths[i], max(map(len, wrappedEntry[i]))
                )

    def _colWidth(self, col: int, withPadding: bool = False) -> int:
        if col < 0 or col >= len(self.maxWidths):
            return 0

        wid = self.maxWidths[col]
        if col == 0 and wid < self.MIN_COL0_WIDTH:
            wid = self.MIN_COL0_WIDTH

        if (wid == 0) and (col > 1):
            return 0

        if withPadding:
            # |if (col == 1):
            # |    wid += 2
            # |else:
            wid += 1
        return wid

    def _asSingleLine(self, cols: list[str]) -> str:

        txt = f"{cols[0]:<{self._colWidth(0)}} {cols[1]:<{self._colWidth(1)}} "  # |x| {' ' if self.maxWidths[1] == 0 else '|'}"

        for n in self.COLUMNS:
            if n <= 1 or (self.maxWidths[n] <= 0):
                continue
            txt += f" {cols[n]:<{self._colWidth(n)}}"
        return txt

    def _cumulativeWidthIncludingPadding(self, colAfterLast: int, colFirst: int = 0):

        result = 0
        for n in range(colFirst, colAfterLast):
            result += self._colWidth(n, withPadding=True)
        return result

    def asLines(self, caption: str) -> list[str]:

        self._doReview()
        results: list[str] = []

        if self.maxWidths[3] > 0:
            col3Caption = "Default"
            self.maxWidths[3] = max(self.maxWidths[3], len(col3Caption))
        else:
            col3Caption = ""
        results.append(
            f"{caption:<{self._cumulativeWidthIncludingPadding(3)}} {col3Caption}"
        )
        for columnsOfWrappedLines in self.wrapped:
            subLine = 0
            while True:
                hasContents = False
                subLineContents = []
                for i in self.COLUMNS:
                    wrappedCol = columnsOfWrappedLines[i]
                    if len(wrappedCol) > subLine:
                        hasContents = True
                        subLineContents.append(wrappedCol[subLine])
                    else:
                        subLineContents.append("")

                if not hasContents:
                    break

                results.append(self._asSingleLine(subLineContents))
                subLine += 1

        return results


class ParamSpec:

    #
    # Fields include:
    #   * mayBeDirect - if the parameter can be passed directly as a value
    #   * default     - the default value for the parameter
    #   * type        - the type of the parameter (int, str, bool)
    #   * lookup      - a dictionary of values for the parameter  (Or a list of permitted values)
    #   * min         - the minimum value for the parameter
    #   * max         - the maximum value for the parameter
    #   * shortName   - a short name for the parameter (single character)
    #   * name        - the name of the parameter
    #   * supportMultiple
    #   * supportEscaping
    #   * mustBeDirect
    #   * hidden

    def __init__(self, spec: dict[str, Any], defaultSupportEscaping: bool = False):
        self.defaultSupportEscaping = defaultSupportEscaping
        self.spec = spec
        self._isEscaped = self._calcIsEscaped(defaultSupportEscaping)

    def isEscaped(self) -> bool:
        return self._isEscaped

    def _calcIsEscaped(self, defaultSupportEscaping: bool) -> bool:
        if not self.type() is str:
            return False

        if not defaultSupportEscaping:
            return self.spec.get("supportEscaping", False)
        else:
            if not self.spec.get("supportEscaping", True):
                return False

            _lookup = self.getLookup()
            if _lookup is None:
                return True

            for x in _lookup if isinstance(_lookup, list) else _lookup.keys():
                if "/" in json.dumps(str(x)):
                    return True

            return False

    def getDescriptions(self) -> dict[str, Any]:
        return self.spec.get("descriptions", {})

    def getSuggestions(self) -> list[str]:
        return self.spec.get("suggestions", [])

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key, default=None):
        return self.spec.get(key, default)

    def asDict(self):
        return self.spec

    def name(self) -> str:
        return str(self.spec.get("name", ""))

    def __contains__(self, item):
        # Define what it means for an item to be "in" the container
        return item in self.spec

    def getLookup(self):
        if "lookup" in self.spec:
            return self.spec["lookup"]
        elif "permitted" in self.spec:
            from ukko_pylibs.app.appSupport import appLog

            appLog.print_warning(
                "Internal note: Spec uses 'permitted' instead of 'lookup' - please update to use 'lookup'"
            )
            return self.spec["permitted"]
        else:
            return None

    def defaultValue(self, withoutEnv: bool = False):
        from ukko_pylibs.app.appSupport import appLog

        if self.spec is None:
            return None

        if not withoutEnv:
            envVarName = self.spec.get("defaultEnvVar", None)

            if envVarName is not None:
                envVarValue = os.environ.get(envVarName, None)
                if envVarValue is not None:
                    value = self.convertArg(
                        envVarValue, returnNoneInsteadOfThrowingError=True
                    )
                    if value is None:
                        appLog.print_warning(
                            f"Param[{self.name()}]: Environment variable ${envVarName}={json.dumps(envVarValue)} not suitable.  Ignored"
                        )
                    else:
                        if not self.spec.get("_notedEnvVarDefault", None):
                            self.spec["_notedEnvVarDefault"] = appLog.print_verbose(
                                f"Param[{self.name()}]: Environment variable ${envVarName}={json.dumps(envVarValue)} used for default"
                            )
                        return value

        if not ("default" in self.spec):
            return None
        else:
            value = self.spec["default"]
            _lookup = self.getLookup()
            if _lookup is not None and isinstance(_lookup, dict) and (value in _lookup):
                value = _lookup[value]
            return value

    def type(self):
        if "type" in self.spec:
            result = self.spec["type"]
            if not isinstance(result, str):
                return self.spec["type"]
            elif result == "int":
                return int
            elif result == "bool":
                return bool
            elif result == "str":
                return str
            else:
                from ukko_pylibs.app.appSupport import appLog

                appLog.print_warning(
                    f"Failed to get type for  {self.spec['name']}={self.spec['type']}"
                )
                return None

        typeOfDefault = type(self.defaultValue())
        if (typeOfDefault is not None) and (typeOfDefault is not type(None)):
            return typeOfDefault

        _lookup = self.getLookup()
        if _lookup is not None:
            if isinstance(_lookup, dict):
                _lookup = _lookup.values()
            if len(_lookup) > 0:
                first_value = next(iter(_lookup))
                if first_value is None:
                    first_value = {}
                return type(first_value)

        return type(None)

    def hasBoolValueForPresence(self):
        return not self.hasValue()

    def hasValue(self):
        return self.type() is not type(None)

    def defaultQuotedTxt(self):
        txt = self._defaultTxt()
        if txt is None:
            txt = ""
        elif (self.type() is DataContents) and txt == "":
            txt = ""
        elif txt == "":
            txt = "''"
        return f"{txt}"

    def _defaultTxt(self) -> str | None:
        if not self.hasValue():
            return None

        if not ("default" in self.spec):
            if ("type" in self.spec) or ("lookup" in self.spec):
                return "••Required••"
            else:
                return ""
        _default = self.defaultValue()
        if (type(_default) is list) and (len(_default) > 0):
            _default = _default[0]
        if _default is None:
            return None
        else:
            return str(_default)

    def isUsable(self) -> bool:
        if self.spec.get("skip", False):
            return False
        return True

    def shortNameWithHyphen(self) -> str:
        if not self.isUsable():
            return ""
        elif "shortName" in self.spec:
            return "" if not self.spec["shortName"] else "-" + self.spec["shortName"]
        elif "name" in self.spec and (len(self.spec["name"]) > 0):
            return "-" + self.spec["name"][0]
        else:
            return ""

    def longNameWithHyphens(self) -> str:
        if not self.isUsable():
            return ""
        elif "name" in self.spec and (len(self.spec["name"]) > 0):
            return "--" + self.spec["name"]
        else:
            return ""

    def matches(self, option: str):
        _shortName = self.shortNameWithHyphen()
        if option == _shortName:
            return True
        if ("name" in self.spec) and (option == "--" + self.spec["name"]):
            return True
        return False

    from enum import Enum

    class InfoStyle(Enum):
        EXPECTED_SENTENCE = 1
        TERSE_SUMMARY = 2

    def getValueHelp(self, style: InfoStyle) -> str:
        result = ""
        _lookup = self.getLookup()
        if _lookup is not None:
            if isinstance(_lookup, dict):
                result = ", ".join(_lookup.keys())
            else:
                result = ", ".join(map(str, _lookup))
            if style == ParamSpec.InfoStyle.TERSE_SUMMARY:
                result = f"{result.replace(' ','').replace(',','/')}"
            elif style == ParamSpec.InfoStyle.EXPECTED_SENTENCE:
                result = f"Expected one of [{result}]"
        elif ("min" in self.spec) or ("max" in self.spec):
            result = f"{self.spec.get('min','')} … {self.spec.get('max','')}"
            if style == ParamSpec.InfoStyle.EXPECTED_SENTENCE:
                result = f"Expected a number in the range of {result}"
            elif style == ParamSpec.InfoStyle.TERSE_SUMMARY:
                result = result.replace(" ", "")
        elif self.type() is DataContents:
            result = "Extended support, including 'file:file.bin', 'hex:12ab' & 'base64:MQ==' "
        elif self.isEscaped():
            result = "Supports escape characters (such as \\n, \\t)"
        return result

    def load(
        self,
        arg: str | int | float | bool,
        currentValue=None,
        returnNoneInsteadOfThrowingError: bool = False,
    ):

        value = self.convertArg(
            arg, returnNoneInsteadOfThrowingError=returnNoneInsteadOfThrowingError
        )

        if not (self.spec.get("supportMultiple", False)):
            return value

        if currentValue is None:
            valueList = []
        elif not isinstance(currentValue, list):
            valueList = [currentValue]
        else:
            valueList = list(currentValue)

        valueList.append(value)

        return valueList

    def convertArg(self, arg, returnNoneInsteadOfThrowingError: bool = False) -> Any:

        def _error(msg: str, e: Exception | None = None):
            if returnNoneInsteadOfThrowingError:
                return None
            else:
                from ukko_pylibs.app.appSupport import error_exit

                error_exit(f"Parameter {_name}: {msg}", e, withSuggestion=True)

        _name = self.spec.get("name", "<Unnamed>")
        _lookup = self.getLookup()
        if _lookup is not None:
            if isinstance(_lookup, dict):
                if arg in _lookup:
                    return _lookup[arg]
                else:
                    return _error(
                        f"{self.getValueHelp(ParamSpec.InfoStyle.EXPECTED_SENTENCE)} -- but is {arg}"
                    )
            elif arg in _lookup:
                return arg
            else:
                #
                # Also support 'count=13' for 'count=<integer>'
                parts = arg.split("=", 1)
                if len(parts) == 2:
                    for humanFormatted in _lookup:
                        if humanFormatted.startswith(parts[0] + "=<"):
                            return arg
            return _error(
                f"{self.getValueHelp(ParamSpec.InfoStyle.EXPECTED_SENTENCE)} -- but is {arg}"
            )

        _type = self.type()

        if _type is type(None):
            if arg is None:
                return True  # Just return True for 'Yes - it is included'
            else:
                return _error(f"No type defined, cannot parse value: '{arg}'")

        if _type == bool:
            if arg.lower() in ("true", "yes", "1"):
                return True
            elif arg.lower() in ("false", "no", "0"):
                return False
            else:
                return _error(f"Expects a boolean value -- but is {arg}")
        elif (_type is int) or (_type is float):
            try:
                if _type is int:
                    value = int(arg)
                else:
                    value = float(arg)
                if "min" in self.spec and value < self.spec["min"]:
                    return _error(
                        f"Must be at least {self.spec['min']} --but is {value}"
                    )
                if "max" in self.spec and value > self.spec["max"]:
                    return _error(
                        f"Must be at most {self.spec['max']} -- but is {value}"
                    )

                return value
            except ValueError:
                return _error(
                    f"Parameter {_name} expects {PrettyText.withAOrAn( _type.__name__)} value -- but is {arg}"
                )
        elif _type is str:
            if self.isEscaped():
                return EscapeMgr.fromEscapedText(arg)
            else:
                return arg
        elif _type is DataContents:
            try:
                return DataContents(
                    arg,
                    formatIn=self.spec.get("format", "default"),
                    optionalNameSuggestion=_name,
                )
            except Exception as e:
                return _error(f"Provided with `{arg}` which gave error", e)
        else:
            return _error(f"Unsupported type: {str(_type)}")

    def mayBeDirect(self) -> bool:
        return (
            self.spec.get("mayBeDirect", False) or self.spec.get("mustBeDirect", False)
        ) and not self.spec.get("hidden", False)

    def getHelpSummary(self) -> ValueHelpSummary | None:
        """Returns: HelpSummary object or None"""
        if (
            self.spec.get("hidden", False)
            or self.spec.get("mustBeDirect", False)
            or self.spec.get("isChosen", False)
        ):
            return None

        ##########
        #
        out_shortName = self.shortNameWithHyphen() or ""

        ##########
        #
        out_decoratedName = "--" + self.name()
        if self.hasValue():
            out_decoratedName += "="
        if "mayBeDirect" in self.spec:
            out_decoratedName += "⁺"

        ##########
        #
        out_defaultTxt = self.defaultQuotedTxt()

        envVarName = self.spec.get("defaultEnvVar", None)
        if envVarName is not None:
            _envNote = f"Env: ${envVarName}"

            envValue = os.environ.get(envVarName, None)
            if envValue is not None:
                _envNote += f"='{envValue}'"

                otherDefault = self.defaultValue(withoutEnv=True)
                if (otherDefault != envValue) and otherDefault is not None:
                    _envNote += f" overwrites {otherDefault}"
                    _envNote = _envNote.removeprefix("Env: ")
            out_defaultTxt = f"{out_defaultTxt} ({_envNote})".strip()

        ##########
        #

        out_terseInfo = self.getValueHelp(ParamSpec.InfoStyle.TERSE_SUMMARY)

        ##########
        #
        _list = self.getSuggestions()
        if _list:
            out_extraInfo = f" Suggestion: {' -or- '.join(map(str, _list))}"
        else:
            out_extraInfo = ""

        ##########
        #
        out_description = str(self.get("description", ""))

        ##########
        #

        return ValueHelpSummary(
            out_shortName,
            out_decoratedName + out_terseInfo,
            out_defaultTxt,
            out_extraInfo,
            out_description,
        )
