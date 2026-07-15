#########################################################################
#
# app.define- a helper class for command line applications
#             It basically is the 'app.definition'
#
import json
import os
import sys
from types import NoneType
from typing import Any, Tuple

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.class_HandledException import HandledException
from ukko_pylibs.basic.simpleUtils import PrettyText, EscapeMgr, Utils
from ukko_pylibs.basic.logger import appLog
from ukko_pylibs.basic.class_DataContents import DataContents

import ukko_pylibs.basic.styling as styling

#
################################################################################


class ValueHelpSummary:

    Columns = Tuple[list[str], list[str], list[str], list[str], list[str]]

    def __init__(
        self,
        group: str,
        shortName: str,
        decoratedNamePlusExtras: str,
        defaultInfo: str = "",
        extraInfo: str = "",
        description: str = "",
        summaryAdd_param: str = "",
        summaryAdd_directPrefixes: list[dict[str, str]] | None = None,
    ):
        self.group = group
        self.shortName = shortName  # "" if not shortName else f"{shortName},"
        self.decoratedNamePlusExtras = decoratedNamePlusExtras
        self.defaultInfo = defaultInfo
        self.extraInfo = extraInfo
        self.description = description  # "" if not description else f" • {description}"
        self.summaryAdd_param = summaryAdd_param
        self.summaryAdd_directPrefixes = summaryAdd_directPrefixes or []

    def clone(self) -> "ValueHelpSummary":
        return ValueHelpSummary(
            self.group,
            self.shortName,
            self.decoratedNamePlusExtras,
            self.defaultInfo,
            self.extraInfo,
            self.description,
            self.summaryAdd_param,
            list(self.summaryAdd_directPrefixes),
        )

    def asDict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "namePlus": self.decoratedNamePlusExtras,
            "group": self.group,
        }

        if self.shortName:
            result["shortName"] = self.shortName
        result["description"] = self.description
        if self.extraInfo:
            result["extraInfo"] = self.extraInfo
        if self.defaultInfo:
            result["defaultInfo"] = self.defaultInfo
        if self.summaryAdd_param:
            result["summaryAdd_param"] = self.summaryAdd_param
        if self.summaryAdd_directPrefixes:
            result["summaryAdd_directPrefixes"] = self.summaryAdd_directPrefixes

        return result

    def asWrapped(self) -> "ValueHelpSummary.Columns":
        return (
            PrettyText.textWrapWithPrefixes(self.shortName),
            PrettyText.textWrapWithPrefixes(
                self.decoratedNamePlusExtras,
                50,
            ),
            PrettyText.textWrapWithPrefixes(self.extraInfo, 72),
            PrettyText.textWrapWithPrefixes(self.defaultInfo),
            PrettyText.textWrapWithPrefixes(self.description, 102, [" • "]),
        )


class ParamSpec:

    #
    # Fields include:
    #   * name            - the name of the parameter
    #   * shortName       - a short name for the parameter (single character)
    #   * default         - the default value for the parameter
    #   * type            - the type of the parameter (int, str, bool)
    #   * lookup          - a dictionary of values for the parameter  (Or a list of permitted values)
    #   * min             - the minimum value for the parameter
    #   * max             - the maximum value for the parameter
    #
    # Used more rarely:
    #   * supportMultiple - The parameter is returned as an array of the multiple values
    #   * mayBeDirect     - The parameter optionally can be passed directly as a value
    #   * mustBeDirect    - The parameter MUST be passed directly as a value
    #   * hidden          - The parameter is hidden
    #

    def __init__(self, spec: dict[str, Any], defaultSupportEscaping: bool = False):
        self.defaultSupportEscaping = defaultSupportEscaping
        self.spec = spec
        self._isEscaped = self._calcIsEscaped(defaultSupportEscaping)

    def __clone__(self) -> "ParamSpec":
        return ParamSpec(self.spec, self.defaultSupportEscaping)

    def _calcIsEscaped(self, defaultSupportEscaping: bool) -> bool:
        if not self.type_orNone() is str:
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
        # print("self.asDict():" + Utils.asJsonStr(self.spec, indent=2))
        return self.spec

    def name(self) -> str:
        return str(self.spec.get("name", ""))

    def __contains__(self, item):
        # Define what it means for an item to be "in" the container
        return item in self.spec

    def getLookup(self) -> dict[str, Any] | list[str] | None:
        if "lookup" in self.spec:
            return self.spec["lookup"]
        elif "permitted" in self.spec:
            appLog.deprecationWarning(
                "Spec uses 'permitted' instead of 'lookup' - please update to use 'lookup'"
            )
            return self.spec["permitted"]
        else:
            return None

    def defaultValue_orNoneType(
        self, withoutEnv: bool = False, withoutLookup: bool = False
    ) -> Any | NoneType:

        if self.spec is None:
            return NoneType

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
            return NoneType
        else:
            value = self.spec["default"]
            if not withoutLookup:
                _lookup = self.getLookup()
                if (
                    _lookup is not None
                    and isinstance(_lookup, dict)
                    and (value in _lookup)
                ):
                    value = _lookup[value]
            return value

    def type_orNone(self):
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
                appLog.print_warning(
                    f"Failed to get type for  {self.spec['name']}={self.spec['type']}"
                )
                return None

        _defValue = self.defaultValue_orNoneType()
        if _defValue is not NoneType:
            return type(_defValue)

        _lookup = self.getLookup()
        if _lookup is not None:
            if isinstance(_lookup, dict):
                _lookup = _lookup.values()
            if len(_lookup) > 0:
                first_value = next(iter(_lookup))
                if first_value is None:
                    first_value = {}
                return type(first_value)

        return None

    def hasBoolValueForPresence(self):
        return not self.hasValue()

    def hasValue(self):
        return self.type_orNone() is not None

    def defaultQuotedTxt(self):
        txt = self._defaultTxt()
        if txt is None:
            txt = ""
        elif (self.type_orNone() is DataContents) and txt == "":
            txt = ""
        elif txt == "":
            txt = "''"
        return f"{txt}"

    def _defaultTxt(self, requiredMarker: str = "••Required••") -> str | None:
        if not self.hasValue():
            return None

        _defValue = self.defaultValue_orNoneType(withoutLookup=True)
        if _defValue is NoneType:
            if "type" in self.spec:
                return requiredMarker
            else:
                return ""
        if (type(_defValue) is list) and (len(_defValue) > 0):
            _defValue = _defValue[0]
        if _defValue is None:
            return None
        else:
            return str(_defValue)

    #######################################
    #
    def isUsable(self) -> bool:
        if self.spec.get("skip", False):
            return False
        return True

    def isNotHidden(self) -> bool:
        return not self.spec.get("hidden", False) and self.isUsable()

    def isCustomising(self) -> bool:
        return (self.spec.get("customising", None) is not None) and self.isNotHidden()

    def isEscaped(self) -> bool:
        return self._isEscaped

    #
    #######################################

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

    def getMatchedValue(self, arg: str) -> tuple[bool, str | None]:
        """matched, value"""
        for _prefix in [self.longNameWithHyphens(), self.shortNameWithHyphen()]:
            if _prefix:
                if arg == _prefix:
                    return (True, None if self.hasValue() else "true")
                if self.hasValue() and arg.startswith(f"{_prefix}="):
                    return (True, arg.split("=", 1)[1])
        return (False, None)

    from enum import Enum

    class InfoStyle(Enum):
        EXPECTED_SENTENCE = 1
        TERSE_SUMMARY = (2,)
        PARAM_FORMAT_OR_EXAMPLE = (3,)

    def getValueHelp(self, style: InfoStyle, noExample: bool = False) -> str:
        result = ""

        if style == ParamSpec.InfoStyle.PARAM_FORMAT_OR_EXAMPLE:
            exampleOrNone = self.getExample()
            if exampleOrNone is not None:
                return self.getParamFormat()
            else:
                return (
                    self.getValueHelp(ParamSpec.InfoStyle.EXPECTED_SENTENCE)
                    or self.getParamFormat()
                )

        _lookup = self.getLookup()
        if _lookup is not None:
            _values = list(_lookup.keys()) if isinstance(_lookup, dict) else _lookup
            if style == ParamSpec.InfoStyle.TERSE_SUMMARY:
                result = styling.asOption(_values)
            elif style == ParamSpec.InfoStyle.EXPECTED_SENTENCE:
                result = f"Expected one of [{styling.asSuggestionList(_values)}]"
        elif ("min" in self.spec) or ("max" in self.spec):
            result = f"{self.spec.get('min','')} … {self.spec.get('max','')}"
            if style == ParamSpec.InfoStyle.EXPECTED_SENTENCE:
                result = f"Expected a number in the range of {result}"
            elif style == ParamSpec.InfoStyle.TERSE_SUMMARY:
                result = result.replace(" ", "")

        if style == ParamSpec.InfoStyle.EXPECTED_SENTENCE and not noExample:
            example = self.getExample()
            if example is not None:
                result += (
                    f"{self.getParamFormat()} (eg: {EscapeMgr.asBashParam(example)})"
                )

        return result.strip()

    EXTRA_HELP_SUBSCRIPTS = {
        "⁺": "may be passed directly, without the option name",
        "ⁿ": "support escape characters (such as \\n, \\t)",
        "ꟳ": "support inputs such as 'file:file.bin', 'hex:12ab' & 'base64:MQ==' as well as escape characters",
    }

    def getValueHelpSubscripts(self) -> str:
        """Returns a tuple of (annotation, description) for extra info about the parameter's value."""
        result = ""

        if self.type_orNone() is DataContents:
            result += "ꟳ"
        elif self.isEscaped():
            result += "ⁿ"
        if self.mayBeDirect():
            result += "⁺"
        return styling.asBold(result)

    @staticmethod
    def getValueHelpExtraInfoFromSubscripts(txt: str) -> list[str]:
        """Returns a list of the extra info characters found in the given text."""
        result = []

        for key, help in ParamSpec.EXTRA_HELP_SUBSCRIPTS.items():
            if key in txt:
                result.append(f" • Options marked with {styling.asBold(key)} {help}")

        if len(result) > 0:
            result.insert(0, "Parameter Notes:")
            result.insert(0, "")
        return result

    def getExample(self) -> Any | None:
        return self.spec.get("example", None)

    def getParamFormat(self) -> str:
        if "paramFormat" in self.spec:
            return self.spec["paramFormat"]
        elif "name" in self.spec:
            return self.spec["name"]
        else:
            return ""

    def convertArg_orGiveHelp(self, arg) -> tuple[Any | None, str | None]:
        valueOrNone = self.convertArg(arg, True)
        if valueOrNone is None:
            return None, self.getValueHelp(ParamSpec.InfoStyle.EXPECTED_SENTENCE)
        else:
            return valueOrNone, None

    def _convertArg(self, arg) -> Tuple[Any, str | None]:
        """Returns value/None and error info if any (msg, exception, errorWithSuggestion)"""

        def _error(
            msg: str, e: Exception | None = None, but_is_this_value: Any | None = None
        ):
            if but_is_this_value is not None:
                msg += f" -- but is {styling.asError(but_is_this_value)}"
            if isinstance(e, HandledException):
                msg += f"\nCaused by: {styling.asError(e.origMsg)}"
            elif e is not None:
                msg += f"\nCaused by: {styling.asError(str(e))}"
            return None, f"Parameter {_name}: {msg}"

        _name = self.spec.get("name", "<Unnamed>")
        _lookup = self.getLookup()
        if _lookup is not None:
            if isinstance(_lookup, dict):
                if arg in _lookup:
                    return _lookup[arg], None
                else:
                    return _error(
                        f"{self.getValueHelp(ParamSpec.InfoStyle.EXPECTED_SENTENCE)}",
                        but_is_this_value=arg,
                    )
            elif arg in _lookup:
                return arg, None
            else:
                #
                # Also support 'count=13' for 'count=<integer>'
                parts = arg.split("=", 1)
                if len(parts) == 2:
                    for humanFormatted in _lookup:
                        if humanFormatted.startswith(parts[0] + "=<"):
                            return arg, None
            return _error(
                f"{self.getValueHelp(ParamSpec.InfoStyle.EXPECTED_SENTENCE)}",
                but_is_this_value=arg,
            )

        _type = self.type_orNone()

        if _type is None:
            if arg is None:
                return True, None  # Just return True for 'Yes - it is included'

            _result = Utils.toBool(arg)
            if _result is not None:
                return _result, None
            else:
                return _error(
                    f"Expects a boolean presence value", but_is_this_value=arg
                )

        if _type == bool:
            _result = Utils.toBool(arg)
            if _result is not None:
                return _result, None
            else:
                return _error(f"Expects a boolean value", but_is_this_value=arg)
        elif (_type is int) or (_type is float):
            try:
                if _type is int:
                    value = int(arg)
                else:
                    value = float(arg)
                if "min" in self.spec and value < self.spec["min"]:
                    return _error(
                        f"Must be at least {self.spec['min']}", but_is_this_value=value
                    )
                if "max" in self.spec and value > self.spec["max"]:
                    return _error(
                        f"Must be at most {self.spec['max']}", but_is_this_value=value
                    )

                return value, None
            except ValueError:
                return _error(
                    f"Parameter {_name} expects {PrettyText.withAOrAn( _type.__name__)} value",
                    but_is_this_value=arg,
                )
        elif _type is str:
            if self.isEscaped():
                return EscapeMgr.fromEscapedText(arg), None
            else:
                return arg, None
        elif _type is DataContents:
            try:
                return (
                    DataContents(
                        arg,
                        formatIn=self.spec.get("format", "default"),
                        optionalNameSuggestion=_name,
                    ),
                    None,
                )
            except Exception as e:
                return _error(f"Provided with `{arg}` which gave an error", e)
        else:
            return _error(f"Unsupported type: {str(_type)}")

    def convertArg(self, arg, returnNoneInsteadOfThrowingError: bool = False) -> Any:
        _value, _errorInfo = self._convertArg(arg)

        if _errorInfo is None or (returnNoneInsteadOfThrowingError):
            return _value
        else:
            raise HandledException(_errorInfo)

    def getHelpSummary(self) -> ValueHelpSummary | None:
        """Returns: HelpSummary object or None"""
        if self.spec.get("hidden", False) or self.spec.get("isChosen", None):
            return None

        _name = self.name()
        _formattedName = (
            f"{self.get('paramFormat', _name)}{self.getValueHelpSubscripts()}"
        )
        if self.type_orNone() is list or self.get("supportMultiple", None):
            _formattedName += " …"

        ##########
        #
        if self.mustBeDirect():
            out_shortName = ""
        else:
            out_shortName = self.shortNameWithHyphen() or ""

        ##########
        #
        if self.mustBeDirect():
            out_decoratedName = f"[{_formattedName}]"

        else:
            out_decoratedName = "--" + self.name()
            out_decoratedName += self.getValueHelpSubscripts()
            if self.hasValue():
                out_decoratedName += "="

        ##########
        #
        out_defaultTxt = self.defaultQuotedTxt()

        envVarName = self.spec.get("defaultEnvVar", None)
        _envNote = ""
        if envVarName:
            _envNote = f" -- Can also be set with ${envVarName}"

            envValue = os.environ.get(envVarName, None)
            if envValue is not None:
                _envNote += f"={EscapeMgr.escapeIfNeeded(envValue)}"

                otherDefault = self.defaultValue_orNoneType(withoutEnv=True)
                if (otherDefault != envValue) and otherDefault is not NoneType:
                    _envNote += f" (overwrites {otherDefault})"

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
        out_description = f"{self.get('description', '')} {_envNote}".strip()

        ##########
        #
        summaryAdd_param = ""
        summaryAdd_directPrefixes = []

        if self.get("mustBeDirect", None):
            if "descriptions" in self.spec:
                for name, value in self.getDescriptions().items():
                    summaryAdd_directPrefixes.append(
                        {"name": name, "description": value}
                    )
            else:
                summaryAdd_param = f"[{_formattedName}] "
        elif self.get("mayBeDirect", None):
            summaryAdd_param = f"[{_formattedName}] "

        ##########
        #

        return ValueHelpSummary(
            str(self.spec.get("group", None) or ""),
            out_shortName,
            out_decoratedName + out_terseInfo,
            out_defaultTxt,
            out_extraInfo,
            out_description,
            summaryAdd_param=summaryAdd_param,
            summaryAdd_directPrefixes=summaryAdd_directPrefixes,
        )

    def cheatPeekAtValue_orNoneType(
        self, args: list[str] | None = None
    ) -> Any | NoneType:
        # This is a cheat function to peek at the value of a parameter from the command line arguments.
        # It is not intended for normal use, but can be useful for debugging or testing.
        # Limitations:
        #   * It only supports parameters that have a name and are not hidden or mustBeDirect.
        #   * Only the full name is supported (e.g. --param=value), not the short name (e.g. -p value).
        #   * It returns the first matching value it finds, and does not support multiple values for the same parameter.
        #
        arg = NoneType
        if args is None:
            args = sys.argv[1:]
        for x in args:
            if x == "--":
                break
            if x == "--" + self.name():
                arg = True
                break
            elif x.startswith("--" + self.name() + "="):
                arg = self.convertArg(
                    x.split("=", 1)[1], returnNoneInsteadOfThrowingError=True
                )
                break

        return arg if arg is not NoneType else self.defaultValue_orNoneType()

    def mustBeDirect(self) -> bool:
        return self.spec.get("mustBeDirect", False)

    def mayBeUsedDirectly(self) -> bool:
        # Don't include the 'isCustomising()' element as that is used quite differently
        return not self.isCustomising() and (
            (self.spec.get("mayBeDirect", False)) or self.mustBeDirect()
        )

    def mayBeDirect(self) -> bool:
        return (self.spec.get("mayBeDirect", False)) and self.isNotHidden()


class ParamSpecAndValue:
    def __init__(
        self,
        spec: ParamSpec,
        value: Any | list[Any] | None = None,
        convert: str | None = None,
    ):
        self.spec = spec.__clone__()
        self.value = value
        self.errorNotes: list[str] = []
        if convert is not None:
            self.value = self.load_withConvert(convert)

    def throwIfErrorNotes(self):
        if self.errorNotes:
            raise Exception(self.errorNotes[0])

    def name(self) -> str:
        return self.spec.name()

    def asDict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"name": self.name(), "spec": self.spec.asDict()}
        if self.value is not None:
            result["value"] = self.value
        if self.errorNotes:
            result["errorNotes"] = self.errorNotes
        return result

    def load_withConvert(self, arg: str) -> str | None:
        errmsg: str | None = None
        _value, _errorNote = self.spec._convertArg(arg)

        if _errorNote is not None:
            self.errorNotes.append(_errorNote)
        elif not (self.spec.get("supportMultiple", False)):
            if self.value is None:
                self.value = _value

            elif not self.errorNotes:

                self.errorNotes.append(
                    f"Parameter {self.spec.name()} does not support multiple values, but was provided with multiple values: {self.value} and {arg}"
                )
        else:
            if self.value is None or not isinstance(self.value, list):
                self.value = []
            self.value.append(_value)

        return errmsg


class ParamSpecList(list[ParamSpec]):
    def __init__(
        self,
        specs: list[dict[str, Any]] | None = None,
        group: str = "",
        escapeArguments: bool = False,
    ):
        super().__init__()
        for _spec in specs or []:
            spec = ParamSpec(_spec, escapeArguments)
            self.append(spec)

    def doFilterByAttr(self, attr) -> "ParamSpecList":
        result = ParamSpecList()
        for spec in self:
            if getattr(spec, attr)():
                result.append(spec)
        return result

    def get(self, name: str) -> ParamSpec | None:
        for spec in self:
            if spec.name() == name:
                return spec
        return None

    def cheatPeekAtValue_orNoneType(self, name: str) -> Any | NoneType:
        spec = self.get(name)
        return NoneType if spec is None else spec.cheatPeekAtValue_orNoneType()

    def containsShortName(self, shortName: str) -> bool:
        for spec in self:
            if spec.shortNameWithHyphen() == shortName:
                return True
        return False

    def getMatchedSpecAndValue(self, arg: str) -> tuple[ParamSpec | None, str | None]:
        for spec in self:
            if not spec.get("mustBeDirect", False):
                argMatched, _value = spec.getMatchedValue(arg)
                if argMatched:
                    return spec, _value
        return None, None


class ValueHelpSummaries(list[ValueHelpSummary]):
    COLUMNS = range(5)
    MIN_COL0_WIDTH = 3

    def appendItem(
        self,
        groupCaption: str,
        item: ValueHelpSummary | ParamSpec | dict[str, Any] | None,
    ):
        if item is None:
            return

        if isinstance(item, dict):
            item = ParamSpec(item)
        if isinstance(item, ParamSpec):
            item = item.getHelpSummary()

        if item is not None:
            item_out = item.clone()
            item_out.group = groupCaption
            self.append(item_out)

    def _doReview(self):
        self.maxWidths = [0, 0, 0, 0, 0]
        self.groupPlusWrapped: list[Tuple[str, ValueHelpSummary.Columns]] = []

        for entry in self:
            wrappedEntry = entry.asWrapped()
            self.groupPlusWrapped.append((entry.group, wrappedEntry))

            for i in self.COLUMNS:
                self.maxWidths[i] = max(
                    self.maxWidths[i],
                    max(map(PrettyText.uniLen_approx, wrappedEntry[i])),
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
            if col > 0:
                wid += 1
        return wid

    def _asSingleLine(self, cols: list[str]) -> str:

        if cols[0] != "":
            cols[0] += ","
        txt = f"{PrettyText.padToWidth(cols[0], self._colWidth(0))}{PrettyText.padToWidth(cols[1], self._colWidth(1))}"

        for n in self.COLUMNS:
            if n <= 1 or (self.maxWidths[n] <= 0):
                continue
            txt += f" {PrettyText.padToWidth(cols[n], self._colWidth(n))}"
        return txt

    def getDividerLine(self, horizontalChar: str = "─", verticalChar: str = "┼") -> str:
        line = ""
        for width in self.maxWidths:
            if width > 0:
                if line != "":
                    line += verticalChar
                line += horizontalChar * width
        return line

    def _cumulativeWidthIncludingPadding(self, colAfterLast: int, colFirst: int = 0):

        result = 0
        for n in range(colFirst, colAfterLast):
            result += self._colWidth(n, withPadding=True)
        return result

    def maxLenOfGroupCol(self, group: str, column: int) -> int:
        return max(
            [
                len("".join(y[column]))
                for _group, y in self.groupPlusWrapped
                if _group == group
            ]
        )

    def asLines(self) -> list[str]:

        self._doReview()
        results: list[str] = []

        if self.maxWidths[3] > 0:
            col3Caption = "Default"
            self.maxWidths[3] = max(
                self.maxWidths[3], PrettyText.uniLen_approx(col3Caption)
            )
        else:
            col3Caption = ""

        prevGroup: str | None = None
        for group, columnsOfWrappedLines in self.groupPlusWrapped:
            if group != prevGroup:
                if prevGroup is not None:
                    results.append("")

                titleLine = "   " + styling.asUnderline(group)

                if self.maxLenOfGroupCol(group, 3) > 0:
                    titleLine += " " * (
                        self._cumulativeWidthIncludingPadding(3)
                        - PrettyText.uniLen_approx(titleLine)
                    ) + styling.asUnderline(col3Caption)
                    # col3Caption='' #< If we want this only on the topmost line
                results.append(titleLine)

                # |For experiments|results.append(f"{self.getDividerLine()} ! {self.maxWidths}")
                prevGroup = group

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

    @staticmethod
    def createFromDescriptions(
        specs: list[dict[str, Any]] = [],
        group: str = "",
        escapeArguments: bool = False,
        includeMustBeDirect: bool = False,
    ) -> "ValueHelpSummaries":
        return ValueHelpSummaries.createFromParamSpecList(
            ParamSpecList(specs, group, escapeArguments), includeMustBeDirect
        )

    @staticmethod
    def createFromParamSpecList(
        paramSpecList: "ParamSpecList", includeMustBeDirect: bool = False
    ) -> "ValueHelpSummaries":
        result = ValueHelpSummaries()
        for spec in paramSpecList:
            if not spec.mustBeDirect() or includeMustBeDirect:
                pairOrNone = spec.getHelpSummary()
                if pairOrNone is not None:
                    result.append(pairOrNone)
        return result

    def findByShortName(self, shortName: str) -> ValueHelpSummary | None:
        for entry in self:
            if entry.shortName == shortName:
                return entry
        return None
