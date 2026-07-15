#########################################################################
#
# app.define- a helper class for command line applications
#             It basically is the 'app.definition'
#
from copy import deepcopy
import errno
import json
import os
import sys
from typing import Any, Callable, NoReturn, Tuple
from types import NoneType

from ukko_pylibs.basic.class_DataContents import DataContents

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic import fileUtils
from ukko_pylibs.basic.simpleUtils import (
    PrettyTable,
    Utils,
    PrettyText,
    EscapeMgr,
    DictUtils,
)
from ukko_pylibs.basic.logger import appLog
from ukko_pylibs.basic.class_HandledException import (
    HandledException,
    getPrettyExceptionInfo,
)
from ukko_pylibs.basic import styling
from ukko_pylibs.app.class_Configuration import Configuration
from ukko_pylibs.app.class_ParamSpec import (
    ParamSpec,
    ParamSpecAndValue,
    ParamSpecList,
    ValueHelpSummaries,
)

#
################################################################################


app = sys.modules[__name__]

######################################
#
g_appInfo: dict[str, Any] = (
    {}
)  # Global variable to store the app definition & info in used


def appInfo_getStr(name: str | list[str], valueIfNotFoundOrNone: str = "") -> str:
    _value = appInfo_get(name, valueIfNotFoundOrNone)
    return str(_value) if _value is not None else valueIfNotFoundOrNone


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
    elif name == "name+actions":
        _value = (
            appInfo_getStr("exeFullName") + appInfo_getStr("APP_AS_USED.post_exe")
        ).strip()
    elif name == "name+params":
        _value = (
            appInfo_getStr("exeFullName")
            + " "
            + appInfo_getStr("APP_AS_USED.allParams")
        ).strip()
    elif name == "name+version":
        _value = appInfo_getStr("exeFullName")
        suffix = appInfo_getStr("APP_DEFINITION.version")

        if suffix:
            _value += f" (v{suffix.removeprefix('v')})"

    elif name == "runBasics":
        _value = appInfo_getStr("name+version")
        _args = sys.argv[1:]
        if len(_args) > 0:
            _value += " args: " + json.dumps(_args)

    if _value is not None:
        DictUtils.set(g_appInfo, name, _value)

    return valueIfNotFoundOrNone if (_value is None) else _value


def appInfo_set(name: str | list[str], value: Any):
    global g_appInfo
    return DictUtils.set(g_appInfo, name, value)


def appInfo_appendStr(
    name: str | list[str], valueToAppend: str, withSpace: bool = True
):
    oldValue = appInfo_getStr(name, "")
    if withSpace and oldValue != "" and valueToAppend != "":
        appInfo_set(name, oldValue + " " + valueToAppend)
    else:
        appInfo_set(name, oldValue + valueToAppend)


def appInfo_cmdWithVariant(spec: ParamSpec | None, value: Any) -> str:

    # return f"{appInfo_getStr("name+actions")} {valuePrefixOrBlank}{paramValue}"

    oldParams: list = appInfo_get(
        "APP_AS_USED.paramsArray", []
    )  # pyright: ignore[reportAssignmentType]

    newList: list[Any] = [appInfo_getStr("exeFullName")]

    if spec is None:
        newList.extend(oldParams)
    elif spec.get("mustBeDirect"):
        newList.extend(oldParams)
        if str(value).startswith("-") and not ("--" in newList):
            newList.append("--")

        newList.append(str(value))
    else:
        if spec.hasValue():
            newEntry = f"--{spec.name()}={value}"
        elif spec.hasBoolValueForPresence() and value:
            newEntry = f"--{spec.name()}"
        else:
            newEntry = ""
        forcingDirect = False
        for x in oldParams:
            addExisting = True
            if not forcingDirect:
                if x == "--":
                    if newEntry != "":
                        newList.append(newEntry)
                    forcingDirect = True
                elif spec.getMatchedValue(x)[0]:
                    if newEntry != "":
                        newList.append(newEntry)
                    addExisting = False
                    forcingDirect = True

            if addExisting:
                newList.append(x)

        if not forcingDirect and newEntry != "":
            newList.append(newEntry)

    return " ".join([EscapeMgr.asBashParam(x) for x in newList])


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


appLog.setName(getExeName())
appConfig = Configuration(logger=appLog)


entries, default = appLog.get_thresholds()


def getValue(name: str, default: Any | None = None) -> Any | None:
    global g_runningApp

    if g_runningApp is not None:
        return g_runningApp.appChoices.get(name, default)
    else:
        return default


# AppChoices
# .appOptions = appOptions
# .defaultsUsed = defaults_used
# .nextCustomisationAvail = nextCustomisationAvail
# .customisingChoicesMade=[]
#
class AppChoices:
    """This is the final results of what the user has chosen, after parsing the command line arguments and applying any defaults
    See AppParameterParsing for details of HOW this is generated - but the results are deliberately kept separate to avoid the messiness.
    """

    def __init__(
        self,
        paramsChosen: dict[str, Any],
        appValues: dict[str, Any],
        defaults_used: list[str],
        nextCustomisationAvail: dict[str, Any] | None,
    ):
        self.params = paramsChosen
        self.appValues = appValues
        self.defaultsUsed = defaults_used
        self.nextCustomisationAvail = nextCustomisationAvail
        self.customisingChoicesMade: list[Tuple[str, str]] = []

    def customisingChoices_asText(self, separator: str = " ") -> str:
        result = separator.join([str(x[1]) for x in self.customisingChoicesMade])
        if result != "" and separator == " ":
            result = " " + result
        return result

    def appValue(self, name: str) -> Any | None:
        if name in self.appValues:
            return self.appValues[name]

        APP_OPTION_DEFAULTS = {
            "settings": None,
            "show-config": False,
            "examples": [],
            "description": "Application",
            "runner": None,
            "escapeArguments": None,
            "additional_parameters": "",
            "exeName": getExeName(),
            "enableStyling": True,
            "versions_extra": [],
        }
        if name in APP_OPTION_DEFAULTS:
            return APP_OPTION_DEFAULTS[name]

        appLog.print_warning(
            f"AppChoices.appValue() - Unknown option requested: {name}"
        )
        return APP_OPTION_DEFAULTS.get(name, None)

    def paramChoice(self, name: str, default: Any | None = None) -> Any | None:
        return self.params.get(name, default)

    def asDict(self) -> dict[str, Any]:

        obj: dict[str, Any] = {
            "customisingChoices_asText": self.customisingChoices_asText(),
            "params": self.params,
            "appValues": self.appValues,
        }
        if self.customisingChoicesMade:
            obj["customisingChoicesMade"] = [
                f"{x[0]}={x[1]}" for x in self.customisingChoicesMade
            ]
        if self.defaultsUsed:
            obj["defaultsUsed"] = self.defaultsUsed
        if self.nextCustomisationAvail:
            obj["nextCustomisationAvail"] = self.nextCustomisationAvail
        return obj

    def __getitem__(self, key):
        return self.paramChoice(key)

    def asStr(self, name) -> str:
        _value = self.paramChoice(name)
        return "" if _value is None else str(_value)

    def asList(self, name) -> list[Any]:
        _value = self.paramChoice(name)
        return [] if _value is None else list(_value)

    def asInt(self, name) -> int:
        _value = self.paramChoice(name)
        return 0 if _value is None else int(_value)

    def get(self, key, default=None):
        return self.paramChoice(key, default)

    def getDataContents_orNone(self, key) -> DataContents | None:
        return self.paramChoice(key, None)

    def getOverviewAsTextAndParams(self) -> tuple[str, list[str]]:
        param_info = ""
        summarisedParams: list[str] = []
        for spec in self.getOptions():
            usage = spec.getHelpSummary()
            if usage and usage.summaryAdd_param:
                param_info += usage.summaryAdd_param
                summarisedParams.append(spec.name())

        additionalParams = self.appValues.get("additional_parameters", None)
        if additionalParams:
            param_info += f" -- {additionalParams}"
        return param_info.strip(), summarisedParams

    def getOptions(self) -> ParamSpecList:
        return ParamSpecList(self.appValues.get("options", []))


class AppParamParseResults:
    def __init__(
        self,
        paramSpec_chosen: dict[str, ParamSpecAndValue],
        errors: list[Tuple[str, str | None]],
        paramSpec_avail: ParamSpecList,
        appChoices: AppChoices,
    ):
        self.paramSpec_chosen = paramSpec_chosen
        self.errors = errors
        self.paramSpec_avail = paramSpec_avail
        self.appChoices = appChoices

    def asDict(self) -> dict[str, Any]:
        obj = {
            "paramSpec_chosen": {
                k: v.asDict() for k, v in self.paramSpec_chosen.items()
            },
            "paramSpec_avail": [x.asDict() for x in self.paramSpec_avail],
            "appChoices": self.appChoices.asDict(),
        }

        if self.errors:
            errorsOut = []
            for x in self.errors:
                msg = PrettyText.removeAnsiCodes(str(x[0]))
                if x[1] is None:
                    errorsOut.append(msg)
                else:
                    errorsOut.append(
                        {
                            "message": msg,
                            "suggestion": PrettyText.removeAnsiCodes(str(x[1])),
                        }
                    )

            obj["errors"] = errorsOut

        return obj


class _AppParameterParser:
    def asDict(self) -> dict[str, Any]:
        obj = {
            "appChoices": self._partialInfo.appChoicesBeingBuilt.asDict(),
            # "paramOptionsAfterParsing": self.paramOptionsAfterParsing,
            "orig_options": self.orig_options,
            "choices_walked": self.customisedChoicesWalked,
        }
        return obj

    def __init__(self, structWithOptions: dict[str, Any]):

        self.orig_options = structWithOptions.get("options", [])
        self.customisedChoicesWalked: list[dict[str, Any]] = [
            deepcopy(structWithOptions)
        ]

        self.availParamsFromAppInfo: ParamSpecList = ParamSpecList([])
        self._partialInfo = _AppParameterParser.ProcessingPartialInfo(
            structWithOptions, self.availParamsFromAppInfo
        )

    def doParsing(self, args: list[str]) -> AppParamParseResults:
        return self._partialInfo.doParsing(args)

    class ProcessingPartialInfo:

        def __init__(
            self,
            app_definition: dict[str, Any],
            availParamsFromAppInfo: ParamSpecList | None = None,
        ):
            self.appChoicesBeingBuilt = AppChoices({}, {}, [], None)
            self._mergedAppInfo = self.appChoicesBeingBuilt.appValues

            self.availParamsFromAppInfo = availParamsFromAppInfo or ParamSpecList([])

            self._noteGroupInfo(app_definition, None)

        def doParsing(self, args: list[str]) -> AppParamParseResults:

            ####################################################################################
            # Ensures we get the detailed logging (and colours) during parameter review
            _entries = self.getAvailParamsAll()
            appLog.setVerbosity(
                _entries.cheatPeekAtValue_orNoneType("verbosity"), silentOnFailure=True
            )
            styling.doDisable(
                _entries.cheatPeekAtValue_orNoneType("colour") == "disable"
            )

            ####################################################################################
            # Uses:
            #   * self.appChoicesBeingBuilt
            #   * self.getAvailParamsAll()
            #
            #
            # Creates:
            #   *  paramSpec_chosen    : dict[str, ParamSpecAndValue]
            #   *  errors: list[Tuple[str, str|None]]
            #
            _chosenSpec: ParamSpec | None = None
            _errors: list[Tuple[str, str | None]] = []
            paramSpec_chosen: dict[str, ParamSpecAndValue] = {}

            if appConfig.hasContents():
                configOptions = appConfig
            else:
                configOptions = None

            def _loadIntoSpec_direct(spec: ParamSpec, value: Any):
                _name: str = spec.name()

                if _name in paramSpec_chosen:
                    _errors.append(
                        (f"Cannot load directly into {_name} : Already has value", None)
                    )
                    return

                paramSpec_chosen[_name] = ParamSpecAndValue(spec)
                paramSpec_chosen[_name].value = value

            def _loadIntoSpec_fromArg(spec: ParamSpec, arg: str):
                _name: str = spec.name()

                if not (_name in paramSpec_chosen):
                    paramSpec_chosen[_name] = ParamSpecAndValue(spec)

                _error = paramSpec_chosen[_name].load_withConvert(arg)
                if _error:
                    _errors.append((_error, None))

            _force_non_options = False
            for arg in args:
                #
                if _chosenSpec is not None:
                    _loadIntoSpec_fromArg(_chosenSpec, arg)
                    _chosenSpec = None
                elif (arg == "--") and not (_force_non_options):
                    _force_non_options = True
                elif not arg.startswith("-") or (_force_non_options):
                    if not self._processCustomisingEntry(arg, _errors):

                        specToUse = next(
                            (
                                _spec
                                for _spec in self.getAvailParamsAll()
                                if _spec.mayBeUsedDirectly()
                                and (
                                    not (_spec.name() in paramSpec_chosen)
                                    or _spec.get("supportMultiple", False)
                                )
                            ),
                            None,
                        )

                        if specToUse is None:
                            specToUse = self.getAvailParamsAll().get("--")
                        if specToUse is not None:
                            _loadIntoSpec_fromArg(specToUse, arg)
                        else:
                            _errors.append((f"Unexpected direct argument: {arg}", None))
                else:
                    _done = False
                    if (
                        configOptions is not None
                        and (arg.startswith("--"))
                        and ("=" in arg)
                    ):

                        _done, errMsg = configOptions.setting_applyIfMatchesWithErrMsg(
                            arg.removeprefix("--").split("=", 1)
                        )

                        if errMsg:
                            _errors.append((errMsg, None))
                            _done = True

                    if not _done:
                        foundSpec, _value = self.getParamMatch(arg)

                        if foundSpec is None:
                            action_suffix = (
                                self.appChoicesBeingBuilt.customisingChoices_asText()
                            )
                            if action_suffix is None or (
                                str(action_suffix).strip() == ""
                            ):
                                action_suffix = ""

                            _errors.append(
                                (f"Unknown{action_suffix} option: {arg}", None)
                            )
                        elif _value is not None:
                            _loadIntoSpec_fromArg(foundSpec, _value)
                        else:
                            _chosenSpec = foundSpec
            if _chosenSpec is not None:
                _errors.append(
                    (f"Missing value for option: {_chosenSpec.name()}", None)
                )

            ##################################################################################################
            # Now has:
            #   * paramSpec_chosen    : dict[str, ParamSpecAndValue]
            #   * errors              : list[Tuple[str, str|None]]

            ################################################
            # Load Defaults for missing --options
            #
            _usedDefaults = []
            for spec in self.getAvailParamsAll():
                _name: str = spec.name()
                if _name not in paramSpec_chosen:
                    _defValue = spec.defaultValue_orNoneType()
                    if spec.isCustomising():
                        if self.appChoicesBeingBuilt.nextCustomisationAvail is None:
                            self.appChoicesBeingBuilt.nextCustomisationAvail = spec.get(
                                "customising", None
                            )
                    elif _defValue is not NoneType:
                        _usedDefaults.append(_name)
                        _loadIntoSpec_direct(spec, _defValue)
                    elif spec.hasBoolValueForPresence():
                        # Special case - the existance of it is the value - so if it is included we set it to True (eg: --help)
                        # but if it is not included, we set it to False
                        if spec.isNotHidden():
                            _usedDefaults.append(_name)
                            _loadIntoSpec_direct(spec, False)
                    elif spec.isNotHidden():

                        _errmsg = f"Missing required parameter: {styling.asError(spec.getValueHelp(ParamSpec.InfoStyle.PARAM_FORMAT_OR_EXAMPLE))}"

                        exampleOrNone = spec.getExample()

                        if exampleOrNone is None:
                            _suggestion = None
                        else:
                            _suggestion = appInfo_cmdWithVariant(spec, exampleOrNone)

                        _errors.append((_errmsg, _suggestion))

            if len(_usedDefaults) > 0:
                appLog.print_tediousDetail(
                    f"Used defaults for: {', '.join(_usedDefaults)}"
                )

            ##################################################################################################
            # Now has:
            #
            #   * paramSpec_chosen    : dict[str, ParamSpecAndValue]
            #   * errors              : list[Tuple[str, str|None]]
            #   * _usedDefaults       : list[str]
            #
            for x in paramSpec_chosen.values():
                for y in x.errorNotes:
                    _errors.insert(0, (y, None))

            appLog.print_tediousDetail(f"argv: " + Utils.asJsonStr(args, indent=2))
            appLog.print_tediousDetail(f"errors: " + Utils.asJsonStr(_errors, indent=2))
            appLog.print_tediousDetail(
                f"AS LOADED: " + Utils.asJsonStr(paramSpec_chosen, indent=2)
            )

            if (
                self.appChoicesBeingBuilt.nextCustomisationAvail is not None
                and "help" not in paramSpec_chosen
            ):
                _errors.append(
                    (
                        f"Expected one of {styling.asSuggestionList(self.appChoicesBeingBuilt.nextCustomisationAvail.keys())}",
                        None,
                    )
                )
            self.appChoicesBeingBuilt.defaultsUsed = _usedDefaults
            return AppParamParseResults(
                paramSpec_chosen,
                _errors,
                self.getAvailParamsAll(),
                self.appChoicesBeingBuilt,
            )

        def getParamMatch(self, arg) -> tuple[ParamSpec | None, str | None]:
            return self.getAvailParamsAll().getMatchedSpecAndValue(arg)

        def getAvailParamsAll(self) -> ParamSpecList:
            _all = ParamSpecList([])
            for x in self.availParamsFromAppInfo:
                _all.append(x)

            extraParams = self.appChoicesBeingBuilt.appValue("additional_parameters")

            if extraParams:
                _all.append(
                    ParamSpec(
                        {
                            "name": "--",
                            "group": "Additional Parameters",
                            "shortName": "",
                            "description": "extraParams",
                            "type": str,
                            "supportMultiple": True,
                            "hidden": True,
                        }
                    )
                )

            #################################################################################################
            #
            # Default options that might be available based on the current configuration
            #
            _all.append(
                ParamSpec(
                    {
                        "name": "verbosity",
                        "group": "~appAuto",
                        "lookup": entries,
                        "default": default,
                        "defaultEnvVar": "UAPP_VERBOSITY",
                        "description": "Set verbosity of messaging       ",
                    }
                )
            )

            #############################
            #
            # Styling
            #
            if (
                self.appChoicesBeingBuilt.appValue("enableStyling")
                and styling.isSupported()
            ):
                _all.append(
                    ParamSpec(
                        {
                            "name": "colour",
                            "lookup": ["enable", "disable"],
                            "group": "~appAuto",
                            "shortName": "",
                            "default": "enable",
                            "defaultEnvVar": "UAPP_COLOUR",
                            "description": "Select output colouring & styling",
                        }
                    )
                )
            if self.appChoicesBeingBuilt.appValue("show-config"):
                _all.append(
                    ParamSpec(
                        {
                            "name": "config-view",
                            "group": self.appChoicesBeingBuilt.customisingChoices_asText(
                                "+"
                            ),
                            "shortName": "C",
                            "description": "Gives the current configuration",
                        }
                    )
                )

            _all.append(
                ParamSpec(
                    {
                        "name": "version",
                        "group": "~appAuto",
                        "shortName": "",
                        "description": "Gives version information for this app: "
                        + styling.asBold(
                            f"v{self.appChoicesBeingBuilt.appValue('version')}"
                        ),
                    }
                )
            )

            _all.append(
                ParamSpec(
                    {
                        "name": "help",
                        "group": "~appAuto",
                        "shortName": "?" if _all.containsShortName("-h") else "h",
                        "description": "Gives help",
                    }
                )
            )

            _all.append(
                ParamSpec(
                    {
                        "hidden": True,
                        "name": "debug-info",
                        "group": "~appAuto",
                        "description": "Gives additional information about the app and its configuration",
                        "lookup": {
                            "none": None,
                            "app-info": "app-info",
                            "config-info": "config-info",
                            "all": "all",
                        },
                    }
                )
            )
            #
            ###################################################################################################
            return _all

        def _mergeStr(self, name: str, actionInfo: dict[str, Any], separator: str):
            appendThis = actionInfo.get(name, None)
            if appendThis is None:
                return
            if not isinstance(self._mergedAppInfo.get(name, None), str):
                self._mergedAppInfo[name] = ""
            if self._mergedAppInfo[name] != "":
                self._mergedAppInfo[name] += separator
            self._mergedAppInfo[name] += str(appendThis)

        def _noteGroupInfo(
            self,
            _actionInfo: dict[str, Any],
            _parentToReplace: Tuple[int, int, str] | None = None,
        ):
            """parentToReplace is a tuple of (availParam_index, options_index, chosenAction) - if provided, it will remove the parent customisation from the options list if it is present"""
            actionInfo = deepcopy(_actionInfo)

            # Update:
            #   * self._mergedAppInfo
            #   * self.availParamsFromAppInfo

            #########################
            # Update: _mergedAppInfo
            #
            for name in actionInfo:
                if name == "options":
                    pass  # Do separately at the end
                elif name not in self._mergedAppInfo:
                    self._mergedAppInfo[name] = actionInfo[name]
                elif name in ["description", "escapeArguments", "examples"]:
                    self._mergedAppInfo[name] = actionInfo[name]
                    # self._mergeStr(name, actionInfo, ' - ')
                elif name in ["version"]:
                    self._mergeStr(name, actionInfo, ",")
                elif isinstance(self._mergedAppInfo[name], list):
                    self._mergedAppInfo[name].extend(actionInfo[name])
                else:
                    n = 1
                    while f"{name}_prev[{n}]" in self._mergedAppInfo:
                        n += 1

                    for i in range(n - 1, 1, -1):
                        self._mergedAppInfo[f"{name}_prev[{i+1}]"] = (
                            self._mergedAppInfo[f"{name}_prev[{i}]"]
                        )
                    self._mergedAppInfo[f"{name}_prev[1]"] = self._mergedAppInfo[name]
                    self._mergedAppInfo[name] = actionInfo[name]

            #########################
            # Update:
            #   * self._mergedAppInfo[options]
            #   * self.availParamsFromAppInfo
            #
            _optionList: list[dict[str, Any]] | None = self._mergedAppInfo.get(
                "options", None
            )
            if _optionList is None:
                _optionList = []
                self._mergedAppInfo["options"] = _optionList

            # Remove the parent customisation if provided
            optionList_index = len(_optionList)
            availParams_index = len(self.availParamsFromAppInfo)
            chosenAction = None
            if _parentToReplace is not None:
                availParams_index, optionList_index, chosenAction = _parentToReplace

                _optionList.pop(optionList_index)
                self.availParamsFromAppInfo.pop(availParams_index)

            if _optionList is actionInfo.get("options", None):
                appLog.print_warning(
                    "Impossible configuration - Adding a list to itself ?"
                )
            else:
                for xx in actionInfo.get("options", []):
                    self.cleanEntry(xx)
                    if chosenAction and not xx.get("group", ""):
                        xx["group"] = chosenAction
                    self.availParamsFromAppInfo.insert(
                        availParams_index,
                        ParamSpec(
                            xx,
                            bool(self.appChoicesBeingBuilt.appValue("escapeArguments")),
                        ),
                    )
                    availParams_index += 1
                    _optionList.insert(optionList_index, xx)
                    optionList_index += 1

            #########################
            # Done
            #
            return actionInfo

        def cleanEntry(
            self,
            entry: dict[str, Any],
        ):

            if not "group" in entry:
                entry["group"] = self.appChoicesBeingBuilt.customisingChoices_asText(
                    "+"
                )

            if "const" in entry:
                entry["default"] = entry["const"]
                entry["hidden"] = True

            _customisations = entry.get("customising", None)
            if _customisations is not None:
                if not isinstance(_customisations, dict):
                    return False

                entry["mustBeDirect"] = True
                entry["descriptions"] = {}

                for key in _customisations:
                    entry["descriptions"][key] = _customisations[key].get(
                        "description", ""
                    )
                entry["lookup"] = list(_customisations.keys())

        def _processCustomisingEntry(
            self, param: str, _errors: list[Tuple[str, str | None]]
        ) -> bool:
            chosenAction = param.strip()

            if chosenAction == "":
                return False

            availParam_index = -1
            for nn in range(len(self.availParamsFromAppInfo)):
                if self.availParamsFromAppInfo[nn].isCustomising():
                    availParam_index = nn
                    break

            options_index = -1
            for nn in range(len(self._mergedAppInfo.get("options", []))):
                if "customising" in self._mergedAppInfo["options"][nn]:
                    options_index = nn
                    break

            if (availParam_index < 0) and (options_index < 0):
                return False

            if (availParam_index < 0) or (options_index < 0):
                appLog.print_warning(
                    f"Internal Error: Customising option {chosenAction} found in one of the lists but not the other - ignoring"
                )
                return False

            _name = self.availParamsFromAppInfo[availParam_index].name()
            _customisations = self.availParamsFromAppInfo[availParam_index].get(
                "customising", None
            )
            if _customisations is None:
                return False

            if not isinstance(_customisations, dict):
                appLog.print_warning(f"Internal Error: Customising option not valid")
                return False
            if chosenAction not in _customisations:
                _errors.append(
                    (
                        f"Expected one of {styling.asSuggestionList(_customisations.keys())} but have {styling.asError(EscapeMgr.asBashParam(chosenAction))}",
                        None,
                    )
                )
                return True  # < Failed - but still handled as a customisation, so we don't want to treat it as a normal option

            actionInfo = _customisations[chosenAction]

            actionInfo["isChosen"] = True
            actionInfo["usage"] = "isChosen"
            actionInfo["group"] = chosenAction

            self._noteGroupInfo(
                actionInfo, (availParam_index, options_index, chosenAction)
            )
            self.appChoicesBeingBuilt.customisingChoicesMade.append(
                (_name, chosenAction)
            )

            return True


# |x|    def optionInsert_orNoneType(self, spec: dict[str, Any] | None) -> Any | NoneType:
# |x|        """Returns the value of the spec - or NoneType if no spec provided.
# |x|        Note, due to lookups, 'None' is a valid value, so we cannot use None to indicate no spec provided - hence the use of NoneType
# |x|        """
# |x|        if spec is not None:
# |x|            _spec = ParamSpec(spec)
# |x|            self.availParamsFromAppInfo.insert(0, _spec)
# |x|            return _spec.cheatPeekAtValue_orNoneType()
# |x|        return NoneType


def exeSubstitute(txt: str, exeName: str, exeNameDecorated: str) -> str:
    txt = txt.replace("<exeName>", exeName)
    txt = txt.replace("<exeName+action>", exeNameDecorated)
    return txt


def popLastFromText(txt: str, suffixMarker: str) -> tuple[str, str]:
    x = txt.split(suffixMarker)
    suffix = ""
    if len(x) > 1:
        suffix = suffixMarker + " " + x.pop().strip()
        txt = "#".join(x).strip()
    return txt, suffix


class Define:

    def __init__(self, _app_definition: dict[str, Any]):
        self.app_definition = _app_definition
        self.app_definition["runningDir"] = os.getcwd()
        self.app_definition["exeName"] = getExeName()

        ###############
        #
        if "version" not in self.app_definition:
            self.app_definition["version"] = "0.0.0"
        if "description" not in self.app_definition:
            self.app_definition["description"] = "No description provided"

        #############################
        #

        self.orig_app_definition = deepcopy(self.app_definition)
        appInfo_set("APP_DEFINITION", deepcopy(self.app_definition))

        self.appChoices = AppChoices({}, deepcopy(self.app_definition), [], None)

    def asDict(self) -> dict[str, Any]:
        obj = {
            "app_definition": self.app_definition,
            # "appParamParser": self.appParamParser,
            "appParamsChoices": self.appChoices.asDict(),
        }
        return obj

    def giveHelp(self, file_dest=sys.stdout, shorterVersion=False):
        for x in self.getHelp(shorterVersion=shorterVersion):
            file_dest.write(x.rstrip() + "\n")
        printVerbose_sysInfo()

    def getHelp(self, shorterVersion=False) -> list[str]:
        #
        # Full done from only:
        #   * self.appChoices
        #   * self.availParams
        #
        return self._getHelp(
            self.appChoices, self.availParams, shorterVersion=shorterVersion
        )

    @staticmethod
    def _getHelp(
        appChoices: AppChoices, availParams: ParamSpecList, shorterVersion=False
    ) -> list[str]:
        #
        # Full done from only:
        #   * self.appChoices
        #   * self.availParams

        #
        visibleParams = [
            x for x in availParams if x.isNotHidden() and not x.isCustomising()
        ]

        lines_out: list[str] = []

        exeName = str(appChoices.appValue("exeName"))
        exeNameDecorated = (
            exeName + " " + appChoices.customisingChoices_asText().strip()
        ).strip()

        verText = f"v{appChoices.appValue('version')}"

        params_txt, _mentioned = appChoices.getOverviewAsTextAndParams()

        #########################################
        #  Calculate: `mentionOtherOptions`  (to use with 'params_txt' in the usage line)
        #
        _unmentioned = [
            x
            for x in visibleParams
            if not x.name() in _mentioned and (x.get("group") != "~appAuto")
        ]

        #########################################
        #
        _customisedChoiceNext: dict[str, Any] | None = appChoices.nextCustomisationAvail

        if not _customisedChoiceNext:
            mentionOtherOptions = "" if len(_unmentioned) == 0 else " [options]"
            prefix = (
                styling.asBold(
                    PrettyText.padToWidth(exeNameDecorated, 32)
                    + " "
                    + PrettyText.padToWidth(verText, 13)
                )
                + " : "
            )
            lines_out.append(f"{prefix}{appChoices.appValue('description')}")
            if not shorterVersion:
                prefix = PrettyText.asSpaces(prefix)
                for x in appChoices.appValue("versions_extra") or []:
                    lines_out.append(f"{prefix}{styling.asBold(x)}")

            lines_out.append("")
            lines_out.append(
                f"Usage: {styling.asSuggestion(exeNameDecorated+mentionOtherOptions+' '+params_txt)}"
            )  # + {appChoices.getCustomisationChoicesAsText()}
        else:
            # |eg:|  "send": {
            # |eg:|      "description": "Send ground command messages",
            # |eg:|      "options": [
            # |eg:|          PARAM_COMMANDS_DEFINITION,
            # |eg:|          {
            # |eg:|              "name": "keep-monitoring",
            # |eg:|              "description": "Continues to monitor even after all sent messages are handled",
            # |eg:|          },
            # |eg:|      ],
            # |eg:|      "show-config": True,

            directPrefixes = []
            for key, paramObj in _customisedChoiceNext.items():
                _description = paramObj.get("description", "")
                _obj: dict[str, Any] = {
                    "name": key,
                    "description": _description,
                }  # +"="+Utils.asJsonStr(paramObj)}

                _obj["options"] = paramObj.get("options", None) is not None
                directPrefixes.append(_obj)

            prefix = f"Usage: "
            directPrefixes.append({"blankLine": True})
            directPrefixes.append(
                {
                    "name": "<action> --help",
                    "options": False,
                    "description": "Gives help information on the action (From the above list)",
                }
            )

            for _entry in directPrefixes:
                if not _entry.get("blankLine", False):
                    _name = _entry.get("name", "")
                    exeNameToUse = (
                        exeName
                        if _entry.get("noDecoration", False)
                        else exeNameDecorated
                    )
                    _entry["nameToUse"] = exeNameToUse + " " + _name

            tableOut = PrettyTable()

            tableOut.appendRow(
                [
                    styling.asBold(exeNameDecorated),
                    styling.asBold(verText),
                    "| " + styling.asBold(appChoices.appValue("description")),
                ]
            )
            if not shorterVersion:
                for x in appChoices.appValue("versions_extra") or []:
                    tableOut.appendRow(["", "", "| " + styling.asBold(x)])
                tableOut.appendRow([])

            for _entry in directPrefixes:
                if _entry.get("blankLine", False):
                    tableOut.appendRow([])
                else:
                    _name = _entry.get("name", "")
                    exeNameToUse = (
                        exeName
                        if _entry.get("noDecoration", False)
                        else exeNameDecorated
                    )
                    _nameToUse = exeNameToUse + " " + _name

                    _value = _entry.get("description", "")
                    includeOptions = _entry.get("options", True)

                    params_txt = "[options …]"
                    _params_out = params_txt if includeOptions else ""

                    tableOut.appendRow(
                        [
                            f"{prefix}{styling.asSuggestion(_nameToUse)}",
                            styling.asSuggestion(_params_out),
                            "" if _value == "" else f"| {_value}",
                        ]
                    )
                    prefix = PrettyText.asSpaces(prefix)

            lines_out.extend(tableOut.asLines())

            ###############
            #
            # Add to examples
            #
            _examplesOut = appChoices.appValue("examples")
            if not _examplesOut:
                _examplesOut = []
                appChoices.appValues["examples"] = _examplesOut

            def replaceWithin(txt: str | list[str], needle: str, replacement: str):
                if isinstance(txt, str):
                    return txt.replace(needle, replacement)
                elif isinstance(txt, list):
                    return [replaceWithin(x, needle, replacement) for x in txt]
                else:
                    return txt

            for action, entry in _customisedChoiceNext.items():

                topSuggestion = entry.get("topSuggestion", None)
                if topSuggestion is None:
                    kindExamples = entry.get("examples", [])
                    if len(kindExamples) > 0:
                        topSuggestion = kindExamples[0]

                if topSuggestion is not None:
                    topSuggestion = replaceWithin(
                        topSuggestion,
                        "<exeName+action>",
                        "<exeName+action> " + EscapeMgr.escapeIfNeeded(action),
                    )
                    if isinstance(topSuggestion, str):
                        topSuggestion = topSuggestion.strip()

                        _restyle = topSuggestion.startswith("<exeName+action>")
                    else:
                        _restyle = False

                    if _restyle and isinstance(topSuggestion, str):

                        comment_suffix = ""
                        x = topSuggestion.split("#")
                        if len(x) > 1:
                            comment_suffix = " # " + x.pop()
                            topSuggestion = "#".join(x).strip()

                        topSuggestion = topSuggestion.split(" ") + [comment_suffix]

                if isinstance(topSuggestion, str):
                    _examplesOut.append(topSuggestion)
                elif isinstance(topSuggestion, list):
                    _examplesOut.append(topSuggestion)

        lines_out.append("")

        optionSummaries = ValueHelpSummaries()

        ############################################
        #
        # Add:  ['settings']: 'Setting Options'
        #
        shouldShowConfig = appChoices.appValue("show-config")
        if shouldShowConfig:

            appSettings = appChoices.appValue("settings")

            if appSettings:
                for entry_name, entry_params in appSettings.items():
                    _spec = {"group": "settings", "name": entry_name, "shortName": ""}
                    _spec.update(entry_params)
                    _spec["default"] = appConfig.setting_getPreUser(
                        entry_name
                    )  # < After update to overwrite it
                    optionSummaries.appendItem("Setting Options", _spec)

        ############################################
        #
        # Add:  ['~chosen']: 'Specific Options'
        #

        otherName = "Basic Options"
        for paramObj in visibleParams:
            _g = paramObj.get("group")
            if _g and (_g != "~appAuto"):  # < First: Non blank & non-auto entries
                titlePrefix = str(_g).title().replace("_", " ")
                if " " in titlePrefix or ":" in titlePrefix:
                    titlePrefix = "Basic"

                optionSummaries.appendItem(f"{titlePrefix} Options", paramObj)
                otherName = "Common Options"

        # < Ensure '~appAuto' are last
        for paramObj in visibleParams:
            _g = paramObj.get("group", None)
            if not _g:
                optionSummaries.appendItem(otherName, paramObj)  # < Then: Blank Entries

        for paramObj in visibleParams:
            _g = paramObj.get("group", None)
            if _g == "~appAuto":  # < Then: Auto entries
                optionSummaries.appendItem("Tailoring Options", paramObj)

        ############################################
        #
        # Print the options
        #
        lines_out.extend(optionSummaries.asLines())

        subscripts = ""
        for d in visibleParams:
            subscripts += d.getValueHelpSubscripts()
        lines_out.extend(ParamSpec.getValueHelpExtraInfoFromSubscripts(subscripts))

        ############################################
        #
        # Add examples
        #
        _examplesRaw = appChoices.appValue("examples")
        if shorterVersion:
            lines_out.append("")
        elif _examplesRaw:

            def popLastFromList(entries: list[str], suffixMarker: str) -> str:
                if len(entries) == 0:
                    return ""
                last = entries[-1]
                if not last.startswith(suffixMarker):
                    return ""
                return entries.pop()

            examplesOut = PrettyTable()
            commentsOut: list[str] = []
            tableColWidths = None
            # pipeOut: list[str] = []
            for s in _examplesRaw:
                if isinstance(s, str):
                    txt, comment_suffix = popLastFromText(
                        exeSubstitute(s, exeName, exeNameDecorated), "#"
                    )
                    # txt, pipe_suffix = popLastFromText(textSubstitute(s), "|")
                    examplesOut.appendRow([styling.asSuggestion(txt)])
                    commentsOut.append(comment_suffix)
                    # pipeOut.append(pipe_suffix)
                elif isinstance(s, dict):
                    if "colWidths" in s:
                        tableColWidths = s.get("colWidths")

                else:
                    line_out = [
                        exeSubstitute(str(x), exeName, exeNameDecorated).strip()
                        for x in s
                    ]

                    comment = popLastFromList(line_out, "#")
                    # pipe=popLastFromList(line_out,'|')
                    commentsOut.append(comment)
                    examplesOut.appendRow([styling.asSuggestion(x) for x in line_out])
                    # pipeOut.append(pipe)

            if examplesOut.rows:

                lines_out.append("")
                lines_out.append("Examples:")

                examplesOut.appendCol(commentsOut)
                for line in examplesOut.asLines(render_colVisWidths=tableColWidths):
                    lines_out.append(f" • {line}")

        return [line.replace("\xa0", " ").rstrip() for line in lines_out]

    def getExeName_decorated(self, decorated=True):
        if decorated:
            return appInfo_getStr("name+actions")
        else:
            return exeInfo_getName()

    def dumpVersion(self, includeAuthor: bool = False):
        txt = f"{PrettyText.padToWidth(getExeName(), 32)} v{PrettyText.padToWidth(self.app_definition['version'], 10)} {PrettyText.padToWidth(str(self.app_definition.get('description','')), 104)}"

        if includeAuthor and ("author" in self.app_definition):
            txt += f" | {self.app_definition['author']}"

        sys.stdout.write(f"{txt.strip()}\n")

        extras = self.app_definition.get("versions_extra", [])

        for line in extras:
            sys.stdout.write(
                f"{PrettyText.padToWidth('', 32)}  {PrettyText.padToWidth('', 10)} {PrettyText.padToWidth(str(line), 104)}\n"
            )

    def _createAppParamParser(self) -> _AppParameterParser:
        ###############
        #
        _appParamParser = _AppParameterParser(self.app_definition)

        return _appParamParser

    def parseParams(self, args: list[str] | None = None) -> AppChoices:
        global g_runningApp
        g_runningApp = self

        appConfig._reload(self.app_definition)

        if args is None:
            args = sys.argv[1:]

        if "--version" in args:
            self.dumpVersion()
            doHalt("Version Info - Exiting", suggestSilent=True)
            exit(0)

        parseResults = self._createAppParamParser().doParsing(args)

        self.availParams = parseResults.paramSpec_avail
        self.appChoices = parseResults.appChoices

        appInfo_appendStr(
            "APP_AS_USED.post_exe", self.appChoices.customisingChoices_asText()
        )

        for name, obj in parseResults.paramSpec_chosen.items():
            self.appChoices.params[name] = obj.value

        for name, value in self.appChoices.customisingChoicesMade:
            self.appChoices.params[name] = value

        ####################################
        #
        if self.appChoices.params.pop("version", None):
            self.dumpVersion()
            doHalt("Version Info - Exiting", suggestSilent=True)
            exit(0)

        exitWithOk = False
        if self.appChoices.params.pop("help", None):
            self.giveHelp(shorterVersion=bool(parseResults.errors))
            doHalt("Help Info - Exiting", suggestSilent=True)

            exitWithOk = True

        if parseResults.errors:
            error_exit(
                parseResults.errors[0][0], None, parseResults.errors[0][1] or True
            )

        if self.appChoices.params.pop("debug-option", None) == "app-info":
            obj = {"appDefinition": self.app_definition}
            print(Utils.asJsonStr(obj, indent=2))
            exitWithOk = True

        self.appChoices.appValues.pop("options", None)

        if exitWithOk:
            doHalt("Exiting", suggestSilent=True)
            exit(0)
        return self.appChoices


g_runningApp: Define | None = None


def getRunningApp() -> Define | None:
    global g_runningApp
    return g_runningApp


# |Remove|    def option_usedDefault(self, name):
# |Remove|        """
# |Remove|        Check if the option is set to its default value.
# |Remove|        :param name: The name of the option to check.
# |Remove|        :return: True if the option was omitted - forcing the deault value to be used
# |Remove|        """
# |Remove|        return name in self.choices_made.get("default_parameters", [])
# |Remove|
# |Remove|    def option_isDefault(self, name):
# |Remove|        """
# |Remove|        Check if the option is set to its default value.
# |Remove|        :param name: The name of the option to check.
# |Remove|        :return: True if the option is set to its default value, False otherwise.
# |Remove|        """
# |Remove|        if self.option_usedDefault(name):
# |Remove|            return True
# |Remove|        _value = self.choices_made.get("chosen_parameters", {}).get(name, None)
# |Remove|        if _value is None:
# |Remove|            return False
# |Remove|        return _value == ParamSpec.defaultValue(
# |Remove|            self.app_definition["options"].get(name)
# |Remove|        )


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


def exitOnException(e: BaseException, action: str | None = None) -> NoReturn:
    """
    Exit the program with an error message if an exception occurs.
    :param ex: The exception that occurred
    :param msg: Custom error message to display
    """
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
    elif not isHandled:
        msg, traceLines = getPrettyExceptionInfo(e)
        msg += "\n"
        if appLog.isVerbose() or [x for x in os.environ if x.startswith("VSCODE_")]:
            msg += "\n".join([f"   [trace]: {x}" for x in traceLines])

        elif g_runningApp is not None:
            msg += f"Suggestion: {styling.asSuggestion(appInfo_cmdWithVariant(g_runningApp.availParams.get('verbosity'),'details'))} for more information"
        error_exit(msg, withSuggestion=False)
    elif e.srcException is not None:
        if appLog.isVerbose() or [x for x in os.environ if x.startswith("VSCODE_")]:
            msg = "\n".join(
                [f"   [trace]: {x}" for x in getPrettyExceptionInfo(e.srcException)[1]]
            )
        elif g_runningApp is not None:
            msg = f"Suggestion: {styling.asSuggestion(appInfo_cmdWithVariant(g_runningApp.availParams.get('verbosity'),'details'))} for more information"
        else:
            msg = ""
        error_exit(f"{action}{emsgSuffix}\n{msg}", withSuggestion=False)

    else:
        error_exit(
            f"{action}{emsgSuffix}", withSuggestion=action.startswith("Missing value")
        )


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

    prefixOrNone = appLog.print_error(msg, noPrefix=True)
    if prefixOrNone is not None:
        if withSuggestion:
            suggestionTxt = ""
            if isinstance(withSuggestion, str):
                suggestionTxt = withSuggestion.removeprefix("Suggest:").strip()
            elif not "--help" in sys.argv:
                suggestionTxt = appInfo_getStr("name+actions") + " --help"

            if suggestionTxt != "":
                print(
                    f"{prefixOrNone}Suggestion: {styling.asSuggestion(suggestionTxt)}",
                    file=sys.stderr,
                )

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
            appLog.print_verbose(f" • STDOUT: {len(returnValue[1])} bytes…")
        else:
            appLog.print_verbose(
                f" • STDOUT: {returnValue[1].decode('utf-8', errors='replace')}"
            )

    if returnValue[2]:
        if len(returnValue[2]) > 2000:
            appLog.print_verbose(f" • STDERR: {len(returnValue[2])} bytes…")
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


def print_extra(message: Any):
    if message is None:
        return
    if isinstance(message, str):
        messageTxt = message
    elif isinstance(message, list):
        for x in message:
            print_extra(x)
        return
    else:
        messageTxt = Utils.asJsonStr(message, indent=2)

    print(styling.apply(messageTxt, "cyan+bold"), file=sys.stderr)
