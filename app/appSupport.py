#########################################################################
#
# app.define- a helper class for command line applications
#             It basically is the 'app.definition'
#
from copy import deepcopy
import errno
import inspect
import json
import os
import sys
import textwrap
import traceback
from typing import Any, Callable, NoReturn, Tuple

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic import fileUtils
from ukko_pylibs.basic.simpleUtils import Utils
from ukko_pylibs.basic.simpleUtils import DictUtils
from ukko_pylibs.basic.simpleUtils import PrettyText
from ukko_pylibs.basic.simpleUtils import EscapeMgr

from ukko_pylibs.basic.logger import SimpleLogger
from ukko_pylibs.basic.class_HandledException import HandledException

from ukko_pylibs.basic.class_DataContents import DataContents

#
################################################################################


######################################
#
g_appInfo: dict[str, Any] = (
    {}
)  # Global variable to store the app definition & info in used


def appInfo_get(
    name: str | list[str], valueIfNotFoundOrNone: Any | None = None
) -> Any | None:
    global g_appInfo

    _value = DictUtils.get(g_appInfo, name)
    if _value is not None:
        return _value

    if name == "exeFullName":
        if exeInfo_isInstalled():
            # sys.stderr.write(f"ℹ️ℹ️  Installed: {os.environ['PYAPP_INSTALL_SOURCE']}\n")
            _value = os.path.basename(os.environ["PYAPP_INSTALL_SOURCE"])
        else:

            fullname = sys.argv[0]
            # sys.stderr.write(f"ℹ️ℹ️  {fullname}\n")

            if (":" + os.path.dirname(fullname) + ":") in (
                ":" + os.environ["PATH"] + ":"
            ):
                _value = os.path.basename(fullname)
            else:
                _value = Utils.pathDisplay(fullname)
    elif name == "name+version":
        _value = f"{appInfo_get('exeFullName')}"
        suffix = appInfo_get("APP_DEFINITION.version")

        if suffix is not None:
            _value += f" (v{suffix})"

    elif name == "runBasics":
        _value = str(appInfo_get("name+version"))
        _args = sys.argv[1:]
        if len(_args) > 0:
            _value += " args: " + json.dumps(_args)

    if _value is not None:
        DictUtils.set(g_appInfo, name, _value)

    return valueIfNotFoundOrNone if (_value is None) else _value


def appInfo_set(name: str | list[str], value: Any):
    global g_appInfo

    return DictUtils.set(g_appInfo, name, value)


def getExeName() -> str:
    return str(appInfo_get("exeFullName"))


#
###################################


def getMainDir() -> str:

    try:
        import __main__

        return os.path.abspath(__main__.__file__)
    except Exception as e:
        appLog.print_error_withException(e, f"getMainDir() ->defaulting to ~")
        return os.path.expanduser("~")


def exeInfo_isInstalled():
    return "PYAPP_INSTALL_SOURCE" in os.environ


def logger_traditional_set(loggLevel: int):
    import logging

    if loggLevel == SimpleLogger.MsgKind_ERROR:
        logging.getLogger().setLevel(logging.ERROR)
    elif loggLevel == SimpleLogger.MsgKind_WARNING:
        logging.getLogger().setLevel(logging.WARNING)
    elif loggLevel == SimpleLogger.MsgKind_INFO:
        logging.getLogger().setLevel(logging.INFO)
    elif loggLevel == SimpleLogger.MsgKind_DETAIL:
        logging.getLogger().setLevel(logging.DEBUG)
    elif loggLevel == SimpleLogger.MsgKind_TEDIOUS:
        logging.getLogger().setLevel(logging.DEBUG - 1)


appLog = SimpleLogger(getExeName(), onVerbosityThresholdChange=logger_traditional_set)


def isVerbose() -> bool:
    return appLog.isVerbose()


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
            appLog.print_warning(
                "Internal note: Spec uses 'permitted' instead of 'lookup' - please update to use 'lookup'"
            )
            return self.spec["permitted"]
        else:
            return None

    def defaultValue(self, withoutEnv: bool = False):
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

        # |env:x|
        # |env:x|        envVar , envValue, hint= spec._getEnvVarInfo()
        # |env:x|
        # |env:x|
        # |env:x|        _envVarDefault = spec.get("envVarDefault", None)
        # |env:x|        if _envVarDefault is not None:
        # |env:x|            txt = f"{txt:<-20} (If ${_envVarDefault} is set, it would be used as the default value for this option)"
        # |env:x|        else:
        # |env:x|            txt += f"{txt:<-20} (ie: ${_envVarDefault})"
        # |env:x|

        _lookup = self.getLookup()
        if _lookup is not None and not (txt in _lookup):
            txt = "❌ " + txt
        return txt

    def isUsable(self) -> bool:
        if self.spec.get("skip", False):
            return False
        return True

    def shortNameWithHyphen(self) -> str:
        if not self.isUsable():
            return ""
        elif "shortName" in self.spec:
            return "-" + self.spec["shortName"]
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
                result = f"One of [{result}]"
            elif style == ParamSpec.InfoStyle.EXPECTED_SENTENCE:
                result = f"Expected one of [{result}]"
        elif ("min" in self.spec) or ("max" in self.spec):
            result = f"range: {self.spec.get('min','')} .. {self.spec.get('max','')}"
            if style == ParamSpec.InfoStyle.EXPECTED_SENTENCE:
                result = f"Expected a number in the range of {result}"
            elif style == ParamSpec.InfoStyle.TERSE_SUMMARY:
                result = f"Range: {result}"
        elif self.type() is DataContents:
            result = "Extended support, including 'file:file.bin', 'hex:12ab' & 'base64:MQ==' "
        elif self.isEscaped():
            result = "Supports escape characters (such as \\n, \\t)"
        return result

    def load(
        self, arg, currentValue=None, returnNoneInsteadOfThrowingError: bool = False
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


def reviewParams(
    args,
    options_in_: list,
    actionOwner=None,
    limitedExtraParams: int | str | None = None,
    appValue_escapeArguments: bool = False,
):
    returnNoneInsteadOfThrowingError = actionOwner is None
    help_marker = "h"
    options_in: list[ParamSpec] = []
    for _spec in options_in_:
        paramSpec = ParamSpec(_spec, appValue_escapeArguments)
        options_in.append(paramSpec)

        _shortName = paramSpec.shortNameWithHyphen()
        if _shortName == "-h":
            help_marker = "?"

    options_chosen: dict[str, Any] = {}
    non_option_args = []
    force_non_options = False

    loadIntoSpec: ParamSpec | None = None
    spec = None
    arg_cleaned = ""
    giveHelp = False
    for arg in args:
        arg_cleaned = arg.replace("–", "-")
        if loadIntoSpec is not None:
            _name: str = loadIntoSpec.name()
            options_chosen[_name] = loadIntoSpec.load(
                arg_cleaned,
                options_chosen.get(_name, None),
                returnNoneInsteadOfThrowingError,
            )
            loadIntoSpec = None
        elif (arg_cleaned == "--") and not (force_non_options):
            force_non_options = True
        elif arg_cleaned.startswith("-") and not (force_non_options):
            #
            # Process option
            if arg_cleaned in (("-" + help_marker), "--help"):
                giveHelp = True
                returnNoneInsteadOfThrowingError = True
            elif arg_cleaned == "--version":
                if actionOwner is not None:
                    actionOwner.dumpVersion()
                    doHalt("Version Info - Exiting", suggestSilent=True)
                    sys.exit()
            else:
                argMatched = False
                for spec in options_in:
                    _name: str = spec.name()
                    if spec.get("mustBeDirect", False):
                        continue
                    paramSpec_hasValue = spec.hasValue()
                    if spec.matches(arg_cleaned):
                        if not paramSpec_hasValue:
                            options_chosen[_name] = True
                        else:
                            loadIntoSpec = spec

                        argMatched = True
                        break
                    elif paramSpec_hasValue and arg_cleaned.startswith(f"--{_name}="):
                        options_chosen[_name] = spec.load(
                            arg.split("=", 1)[1],
                            options_chosen.get(_name, None),
                            returnNoneInsteadOfThrowingError,
                        )
                        argMatched = True
                        break
                    elif not paramSpec_hasValue and (arg_cleaned == f"--{_name}"):
                        options_chosen[_name] = True
                        argMatched = True
                        break

                if not (argMatched) and not (returnNoneInsteadOfThrowingError):
                    action_suffix = appInfo_get("APP_DEFINITION.post_exe", "")
                    if action_suffix is None or (str(action_suffix).strip() == ""):
                        action_suffix = ""

                    error_exit(f"Unknown{action_suffix} option: {arg}")
        else:
            non_option_args.append(arg)

    if loadIntoSpec is not None:
        error_exit(f"Missing value for option: {arg_cleaned}")

        # |Logging| print_verbose(f"arg: {arg}")

    ##################################################################################################
    # Load non_option_args - either into _options ('mayBeDirect/mustBeDirect') or into 'remaining_args'
    #
    remaining_args = []
    for arg in non_option_args:
        remaining_arg = arg
        for spec in options_in:
            _name: str = spec.name()
            permit_direct = spec.mayBeDirect() and (
                not (_name in options_chosen) or spec.get("supportMultiple", False)
            )
            if permit_direct:
                options_chosen[_name] = spec.load(
                    arg,
                    options_chosen.get(_name, None),
                    returnNoneInsteadOfThrowingError,
                )  # Can be direct parameter
                remaining_arg = None
                break

        if remaining_arg is not None:
            remaining_args.append(remaining_arg)

    if (remaining_args is not None) and (len(remaining_args) > 0):
        if appValue_escapeArguments:
            options_chosen["--"] = [
                EscapeMgr.fromEscapedText(x) for x in remaining_args
            ]
        else:
            options_chosen["--"] = remaining_args

    ################################################
    # Load Defaults for missing _options
    #
    _used_defaults = []
    for spec in options_in:
        _name: str = spec.name()
        if _name not in options_chosen:
            if "default" in spec:
                _used_defaults.append(_name)
                options_chosen[_name] = spec.defaultValue()
            elif spec.type() is type(None):
                # Special case - the existance of it is the value - so if it is included we set it to True (eg: --verbose)
                # but if it is not included, we set it to False
                _used_defaults.append(_name)
                options_chosen[_name] = False
            elif not returnNoneInsteadOfThrowingError:
                valueHelp = spec.getValueHelp(ParamSpec.InfoStyle.EXPECTED_SENTENCE)

                if not spec.get("mustBeDirect", False):
                    prefix = "--" + _name + " "
                elif valueHelp == "":
                    prefix = _name
                else:
                    prefix = ""

                error_exit(f"Missing required parameter: {prefix}{valueHelp}")
    if len(_used_defaults) > 0:
        appLog.print_tediousDetail(f"Used defaults for: {', '.join(_used_defaults)}")

    ################################################
    #
    # Validate extra parameters etc
    #
    appLog.print_tediousDetail(f"argv: " + Utils.asJsonStr(args, indent=2))
    appLog.print_tediousDetail(
        f"AS LOADED: " + Utils.asJsonStr(options_chosen, indent=2)
    )

    if not returnNoneInsteadOfThrowingError and not (limitedExtraParams is None):
        found_count = len(options_chosen.get("--", []))
        if isinstance(limitedExtraParams, str):
            if found_count == 0:
                error_exit(f"Expected {limitedExtraParams}")
        elif found_count != limitedExtraParams:
            txt = (
                "No additional parameters expected"
                if (limitedExtraParams == 0)
                else f"Expected {PrettyText.pluralize(limitedExtraParams, 'additional parameter')}"
            )
            if found_count > 0:
                txt += f"  {found_count}: {','.join(remaining_args)}"
            error_exit(txt)

    appLog.print_tediousDetail(f"AS USED: " + Utils.asJsonStr(options_chosen, indent=2))
    appLog.print_tediousDetail(f"Remaining Arguments: {remaining_args}")

    if actionOwner is not None and hasattr(actionOwner, "choices_made"):
        actionOwner.choices_made["params"] = options_chosen
        actionOwner.choices_made["default_parameters"] = _used_defaults

        appLog.print_tediousDetail(
            f"Choices made: {Utils.asJsonStr(actionOwner.choices_made, indent=2)}"
        )
        appLog.print_tediousDetail(
            f"OptionsAvail: {Utils.asJsonStr(options_in_, indent=2)}"
        )

    if giveHelp:
        if actionOwner is not None:
            actionOwner.giveHelp(sys.stdout)
            doHalt("Help Info Provided - Exiting", suggestSilent=True)
            sys.exit()


# |env:x|
# |env:x|def _fillInOptionsFromEnvVars(appDefinitionsIn: dict[str, Any]):
# |env:x|    specListIn=appDefinitionsIn.get("options",[])
# |env:x|    specListOut=[]
# |env:x|    for spec in specListIn:
# |env:x|        envVar , envValue, hint= _getEnvVarInfo(spec)
# |env:x|        if envVar is not None:
# |env:x|            print(f"!!! {spec} - {envVar}")
# |env:x|
# |env:x|            spec['hint']=hint
# |env:x|            if not envValue is None:
# |env:x|                spec['default']=envValue
# |env:x|
# |env:x|            print(f"specOut: {spec}")
# |env:x|        specListOut.append(spec)
# |env:x|    appDefinitionsIn["options"]=specListOut
# |env:x|    return appDefinitionsIn

g_reviewedParams = {}
g_appDefinition = {}


def getAllParams() -> dict[str, Any]:
    global g_reviewedParams
    return deepcopy(g_reviewedParams)


def getDefinition():
    global g_appDefinition
    return deepcopy(g_appDefinition)


def getValue(name: str, default: Any | None = None) -> Any | None:
    global g_reviewedParams
    if name in g_reviewedParams:
        return g_reviewedParams[name]
    else:
        return default


def getNonDefaultParams() -> dict[str, Any]:
    global g_reviewedParams
    _reviewParams = deepcopy(g_reviewedParams)
    defaultsUsed = _reviewParams.pop("__defaults_used__", [])
    for k in defaultsUsed:
        _reviewParams.pop(k, None)

    return _reviewParams


class Define:
    def getCallbackAndParams(self, args) -> Tuple[Any, dict[str, Any]]:
        params = self.parseParams(args)

        _actionFunction = self.choices_made.get("functionCallback", None)

        if _actionFunction is None:
            error_exit(
                f"No action function found for the given arguments (AppDefinition appears to be incorrectly configured)"
            )

        appLog.print_info(
            f"Running {self.choices_made.get('functionCallback_Reason',None)}"
        )

        return _actionFunction, params

    def _setupVerbosity(self):

        if "options" not in self.app_definition:
            self.app_definition["options"] = []

        entries, default = appLog.get_thresholds()

        _verbositySpec = {
            "name": "verbosity",
            "lookup": entries,
            "default": default,
            "defaultEnvVar": "UKKO_VERBOSITY",
        }

        self.app_definition["options"].insert(0, _verbositySpec)
        # Ensures we get the detailed logging during parameter review
        verbosityArg = None
        for x in sys.argv[1:]:
            if x == "--":
                break
            if x.startswith("--verbosity="):
                ParamSpec(_verbositySpec).load(
                    self.app_definition["options"][0]["default"]
                )
                verbosityArg = x.split("=", 1)[1]
                break

        if verbosityArg is None:
            verbosityArg = ParamSpec(_verbositySpec).defaultValue()
        if verbosityArg is not None:
            appLog.setVerbosity(verbosityArg, silentOnFailure=True)

    def __init__(self, _app_definition: dict[str, Any]):
        self.app_definition = _app_definition
        self._setupVerbosity()
        self.app_definition["runningDir"] = os.getcwd()
        if "version" not in self.app_definition:
            self.app_definition["version"] = "0.0.0"
        if "description" not in self.app_definition:
            self.app_definition["description"] = "No description provided"

        self.choices_made = {}
        self.orig_app_definition = deepcopy(self.app_definition)
        appInfo_set("APP_DEFINITION", deepcopy(self.app_definition))

        config_fname = DictUtils.get(self.app_definition, "config/fname")
        if config_fname is not None:
            config_defaults = deepcopy(
                DictUtils.get(self.app_definition, "config/defaults", {})
            )

            if not config_defaults:
                config_defaults = {}

            settings = DictUtils.getDict(self.app_definition, "settings", {})

            for key, value in settings.items():
                if "default" in value:
                    DictUtils.set(config_defaults, ["settings", key], value["default"])
                    DictUtils.get(settings, [key, "default"])

            config_init(config_fname, config_defaults)

    def giveHelp(self, file_dest=sys.stdout):
        for x in self.getHelp():
            file_dest.write(x.rstrip() + "\n")
        printVerbose_sysInfo()

    def getHelp(self) -> list[str]:

        lines_out: list[str] = []

        exeName = getExeName()
        exeNameDecorated = self.getExeName_decorated()
        # |Logging| try:
        # |Logging|     print(Utils.asJsonStr(self.app_definition, indent=2))
        # |Logging| except:
        # |Logging|     print(self.app_definition)

        extra_params = self.app_definition.get("additional_parameters", 0)

        param_info = ""
        directPrefixes = []
        extra_msg = ""
        #
        # parameter spec contains:
        #   * mayBeDirect - if the parameter can be passed directly as a value
        #   * default     - the default value for the parameter
        #   * type        - the type of the parameter (int, str, bool)
        #   * lookup      - a dictionary of values for the parameter  (Or a list of permitted values)
        #   * min         - the minimum value for the parameter
        #   * max         - the maximum value for the parameter
        #   * shortName   - a short name for the parameter (single character)
        #   * name        - the name of the parameter
        #   * supportMultiple
        #   * mayBeDirect
        #   * mustBeDirect
        #   * hidden
        for _spec in self.app_definition["options"]:
            paramSpec = ParamSpec(
                _spec, self.app_definition.get("escapeArguments", False)
            )
            _name = paramSpec.name()

            if paramSpec.get("hidden", False) or paramSpec.get("isChosen", False):
                continue
            if paramSpec.get("mustBeDirect", False):
                if "descriptions" in paramSpec:
                    for name, value in paramSpec.getDescriptions().items():
                        directPrefixes.append({"name": name, "description": value})
                elif paramSpec.type() is list or paramSpec.get(
                    "supportMultiple", False
                ):
                    param_info += f"[{_name}...] "
                else:
                    param_info += f"[{_name}] "

            elif paramSpec.get("mayBeDirect", False):
                if paramSpec.type() is list:
                    param_info += f"[{_name}⁺...] "
                else:
                    param_info += f"[{_name}⁺] "

                extra_msg = "Options marked with ⁺ may be passed directly, without the option name"

        if isinstance(extra_params, str):
            param_info += " -- " + extra_params
        elif extra_params is None:
            param_info += " [--] [param] .. [param]"
        elif extra_params > 0:
            param_info += " [--] [param] " * (extra_params)

        handled_help_and_version = False
        params_txt = f"[options] {param_info}".strip()
        verText = f"v{self.app_definition['version']}"
        if len(directPrefixes) == 0:
            lines_out.append(
                f"{exeNameDecorated:<32} {verText:<13} - {str(self.app_definition.get('description','')):<90}"
            )
            lines_out.append("")
            lines_out.append(f"Usage: {exeNameDecorated} {params_txt}")
        else:
            prefix = "Usage: "
            directPrefixes.append({"blankLine": True})
            directPrefixes.append(
                {
                    "name": "<action> --help",
                    "options": False,
                    "description": "Gives help information on the action (From the above list)",
                }
            )

            directPrefixes.append(
                {
                    "name": "--version",
                    "options": False,
                    "description": "Gives version information for this app: " + verText,
                    "noDecoration": True,
                }
            )

            handled_help_and_version = True

            maxLen = 30
            for _entry in directPrefixes:
                if not _entry.get("blankLine", False):
                    _name = _entry.get("name", "")
                    exeNameToUse = (
                        exeName
                        if _entry.get("noDecoration", False)
                        else exeNameDecorated
                    )
                    _entry["nameToUse"] = exeNameToUse + " " + _name
                    _len = len(_entry["nameToUse"])
                    if _len > maxLen:
                        maxLen = _len
            extrasLen = len(params_txt)
            lines_out.append(
                f"{' '*len(prefix)} {exeNameDecorated:<{maxLen}} {' '*extrasLen} | {str(self.app_definition.get('description','')):<90}"
            )
            lines_out.append("")
            for _entry in directPrefixes:
                if _entry.get("blankLine", False):
                    lines_out.append("")
                else:
                    _nameToUse = _entry.get("nameToUse", "")
                    _value = _entry.get("description", "")
                    includeOptions = _entry.get("options", True)

                    _params_out = (
                        params_txt if includeOptions else ""
                    )  # (' '*len(params_txt))

                    if _value == "":
                        suffix = ""
                    else:
                        suffix = " | " + _value

                    lines_out.append(
                        f"{prefix} {_nameToUse:<{maxLen}} {_params_out:<{extrasLen}}{suffix}"
                    )
                    prefix = " " * len(prefix)

        lines_out.append("")

        outLines = []
        if True:
            help_marker = "h"
            hasDefaults = False
            for _spec in self.app_definition["options"]:
                spec = ParamSpec(
                    _spec, self.app_definition.get("escapeArguments", False)
                )
                cols = ["    ", ""]
                if (
                    spec.get("hidden", False)
                    or spec.get("mustBeDirect", False)
                    or spec.get("isChosen", False)
                ):
                    continue
                _shortName = ParamSpec.shortNameWithHyphen(spec)
                if _shortName is None:
                    cols[0] += f" {'':<3}"
                else:
                    cols[0] += f"{_shortName:<3}"
                    if _shortName == "-h":
                        help_marker = "?"

                decorated_name = spec.name()
                if spec.hasValue():
                    decorated_name += "="
                if "mayBeDirect" in spec:
                    decorated_name += "⁺"

                cols[0] += f" | --{decorated_name:<20}"

                cols[1] = (
                    f"{ParamSpec.defaultQuotedTxt(spec):<20}".replace(" ", "\xa0") + " "
                )

                txt_ = ParamSpec.getValueHelp(spec, ParamSpec.InfoStyle.TERSE_SUMMARY)
                _list = spec.getSuggestions()
                if _list:
                    txt_ += f" Suggestion: {' -or- '.join(map(str, _list))}"

                envVarName = spec.get("defaultEnvVar", None)
                if envVarName is not None:
                    _envNote = f"Env: ${envVarName}"

                    envValue = os.environ.get(envVarName, None)
                    if envValue is not None:
                        _envNote += f"='{envValue}'"

                        otherDefault = spec.defaultValue(withoutEnv=True)
                        if (otherDefault != envValue) and otherDefault is not None:
                            _envNote += f" overwrites {otherDefault}"
                            _envNote = _envNote.removeprefix("Env: ")
                    txt_ += f" ({_envNote})"

                MAX_WIDTH_HERE = 72
                if len(txt_) >= MAX_WIDTH_HERE:

                    for prefix in ("One of [", " Suggestion: "):
                        if txt_.startswith(prefix):
                            cols[1] += prefix
                            txt_ = txt_[len(prefix) :]
                            break

                    parts = textwrap.wrap(txt_, width=MAX_WIDTH_HERE)
                    last_part = parts.pop()
                    hasDefaults = True
                    for part in parts:
                        outLines.append([cols[0], cols[1] + part])
                        cols[0] = " " * len(cols[0])
                        cols[1] = "\xa0" * len(cols[1])

                    cols[1] += last_part
                else:
                    cols[1] += txt_
                cols[1] = cols[1].strip(" \t")

                if cols[1] != "":
                    hasDefaults = True
                outLines.append(cols)

            if not (handled_help_and_version):
                outLines.append([f"    -{help_marker}  | --help", ""])
                outLines.append(["        | --version", ""])

        if len(outLines) > 0:
            headerLine = ["Options:", "Default" if hasDefaults else ""]
            if len(directPrefixes) >= 2:
                headerLine[0] = "Common options:"
            outLines.insert(0, headerLine)
            for cols in outLines:
                _txt = str(cols[1]).strip(" \t")
                lines_out.append(f"{cols[0]:<32}    {_txt}".replace("\xa0", " "))
            if extra_msg != "":
                lines_out.append(f"{extra_msg}")

        if self.app_definition.get("examples", None):
            lines_out.append("")
            lines_out.append("Examples:")
            for s in self.app_definition["examples"]:
                txt = exeName.join(s.split("<exeName>"))
                txt = exeNameDecorated.join(txt.split("<exeName+action>"))
                lines_out.append(f" • {txt}")
        lines_out.append("")

        return lines_out

    def getExeName_decorated(self, decorated=True):
        txt = exeInfo_getName()
        if decorated:
            txt += self.app_definition.get("post_exe", "")
        return txt

    def dumpVersion(self, includeAuthor: bool = False):
        txt = f"{getExeName():<32} v{self.app_definition['version']:<10} {str(self.app_definition.get('description','')):<104}"

        if includeAuthor and ("author" in self.app_definition):
            txt += f" | {self.app_definition['author']}"

        sys.stdout.write(f"{txt.strip()}\n")

        extras = self.app_definition.get("versions_extra", [])

        for line in extras:
            sys.stdout.write(f"{'':<32}  {'':<10} {str(line)}\n")

    def parseParams(self, args: list[str] | None = None) -> dict[str, Any]:
        self.app_definition = deepcopy(self.orig_app_definition)
        ####################################
        #

        chosenActions = []
        options_in = self.app_definition.get("options", [])
        nextActionOptions = None
        options_out = []
        nonOptionArgs = []
        addAll = False
        if args is None:
            args = sys.argv[1:]
        for arg in args:
            if not arg.startswith("-") or addAll:
                nonOptionArgs.append(arg)
            elif arg == "--":
                addAll = True
        nonOptionArgsIndex = 0

        for x in options_in:
            _customisations = x.get("customising", None)
            is_customising_entry = (_customisations is not None) and (
                isinstance(_customisations, dict)
            )

            if not is_customising_entry:
                options_out.append(x)
            else:
                if nextActionOptions is None:
                    nextActionOptions = _customisations
                    x["usage"] = "next"
                extra_options = []
                x["mustBeDirect"] = True
                _customisations = x.get("customising", None)

                if nonOptionArgsIndex < len(nonOptionArgs):

                    chosenAction = nonOptionArgs[nonOptionArgsIndex].strip()

                    if chosenAction in _customisations:
                        chosenActions.append(chosenAction)
                        nextActionOptions = None
                        x["isChosen"] = True
                        x["usage"] = "isChosen"
                        _func_callback = _customisations[chosenAction].get(
                            "_func_callback", None
                        )
                        if _func_callback is not None:
                            self.choices_made["functionCallback"] = _func_callback
                            self.choices_made["functionCallback_Reason"] = "+".join(
                                chosenActions
                            )
                        actionInfo = _customisations[chosenAction]
                        self.app_definition["post_exe"] = (
                            self.app_definition.get("post_exe", "") + " " + chosenAction
                        )

                        extra_options = actionInfo.get("options", [])
                        if "description" in actionInfo:
                            self.app_definition["description"] += (
                                " - " + actionInfo["description"]
                            )
                        if "examples" in actionInfo:
                            if not isinstance(
                                self.app_definition.get("examples", None), list
                            ):
                                self.app_definition["examples"] = []
                            self.app_definition["examples"] += actionInfo["examples"]

                action_descriptions = {}
                action_keys = list(_customisations.keys())

                for key in _customisations:
                    action_descriptions[key] = _customisations[key].get(
                        "description", ""
                    )
                x["descriptions"] = action_descriptions
                x["lookup"] = action_keys
                x["mustBeDirect"] = True
                if x.get("usage", None) is not None:
                    options_out.append(x)
                    options_out += extra_options

            if x.get("mustBeDirect", False) or x.get("mayBeDirect", False):
                nonOptionArgsIndex += 1

        self.choices_made["customisedChoicesMade"] = chosenActions
        self.choices_made["customisedChoicesNext"] = nextActionOptions

        self.app_definition["options"] = options_out

        ######################################
        #
        # Basic parameter review
        reviewParams(
            args,
            self.app_definition["options"],
            self,
            self.app_definition.get("additional_parameters", 0),
            self.app_definition.get("escapeArguments", False),
        )

        _params = deepcopy(self.choices_made["params"])
        _params["__defaults_used__"] = self.choices_made.get("default_parameters", [])

        global g_reviewedParams
        g_reviewedParams = _params
        return _params

    def option_usedDefault(self, name):
        """
        Check if the option is set to its default value.
        :param name: The name of the option to check.
        :return: True if the option was omitted - forcing the deault value to be used
        """
        return name in self.choices_made.get("default_parameters", [])

    def option_isDefault(self, name):
        """
        Check if the option is set to its default value.
        :param name: The name of the option to check.
        :return: True if the option is set to its default value, False otherwise.
        """
        if self.option_usedDefault(name):
            return True
        _value = self.choices_made.get("chosen_parameters", {}).get(name, None)
        if _value is None:
            return False
        return _value == ParamSpec.defaultValue(
            self.app_definition["options"].get(name)
        )


################################
def groupCreate(name: str, defaultValue: str | None = None) -> dict[str, Any]:
    obj = {"name": name, "customising": {}, "mustBeDirect": True}

    if defaultValue is not None:
        obj["defaultValue"] = defaultValue

    return obj


def groupEntry(
    description: str,
    funcCallback,
    _options: list | None = None,
    examples: list | None = None,
):
    obj: dict[str, Any] = {"description": description, "_func_callback": funcCallback}
    if _options is not None:
        obj["options"] = _options
    if examples is not None:
        obj["examples"] = examples
    return obj


g_appIsRunning = True


def isRunning() -> bool:
    global g_appIsRunning
    return g_appIsRunning


def doHalt(msg: str | None = None, suggestSilent: bool = False):
    global g_appIsRunning
    if g_appIsRunning:
        g_appIsRunning = False
        appLog.print_verbose(f"Halting {'' if msg is None else (' -- '+msg)}")
    else:
        appLog.print_tediousDetail(
            f"Confirm Halted {'' if msg is None else (' -- '+msg)}"
        )


def doExit(defaultExitCode: int | None = None) -> NoReturn:
    doHalt()
    if defaultExitCode is not None and defaultExitCode != 0:
        exitCode = defaultExitCode
    else:
        exitCode = 1 if appLog.had_error() else 0
    sys.exit(exitCode)


def doRun(callable: Callable[[], None]):
    try:
        callable()
        doExit()
    except BaseException as e:
        exitOnException(e)


def printVerbose_sysInfo():
    if appLog.isVerbose():
        lines: list[str] = []
        for key, value in sys.modules.items():
            txt = str(value)
            if ".venv" in txt:
                continue
            if txt.endswith("built-in)>"):
                continue
            if txt.endswith("(frozen)>"):
                continue
            if "from '/usr" in txt:
                continue
            if "<class 'typing." in txt:
                continue
            lines.append(f" * [{key:<30}]={txt}")

        appLog.print_verbose(f"Python version: {sys.version}")
        appLog.print_verbose(f"Platform: {sys.platform}")
        appLog.print_verbose(f"Executable: {sys.executable}")
        appLog.print_verbose(f"Current working directory: {os.getcwd()}")
        appLog.print_tediousDetail(f"Modules:\n" + "\n".join(lines))


def getExceptionInfo(giveMinorInfoEvenIfNotVerbose: bool = False) -> list[str]:

    traceLines = traceback.format_exception(sys.exception())

    if appLog.isVerbose():
        return traceLines
    elif not (giveMinorInfoEvenIfNotVerbose):
        return []
    else:
        review = []
        for line in traceLines[-2:-1]:
            review += line.split("\n")

        results = []
        for line in review:
            if not (line.strip().startswith('File "')):
                results.append(line)

        results.append("Use '--verbosity=detailed' for more information")
        return results


def exitOnException(e: BaseException, action: str | None = None) -> NoReturn:

    # |Logging| sys.stderr.write(f"\n⚠️  {type(e)}:{e} {e}\n")
    """
    Exit the program with an error message if an exception occurs.
    :param ex: The exception that occurred
    :param msg: Custom error message to display
    """
    suggestion: bool | str = False
    isHandled = isinstance(e, HandledException)
    if action is None:
        action = str(e)
        if not isHandled:
            action = "Unhandled[" + action + "]"
        emsgSuffix = ""
    else:
        emsgSuffix = f" {e}"

    if isinstance(e, IOError):
        if e.errno == errno.EPIPE:
            # This is expected if the output is piped to another command
            sys.stderr.write(f"\n⚠️  Piping output - Halted")
            doHalt("Piping output - Halted")
            exit(1)
        else:
            error_exit(f"{action}: IOError{emsgSuffix}")
    elif isinstance(e, KeyboardInterrupt):
        sys.stderr.write(f"\n⚠️  Keyboard Interrupt - Exiting\n")
        doHalt("Keyboard Interrupt - Exiting")
        sys.exit(2)
    elif isinstance(e, SystemExit):
        # sys.stderr.write(f"\n⚠️  Exiting with code: {e.code}\n")
        doHalt("System Exit - Exiting")
        sys.exit(e.code)
    else:
        if not isinstance(suggestion, str):
            suggestion = "\n".join(getExceptionInfo(not isHandled))
        error_exit(f"{action}{emsgSuffix}", withSuggestion=suggestion)


def returnJsonData(resultFull: Any, elementNameIfNotFull: str | None = None):
    outputFormat = getValue("output-format", None)
    if outputFormat is None:
        isJson = getValue("json", None)
        if isJson is not None:
            outputFormat = "json" if isJson else "text"

    if outputFormat is None:
        appLog.print_warning(f"Unspecified 'output format' : defaulting to json")
        outputFormat = "json"
    else:
        appLog.print_info(f"Output format: {outputFormat}")

    if outputFormat == "json-full":
        if elementNameIfNotFull:
            resultFull["_elementName"] = elementNameIfNotFull
        print(Utils.asJsonStr(resultFull, indent=2))
    else:

        resultPart = (
            DictUtils.get(resultFull, elementNameIfNotFull, type(None))
            if elementNameIfNotFull is not None
            else resultFull
        )

        if resultPart is type(None):
            appLog.print_error(f"Element '{elementNameIfNotFull}' not found")
            resultPart = resultFull
        else:
            appLog.print_info(f"Output full: {Utils.asJsonStr(resultFull, indent=2)}")

        if outputFormat == "json":
            print(Utils.asJsonStr(resultPart, indent=2))
        elif outputFormat == "text":
            if isinstance(resultPart, list):
                for x in resultPart:
                    print(str(x))
            elif isinstance(resultPart, dict):
                print(Utils.asJsonStr(resultPart, indent=2))
            else:
                print(str(resultPart))
        else:
            appLog.print_error(f"Unknown output format: {outputFormat}")
            print(Utils.asJsonStr(resultPart, indent=2))

    exitCode = DictUtils.get(resultFull, "exitCode", None)
    if exitCode is None:
        exitCode = 0 if isinstance(resultFull, dict) else 0
        success = DictUtils.get(resultFull, "success", None)
        if success == False:
            exitCode = 1
    doExit(exitCode)


def error_exit(
    msg: str, exception: Exception | None = None, withSuggestion: bool | str = True
) -> NoReturn:
    # print_verbose(f"error_exit: {msg} | withSuggestion={withSuggestion}")

    if exception is not None:
        msg += f" | Exception: {str(exception)}"
    if withSuggestion:
        if isinstance(withSuggestion, str):
            extraLines = withSuggestion
        else:
            exe_action = getExeName()
            exe_suffix = appInfo_get("APP_DEFINITION.post_exe", "")
            if exe_suffix is not None and str(exe_suffix).strip() != "":
                exe_action += str(exe_suffix)
            extraLines = f"Suggest: {exe_action} --help"

        msg += "\n" + extraLines

    appLog.print_error(msg, noPrefix=True)

    printVerbose_sysInfo()
    doHalt("Exiting with error")
    sys.exit(1)


def doExitWithCode() -> NoReturn:
    printVerbose_sysInfo()

    if appLog.had_error():
        doHalt("Exiting: Had Error")
        sys.exit(1)
    else:
        doHalt("Exiting: No Error", suggestSilent=True)
        sys.exit(0)


def exeInfo_getName():
    """
    Returns the name of the executable, without the path.
    :return: The name of the executable.
    """
    return os.path.basename(getExeName())


def exeInfo_doUninstall():
    if exeInfo_isInstalled():
        sys.stderr.write(
            f"ℹ️  Uninstalling {exeInfo_getName()} from {os.environ['PYAPP_INSTALL_SOURCE']}\n"
        )
        try:
            os.remove(os.environ["PYAPP_INSTALL_SOURCE"])
            appLog.print_verbose(f"Uninstalled {exeInfo_getName()}")
            doHalt("Uninstall Complete - Exiting")

            sys.exit(0)
        except Exception as e:
            error_exit(f"Unable to uninstall {exeInfo_getName()}: {e}")
    return "PYAPP_INSTALL_SOURCE" in os.environ


class JsonEncoderExtended(json.JSONEncoder):
    def default(self, o):
        return o.__dict__


def exec_cmd(
    cmd: list[str], caption: str | None = None, haltOnError: bool = True
) -> Tuple[int, bytes, bytes, str]:
    """Returns (returncode, stdout, stderr, failureMsg)"""
    import subprocess

    cmd_txt = " ".join(cmd)
    if caption is None:
        caption = f"Executing {cmd_txt}"

    appLog.print_verbose(f"Executing command: {caption}")

    returnValue: Tuple[int, bytes, bytes, str] = (-1, b"", b"", "Not started")

    try:
        if (cmd is None) or (len(cmd) == 0):
            raise ValueError("No command specified")
        result = subprocess.run(cmd, check=False, capture_output=True, text=False)
        returnValue = (result.returncode, result.stdout, result.stderr, "")
    except subprocess.CalledProcessError as e:
        returnValue = (e.returncode, e.stdout, e.stderr, f"CalledProcessError({e})")
    except FileNotFoundError:
        returnValue = (
            -1,
            b"",
            b"",
            "Command not found. Check your OS and command name.",
        )
    except Exception as e:
        appLog.print_error(
            f"Unable to call command {cmd}. Exception: {e}", isFatal=haltOnError
        )
        returnValue = (-1, b"", b"", f"Exception: {e}")

    if returnValue[1]:
        if len(returnValue[1]) > 100:
            appLog.print_verbose(f" • STDOUT: {len(returnValue[1])} bytes ...")
        else:
            appLog.print_verbose(
                f" • STDOUT: {returnValue[1].decode('utf-8', errors='replace')}"
            )

    if returnValue[2]:
        if len(returnValue[2]) > 2000:
            appLog.print_verbose(f" • STDERR: {len(returnValue[2])} bytes ...")
        else:
            appLog.print_verbose(
                f" • STDERR: {returnValue[2].decode('utf-8', errors='replace')}"
            )
    if returnValue[0] == 0:
        appLog.print_verbose(f" • Return code: Ok")
    elif returnValue[0] > 0:
        if haltOnError:
            appLog.print_error(f" • Return code: {returnValue[0]}", isFatal=True)
        else:
            appLog.print_verbose(f" • Return code: {returnValue[0]}")

    failureMsg = returnValue[3]
    if failureMsg != "":
        appLog.print_error(
            f"Command {cmd_txt} failed: {failureMsg}", isFatal=haltOnError
        )

    return returnValue


def loadBinaryFile_orHandledException(
    inputBinaryFilename: str | None,
    jParams_filePath: str | None = None,
    inputJsonParams: dict[str, Any] | None = None,
) -> bytes | None:

    inputBinaryRefDir = None

    updateFilename = True
    if (inputBinaryFilename == "") and (
        isinstance(inputJsonParams, dict) and ("_filename" in inputJsonParams)
    ):  #'inputBinaryFile' in params['__default_used__']):
        inputBinaryFilename = inputJsonParams.get("_filename", None)
        updateFilename = False

    if (inputBinaryFilename is None) or (inputBinaryFilename == ""):
        # appLog.print_verbose(f"Omitting inputBinaryFile")
        return None

    appLog.print_verbose(f"Using inputBinaryFile: {inputBinaryFilename}")
    if jParams_filePath is not None:
        inputBinaryRefDir = os.path.dirname(jParams_filePath)

    if not os.path.isabs(inputBinaryFilename):
        if inputBinaryRefDir is not None:
            inputBinaryFilename = os.path.join(inputBinaryRefDir, inputBinaryFilename)
            appLog.print_verbose(
                f"Resolving inputBinaryFile to absolute path: {inputBinaryFilename}"
            )
        else:
            inputBinaryFilename = os.path.join(os.getcwd(), inputBinaryFilename)
            appLog.print_verbose(
                f"A relative path is provided for the inputBinaryFile - it will be relative to '{os.getcwd()}'"
            )

    if updateFilename and (inputJsonParams is not None):
        inputJsonParams["_filename"] = inputBinaryFilename

    return fileUtils.loadBytesFromFile_orHandledException(inputBinaryFilename)


def appDir(defaultDir: str = ".") -> str:
    """
    Get the application directory, which is the directory of the main module.
    """

    appModule = sys.modules["__main__"]
    _filename = str(getattr(appModule, "__file__", ""))

    reason = ""
    if _filename:
        appDir = os.path.dirname(_filename)
        reason = "mainModuleFile.dir"
    else:
        appDir = defaultDir
        reason = "defaultDir"

    dirFromDef = appInfo_get("APP_DEFINITION.app_dir", None)
    if dirFromDef is not None:
        appDir = dirFromDef
        reason = "app_dir from definition"

    appLog.print_verbose(f"App directory: {appDir} (Reason: {reason})")
    return appDir


def getDir(subDirName: str = "") -> str:
    """
    Get the application directory with an optional subdirectory.
    """

    def _getDirIfExists(baseDir: str, subDirName: str) -> str | None:
        subdir = os.path.realpath(os.path.join(baseDir, subDirName))
        if os.path.exists(subdir):
            return subdir
        return None

    dirPath = appInfo_get(f"APP_DEFINITION.{subDirName}_dir", None)
    if dirPath is not None:
        reason = f"{subDirName}_dir from definition"
    else:
        basePath = appDir()
        dirPath = None
        reason = f"No {subDirName} found - Using default"
        for entry in ("./", "../", "../../"):
            dirPath = _getDirIfExists(basePath, entry + subDirName)
            if dirPath is not None:
                reason = f"Found {subDirName} in {entry} relative to appDir"
                break
        if dirPath is None:
            dirPath = f"{basePath}/"

    appLog.print_verbose(f"Dir[{subDirName}]= {dirPath} (Reason: {reason})")
    return dirPath


def deprecationWarning(message: str):
    try:
        msg = f"Deprecation Warning: {message}"
        stack_lines = []
        if not appLog.isVerbose():
            msg += " (Use --verbosity=detailed for details)"
        else:
            caller_frame = inspect.stack().copy()[
                2:
            ]  # Skip the first two frames (current function and its caller)
            top_frame = True
            for x in caller_frame:
                stack_lines.insert(
                    0,
                    f"{'└── ' if top_frame else '│   '} {('' if x.code_context is None else x.code_context[0].strip()):<120} | {x.filename.split('/')[-1]:<30} : {x.lineno}",
                )
                top_frame = False
        appLog.print_warning(msg + "\n" + ("\n".join(stack_lines)))
    except Exception as e:
        appLog.print_warning(
            f"Deprecation Warning: {message} (Also failed to get caller info: {e})"
        )


CONFIG_DEFAULTS = {}
CONFIG_LOADED = {}
CONFIG_USED = CONFIG_LOADED.copy()


def config_loadFromFile(configPath: str):
    global CONFIG_LOADED
    try:
        with open(configPath, "r", encoding="utf-8") as f:
            CONFIG_LOADED = json.load(f)
    except Exception as e:
        print(f"⚠️  Warning: Unable to load config file '{configPath}': {e}")
        CONFIG_LOADED = {}


def _recursive_merge(dict1: dict, dict2: dict) -> dict:
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _recursive_merge(result[key], value)
        else:
            result[key] = value
    return result


def config_init(config_fname: str | None, defaults: dict[str, Any] | None = None):
    global CONFIG_LOADED
    global CONFIG_USED
    global CONFIG_DEFAULTS

    if defaults is not None:
        CONFIG_DEFAULTS = defaults
    if config_fname is not None:
        config_loadFromFile(config_fname)

    CONFIG_USED = _recursive_merge(CONFIG_DEFAULTS, CONFIG_LOADED)


def config_get(key: str | list[str] = "") -> Any:
    global CONFIG_USED
    global CONFIG_DEFAULTS

    if key == "":
        return CONFIG_USED

    result = DictUtils.get(CONFIG_USED, key, None)
    if result is None:
        appLog.print_error(
            f"Config key '{key}' not found - nor found in CONFIG_DEFAULTS"
        )
    return result


def setting_get_default(key: str) -> Any:
    global CONFIG_DEFAULTS

    result = DictUtils.get(CONFIG_DEFAULTS, "settings/" + key, "!!NOT_FOUND!!")

    if result == "!!NOT_FOUND!!":
        if not key.startswith("!"):
            appLog.print_error(f"Default setting for key '{key}' not found")
        result = None

    return result


def setting_set_int(
    key: str, value: str | int, minValue: int | None = None, maxValue: int | None = None
):

    if not key.startswith("!"):

        defaultValue = setting_get_default(key)

        if (defaultValue is not None) and (not isinstance(defaultValue, int)):
            appLog.print_error(
                f"Default setting for key '{key}' is {defaultValue}: Not an integer"
            )

        if not isinstance(value, int):
            try:
                value = int(value)
            except Exception as e:
                appLog.print_warning(
                    f"Setting[{key}]={value} is not an integer - Using default {defaultValue}"
                )
                return
        if (minValue is not None) and (value < minValue):
            appLog.print_warning(
                f"Setting[{key}] : Clipping {value} to minimum {minValue}"
            )
            value = minValue

        if (maxValue is not None) and (value > maxValue):
            appLog.print_warning(
                f"Setting[{key}] : Clipping {value} to maximum {maxValue}"
            )
            value = maxValue

    global CONFIG_USED
    CONFIG_USED["settings"][key] = value


def setting_set_bool(key: str, value: str | bool):

    defaultValue = setting_get_default(key)

    if (defaultValue is not None) and (not isinstance(defaultValue, bool)):
        appLog.print_warning(
            f"Default setting for key '{key}' is {defaultValue}: Not boolean"
        )

    if not isinstance(value, bool):
        try:
            value = bool(value)
        except Exception as e:
            appLog.print_warning(
                f"Setting[{key}]={value} is not a boolean - Using default {defaultValue}"
            )
            return

    global CONFIG_USED
    CONFIG_USED["settings"][key] = value


def setting_get(key: str) -> Any:
    global CONFIG_USED
    global CONFIG_DEFAULTS

    configKey = "settings/" + key
    result = DictUtils.get(CONFIG_USED, configKey, None)
    if key.startswith("!"):
        return result

    if result is None:
        appLog.print_error(f"Setting '{key}' not found - nor found in CONFIG_DEFAULTS")
    else:

        defaultValue = setting_get_default(key)
        expectedType = type(defaultValue)
        if not isinstance(result, expectedType):
            appLog.print_warning(
                f"Type mismatch for setting '{key}': expected {expectedType}, got {type(result)}"
            )

    return result


def setting_get_bool(key: str, defaultOnUtterFailure: bool = False) -> Any:
    value = setting_get(key)

    type_default = type(defaultOnUtterFailure)
    if value is None:
        return defaultOnUtterFailure  # < Error already noted
    elif isinstance(value, type_default):
        return value
    else:
        appLog.print_error(f"Setting[{key}] = {value} : Expected {type_default}")
        return defaultOnUtterFailure


def setting_get_int(key: str, defaultOnUtterFailure: int = 0) -> Any:

    value = setting_get(key)

    type_default = type(defaultOnUtterFailure)
    if value is None:
        return defaultOnUtterFailure  # < Error already noted
    elif isinstance(value, type_default):
        return value
    elif not key.startswith("!"):
        appLog.print_error(f"Setting[{key}] = {value} : Expected {type_default}")
        return defaultOnUtterFailure
    else:
        return defaultOnUtterFailure
