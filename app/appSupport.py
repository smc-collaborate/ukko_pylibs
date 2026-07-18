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
    ParamSpecAndValue_collection,
    ValueHelpSummaries,
)

from ukko_pylibs.app.appChoices import AppParamParseResults, AppChoices
import ukko_pylibs.app.appHelp as appHelp

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
appConfig = Configuration(
    logger=appLog
)  # < @todo: Move this to inside app -> Global = More issues


entries, default = appLog.get_thresholds()


def appValueOrDefault(appValues: dict[str, Any], name: str) -> Any | None:
    if name in appValues:
        return appValues[name]

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

    appLog.print_warning(f"appValue() - Unknown option requested: {name}")
    return None


class IArgLoader_Template:
    """Generic command line arg parser
    Optionally implement 'doExtraArgReview' & 'event_applyingValue()'
    """

    def __init__(self, app_definition):
        self.buildingParamsFromAppDef = ParamSpecList()

        self.errors: list[Tuple[str, str | None]] = []
        self.nextCustomisationAvail_: dict[str, Any] | None = None
        self.paramsChosen = ParamSpecAndValue_collection()
        self.appValues: dict[str, Any] = {}
        self._noteGroupInfo(app_definition)

        self.processed_args: list[str] = []

    def doExtraArgReview(self, arg: str) -> bool:
        return False

    def event_applyingValue(self, name: str, value: Any, style: str):
        pass

    #########################################
    #
    # Rest is internal only
    def getAppParamParseResults(self) -> AppParamParseResults:

        _defaultsUsed = list(self.paramsChosen.filterBySource("defaults_used").keys())
        _params: dict[str, Any] = {}
        for key, _value in self.paramsChosen.items():
            _params[key] = _value.value
        return AppParamParseResults(
            self.paramsChosen,
            self.errors,
            self.getAvailParamsAll(),
            AppChoices(
                _params,
                self.appValues,
                _defaultsUsed,
                self.nextCustomisationAvail_,
                self.customisingChoices_asText_calc(),
            ),
        )

    def getAppValue(self, name: str) -> Any | None:
        return appValueOrDefault(self.appValues, name)

    def getParamSpec(self, name) -> ParamSpec | None:
        return self.getAvailParamsAll().get(name)

    def getAvailParamsAll(self) -> ParamSpecList:
        _all = ParamSpecList([])
        for x in self.buildingParamsFromAppDef:
            _all.append(x)

        extraParams = self.getAppValue("additional_parameters")

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
        if self.getAppValue("enableStyling") and styling.isSupported():
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
        if self.getAppValue("show-config"):
            _all.append(
                ParamSpec(
                    {
                        "name": "config-view",
                        "group": self.customisingChoices_asText_calc("+"),
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
                    + styling.asBold(f"v{self.getAppValue('version')}"),
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
                    "lookup": ["", "app-info", "app-as-run", "config-info", "all"],
                    "default": "",
                }
            )
        )

        return _all

    def customisingChoices_asText_calc(self, separator: str = " ") -> str:
        result = separator.join(
            [
                x.spec.get("customisationChoice", "???")
                for x in self.getAvailParamsAll().doFilterByAttr("isCustomisingChoice")
            ]
        )
        if result != "" and separator == " ":
            result = " " + result
        return result  # + "![b]!"

    def loadNamed_fromArg(self, spec: ParamSpec, arg: str):
        _name: str = spec.name()

        if not (_name in self.paramsChosen):
            self.paramsChosen[_name] = ParamSpecAndValue(spec)

        _value, _error = self.paramsChosen[_name].load_withConvert(arg)
        self.event_applyingValue(_name, _value, "spec")
        if _error:
            self.errors.append((_error, None))

    # |x|    def loadNamed_withValue(self,spec:ParamSpec, value:Any):
    # |x|        _name: str = spec.name()
    # |x|
    # |x|        self.event_applyingValue(_name, str(value),'???')  #<- Could be short but this will do for the moment
    # |x|        if not (_name in self.paramSpec_chosen):
    # |x|            self.paramSpec_chosen[_name] = ParamSpecAndValue(spec)
    # |x|
    # |x|        _error = self.paramSpec_chosen[_name].load_appendValue(value)
    # |x|        if _error:
    # |x|            self.errors.append((_error, None))

    def _noteGroupInfo(
        self,
        _actionInfo: dict[str, Any],
        replaceNextCustomisationWithThisAction: str | None = None,
    ):
        """parentToReplace -if provided, it will remove the parent customisation from the options list if it is present"""
        actionInfo = deepcopy(_actionInfo)

        # Update:
        #   * self.appValues
        #   * self.availParamsRightNow

        for name in actionInfo:
            if name == "options":
                pass  # Do separately at the end
            elif name not in self.appValues:
                self.appValues[name] = actionInfo[name]
            elif name in ["description", "escapeArguments", "examples"]:
                self.appValues[name] = actionInfo[name]
                # self._mergeStr(name, actionInfo, ' - ')
            elif name in ["version"]:
                DictUtils.appendStr(
                    self.appValues, name, actionInfo.get(name, None), ","
                )
            elif isinstance(self.appValues[name], list):
                self.appValues[name].extend(actionInfo[name])
            else:
                if True:
                    if not "_test_only_" in self.appValues:
                        self.appValues["_test_only_"] = {}
                    _test_only = self.appValues["_test_only_"]
                    n = 1
                    while f"{name}_prev[{n}]" in _test_only:
                        n += 1

                        for i in range(n - 1, 1, -1):
                            _test_only[f"{name}_prev[{i+1}]"] = _test_only[
                                f"{name}_prev[{i}]"
                            ]
                    _test_only[f"{name}_prev[1]"] = self.appValues[name]

                self.appValues[name] = actionInfo[name]

        #########################
        # Update:
        #   * self._mergedAppInfo[options]
        #   * self.availParamsRightNow
        #
        _optionList: list[dict[str, Any]] | None = self.appValues.get("options", None)
        if _optionList is None:
            _optionList = []
            self.appValues["options"] = _optionList

        if _optionList is actionInfo.get("options", None):
            appLog.print_warning("Impossible configuration - Adding a list to itself ?")
            return actionInfo
        ##############################
        # Clean
        #
        for xx in actionInfo.get("options", []):
            self.cleanEntry(xx)
            if replaceNextCustomisationWithThisAction and not xx.get("group", ""):
                xx["group"] = replaceNextCustomisationWithThisAction

        ####################################################
        #
        # Remove the parent customisation if provided
        #
        optionList_index = len(_optionList)
        availParams_index = len(self.buildingParamsFromAppDef)

        if replaceNextCustomisationWithThisAction is not None:
            customisingEntry = (
                self.buildingParamsFromAppDef.nextCustomisationOptions_get()
            )
            if customisingEntry is not None:
                newEntry = customisingEntry.customisationOptionsToChoice(
                    replaceNextCustomisationWithThisAction
                )
                for n in range(len(_optionList)):
                    if "customising" in _optionList[n]:
                        _optionList.pop(n)
                        optionList_index = n
                        break
                _optionList.insert(optionList_index, newEntry)
                optionList_index += 1
                availParams_index = (
                    self.buildingParamsFromAppDef.nextCustomisationOptions_pop()
                )
                newParamSpec = ParamSpec(newEntry)
                self.buildingParamsFromAppDef.insert(availParams_index, newParamSpec)
                self.loadNamed_fromArg(
                    newParamSpec, replaceNextCustomisationWithThisAction
                )
                availParams_index += 1

        ##########################
        # Add _optionList - we could deprecate using this at all ...
        #
        for xx in actionInfo.get("options", []):
            _optionList.insert(optionList_index, xx)
            optionList_index += 1

        #######################################
        # Add to our ParamList
        # (Alternatively we could rebuild the entire ParamList from the new 'options' List)
        for xx in actionInfo.get("options", []):
            self.buildingParamsFromAppDef.insert(
                availParams_index,
                ParamSpec(
                    xx,
                    bool(self.getAppValue("escapeArguments")),
                ),
            )
            availParams_index += 1

        #########################
        # Done
        #
        return actionInfo

    def cleanEntry(
        self,
        entry: dict[str, Any],
    ):

        if not "group" in entry:
            entry["group"] = self.customisingChoices_asText_calc("+")

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
                entry["descriptions"][key] = _customisations[key].get("description", "")
            entry["lookup"] = list(_customisations.keys())

    def loadDefaultsIntoRemainingValues(self):

        ################################################
        # Modifies:
        #   * self.paramsChosen.createNew_SpecAndValue(spec, <value>, 'usedDefault')
        #   * self.errors
        #
        # Creates:
        #   * self.nextCustomisationAvail_
        #
        # Uses:
        #   * self.getAvailParamsAll()
        #   * self.paramsChosen
        #
        for spec in self.getAvailParamsAll():
            if spec.name() not in self.paramsChosen:

                _defValue = spec.defaultValue_orNoneType()
                if spec.isCustomisingOptions():
                    if self.nextCustomisationAvail_ is None:
                        self.nextCustomisationAvail_ = spec.get("customising", None)
                elif _defValue is not NoneType:
                    self.paramsChosen.createNew_SpecAndValue(
                        spec, _defValue, "usedDefault"
                    )
                elif spec.isNotHidden():
                    # Special case - the existance of it is the value - so if it is included we set it to True (eg: --help)
                    # but if it is not included, we set it to False
                    if spec.hasBoolValueForPresence():
                        self.paramsChosen.createNew_SpecAndValue(
                            spec, False, "usedDefault"
                        )
                    elif not "help" in self.paramsChosen:
                        # @todo: Consider adding this anyway with a source as 'omitted - give error' or similar
                        _errmsg = f"Missing required parameter: {styling.asError(spec.getValueHelp(ParamSpec.InfoStyle.PARAM_FORMAT_OR_EXAMPLE))}"

                        exampleOrNone = spec.getExample()

                        if exampleOrNone is None:
                            _suggestion = None
                        else:
                            _suggestion = (
                                appInfo_cmdWithVariant({spec.name(): exampleOrNone})
                                or None
                            )

                        self.errors.append((_errmsg, _suggestion))

    def doIterateArgs(self, args: list[str]):

        _chosenSpec: ParamSpec | None = None
        _force_non_options = False
        for arg in args:
            #

            if _chosenSpec is not None:
                self.loadNamed_fromArg(_chosenSpec, arg)
                _chosenSpec = None
            elif (arg == "--") and not (_force_non_options):
                _force_non_options = True
                self.event_applyingValue("", "", "--")
            elif not arg.startswith("-") or (_force_non_options):
                if not self._processCustomisingEntry(arg):
                    specToUse = next(
                        (
                            _spec
                            for _spec in self.getAvailParamsAll()
                            if _spec.mayBeUsedDirectly()
                            and (
                                not (_spec.name() in self.paramsChosen)
                                or _spec.get("supportMultiple", False)
                            )
                        ),
                        None,
                    )

                    if specToUse is None:
                        specToUse = self.getParamSpec("--")
                    if specToUse is not None:
                        self.loadNamed_fromArg(specToUse, arg)
                    else:
                        self.errors.append((f"Unexpected direct argument: {arg}", None))

            else:
                foundSpec, _value = self.getAvailParamsAll().getMatchedSpecAndValue(arg)
                if foundSpec is not None:
                    if _value is not None:
                        self.loadNamed_fromArg(foundSpec, _value)
                    else:
                        _chosenSpec = foundSpec
                elif not self.doExtraArgReview(arg):
                    action_suffix = self.customisingChoices_asText_calc()
                    if action_suffix is None or (str(action_suffix).strip() == ""):
                        action_suffix = ""

                    self.errors.append((f"Unknown{action_suffix} option: {arg}", None))

        #####################
        #
        # Done - now review the results
        if _chosenSpec is not None:
            self.errors.append(
                (f"Missing value for option: {_chosenSpec.name()}", None)
            )

        if self.nextCustomisationAvail_ is not None and "help" not in self.paramsChosen:
            self.errors.append(
                (
                    f"Expected one of {styling.asSuggestionList(self.nextCustomisationAvail_.keys())}",
                    None,
                )
            )

        self.NOT_NEEDED_customisingChoicesMade_ = []
        for paramSpec in [
            x for x in self.getAvailParamsAll().doFilterByAttr("isCustomisingChoice")
        ]:
            self.NOT_NEEDED_customisingChoicesMade_.append(
                (paramSpec.name(), paramSpec.spec["customisationChoice"])
            )

    def _processCustomisingEntry(
        self, param: str
    ) -> bool:  # <- True=Handled, so don't treat it differently
        chosenAction = param.strip()

        if chosenAction == "":
            return False

        # |x|availParam_index = -1
        # |x|for nn in range(len(self.buildingParamsFromAppDef)):
        # |x|    if self.buildingParamsFromAppDef[nn].isCustomising():
        # |x|        availParam_index = nn
        # |x|        break
        customisingOptions = (
            self.buildingParamsFromAppDef.nextCustomisationOptions_get()
        )
        if customisingOptions is None:
            return False

        _customisations = customisingOptions.get("customising", None)

        if not isinstance(_customisations, dict):
            appLog.print_warning(f"Internal Error: Customising option not valid")
            return False

        if chosenAction not in _customisations:
            self.errors.append(
                (styling.asExpectedOneOf(_customisations.keys(), chosenAction), None)
            )
            return True  # < Failed - but still handled as a customisation, so we don't want to treat it as a normal option

        actionInfo = _customisations[chosenAction]

        actionInfo["isChosen"] = True
        actionInfo["usage"] = "isChosen"
        actionInfo["group"] = chosenAction

        self._noteGroupInfo(actionInfo, chosenAction)

        return True


class ArgLoader_withApplyConfig(IArgLoader_Template):
    def __init__(self, app_definition):
        super().__init__(app_definition)

    def doExtraArgReview(self, arg: str) -> bool:
        if not arg.startswith("--") or not ("=" in arg):
            return False

        if not appConfig.hasContents():
            return False

        name, value = arg.removeprefix("--").split("=", 1)

        _done, errMsg = appConfig.setting_applyIfMatchesWithErrMsg((name, value))

        if errMsg:
            self.errors.append((errMsg, None))
            return True

        return _done


class Define:

    def __init__(self, _app_definition: dict[str, Any]):
        self.app_definition = _app_definition
        self.app_definition["runningDir"] = os.getcwd()
        self.app_definition["exeName"] = getExeName()
        self.original_params = []
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

        self.parseResults: AppParamParseResults | None = None

    def asDict(self) -> dict[str, Any]:
        obj: dict[str, Any] = {
            "app_definition": self.app_definition,
        }

        if self.parseResults is not None:
            obj["parseResults"] = (self.parseResults.asDict(),)

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
        if self.parseResults is None:
            error_exit_internalCause("app.getHelp(parseResults=None)")

        return appHelp.getAppHelp_asLines(
            self.parseResults.appChoices,
            self.parseResults.paramSpec_avail,
            appConfig,
            shorterVersion=shorterVersion,
        )

        # self.appChoices = AppChoices({}, deepcopy(self.app_definition), [], None)

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

    def parseParams(self, args: list[str] | None = None) -> AppChoices:
        global g_runningApp
        g_runningApp = self

        appConfig._reload(self.app_definition)

        if args is None:
            args = sys.argv[1:]
        if args:
            self.original_params = args

        if "--version" in args:
            self.dumpVersion()
            doHalt("Version Info - Exiting", suggestSilent=True)
            exit(0)

        argLoader = ArgLoader_withApplyConfig(self.app_definition)

        ####################################################################################
        # Ensures we get the detailed logging (and colours) during parameter review
        _entries = argLoader.getAvailParamsAll()
        appLog.setVerbosity(
            _entries.cheatPeekAtValue_orNoneType("verbosity"), silentOnFailure=True
        )
        styling.doDisable(_entries.cheatPeekAtValue_orNoneType("colour") == "disable")

        argLoader.doIterateArgs(args)

        argLoader.loadDefaultsIntoRemainingValues()

        _usedDefaults = argLoader.paramsChosen.filterBySource("usedDefault")

        if _usedDefaults:
            appLog.print_tediousDetail(
                f"Used defaults for: {', '.join(_usedDefaults.keys())}"
            )

        ##################################################################################################
        # Now has:
        #
        #   * paramSpec_chosen    : dict[str, ParamSpecAndValue]
        #   * errors              : list[Tuple[str, str|None]]
        #   * _usedDefaults       : list[str]
        #
        appLog.print_tediousDetail(f"argv: " + Utils.asJsonStr(args, indent=2))
        appLog.print_tediousDetail(
            f"errors: " + Utils.asJsonStr(argLoader.errors, indent=2)
        )
        appLog.print_tediousDetail(
            f"AS LOADED: " + Utils.asJsonStr(argLoader, indent=2)
        )

        self.parseResults = argLoader.getAppParamParseResults()

        exitReason = self.doRunOnParseResults(self.parseResults)

        if exitReason is not None:
            doHalt(
                f"{'' if exitReason=='' else exitReason+' - '}Exiting",
                suggestSilent=True,
            )
            exit(0)

        return self.parseResults.appChoices

    def doRunOnParseResults(self, _parseResults: AppParamParseResults) -> str | None:
        appInfo_appendStr(
            "APP_AS_USED.post_exe",
            _parseResults.appChoices.customisingChoicesMade_withLeadingSpace,
        )

        # |x|for name, obj in parseResults.paramSpec_chosen.items():
        # |x|    self.appChoices.params[name] = obj.value

        # |x| for name, value in self.appChoices.customisingChoicesMade:
        # |x|    self.appChoices.params[name] = value

        ####################################
        #
        if _parseResults.appChoices.params.pop("version", None):
            self.dumpVersion()
            return "Version Info"

        exitReason: str | None = None
        if _parseResults.appChoices.params.pop("help", None):
            self.giveHelp(shorterVersion=bool(_parseResults.errors))

            exitReason = "Help Info"

        if _parseResults.errors:
            suggestion = _parseResults.errors[0][1]

            error_exit_withSuggestion(
                _parseResults.errors[0][0], suggestion if suggestion else "<auto>"
            )

        debug_info = _parseResults.appChoices.params.pop("debug-info", None)
        if debug_info:
            obj: dict[str, Any] = {}
            # debug_info: "app-info","app-as-run","config-info","all"
            if debug_info in ["all", "app-info"]:
                obj["app-info"] = self.app_definition
            if debug_info in ["all", "app-as-run"]:
                asRun = deepcopy(_parseResults.appChoices.asDict())
                for x in [
                    "options",
                    "examples",
                    "usage",
                    "group",
                    "isChosen",
                    "_test_only_",
                ]:
                    asRun["appValues"].pop(x)
                obj["app-as-run"] = asRun
            if debug_info in ["all", "config-info"]:
                obj["config-info"] = appConfig.asDict()

            print(Utils.asJsonStr(obj, indent=2))
            exitReason = ""

        _parseResults.appChoices.appValues.pop("options", None)

        return exitReason


##################################################################################################
#
#

g_runningApp: Define | None = None


def getRunningApp() -> Define | None:
    global g_runningApp
    return g_runningApp


def getValue(name: str, default: Any | None = None) -> Any | None:
    global g_runningApp

    if g_runningApp is not None and g_runningApp.parseResults is not None:
        return g_runningApp.parseResults.appChoices.get(name, default)
    else:
        return default


#
#
##################################################################################################


class _ArgLoader_ReplaceParams(IArgLoader_Template):
    def __init__(self, app_definition, replacingArgs: dict[str, Any]):
        super().__init__(app_definition)
        self.toReplace: dict[str, Any] = deepcopy(replacingArgs)

        self.hasModified = False
        self.outputList = []

    def doExtraArgReview(self, arg: str) -> bool:
        key = (
            ""
            if not arg.startswith("--") or not ("=" in arg)
            else arg.removeprefix("--").split("=")[0]
        )

        return False if not appConfig.hasContents() else appConfig.hasKey(key)

    def _nameValueToArg(self, name: str, valueAsText: str):
        spec = self.getParamSpec(name)
        paramAsText = name
        if spec is None:
            paramAsText = f"--{name}={valueAsText}❓  "
        elif spec.mustBeDirect() or (name == "--"):
            paramAsText = valueAsText
        elif spec.hasValue():
            paramAsText = f"--{name}={valueAsText}"
        else:
            paramAsText = f"--{name}"

        return paramAsText

    def event_applyingValue(self, name: str, value: Any, style: str):

        # |x| _msg=f"Applying[{style:<30}] [ {paramAsText:<30}]"
        # |x| print_cyan([_msg])

        if name in self.toReplace:
            newValue = self.toReplace.pop(name)
            paramAsText = self._nameValueToArg(name, value)
            if value != newValue:
                self.hasModified = True

        elif style == "spec":
            paramAsText = self._nameValueToArg(name, value)
        elif style == "--":
            self._appendIfNeeded()
            paramAsText = "--"
        else:
            paramAsText = f"--{name}={value}❓  [style:{style}]"

        self.outputList.append(paramAsText)

    def _appendIfNeeded(self):
        for name, value in self.toReplace.items():
            self.outputList.append(
                self._nameValueToArg(name, value)
            )  # f"--{self.replacingArg}={self.newValue}[**INSERTED]")
            self.hasModified = True
        self.toReplace = {}

    def getReplacedParams(self, exeName: str, blankIfUnchanged: bool) -> str:
        self._appendIfNeeded()

        if not self.hasModified and blankIfUnchanged:
            return ""

        newList: list[str] = [exeName]
        newList.extend(self.outputList)

        return " ".join(newList)  # [EscapeMgr.asBashParam(x) for x in newList])


##################################################################################################
#
#


def appInfo_cmdWithVariant(
    replacingArgs: dict[str, Any], blankIfUnchanged: bool = True
) -> str:
    """Returns: (cmd,isModified) - the command line to run the app with the given spec/value, and whether it is materially different from the existing values
    This is only been tested with named values.  (ie: --name=value)"""

    app = getRunningApp()
    if app is None:
        return ""

    argReplacer = _ArgLoader_ReplaceParams(app.app_definition, replacingArgs)

    argReplacer.doIterateArgs(app.original_params)

    return argReplacer.getReplacedParams(appInfo_getStr("exeFullName"), False)


def appInfo_normalisedCommand() -> str:
    return appInfo_cmdWithVariant({}, blankIfUnchanged=False)


def exeInfo_getName():
    """
    Returns the name of the executable, without the path.
    :return: The name of the executable.
    """
    return os.path.basename(getExeName())


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


#
#
##################################################################################################

################################
# |ToReview| def groupCreate(name: str, defaultValue: str | None = None) -> dict[str, Any]:
# |ToReview|     obj = {"name": name, "customising": {}, "mustBeDirect": True}
# |ToReview|
# |ToReview|     if defaultValue is not None:
# |ToReview|         obj["defaultValue"] = defaultValue
# |ToReview|
# |ToReview|     return obj
# |ToReview|
# |ToReview|
# |ToReview| def groupEntry(
# |ToReview|     description: str,
# |ToReview|     funcCallback,
# |ToReview|     _options: list | None = None,
# |ToReview|     examples: list | None = None,
# |ToReview| ):
# |ToReview|     obj: dict[str, Any] = {"description": description, "_func_callback": funcCallback}
# |ToReview|     if _options is not None:
# |ToReview|         obj["options"] = _options
# |ToReview|     if examples is not None:
# |ToReview|         obj["examples"] = examples
# |ToReview|     return obj
# |ToReview|
# |ToReview| class JsonEncoderExtended(json.JSONEncoder):
# |ToReview|     def default(self, o):
# |ToReview|         return o.__dict__
# |ToReview|

#############################################################################################################################################
#


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


def doRun(callable: Callable[[], None]):
    try:
        callable()
        doExit()
    except BaseException as e:
        exitOnException(e)


#
#############################################################################################################################################


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


#############################################################################################################################################
#


def doExit(defaultExitCode: int | None = None) -> NoReturn:
    doHalt()
    if defaultExitCode is not None and defaultExitCode != 0:
        exitCode = defaultExitCode
    else:
        exitCode = 1 if appLog.had_error() else 0
    sys.exit(exitCode)


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
            error_exit_withAutoSuggestion(f"{action}: IOError{emsgSuffix}")
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

        elif getRunningApp() is not None:
            msg += f"Suggestion: {styling.asSuggestion(appInfo_cmdWithVariant({'verbosity':'details'}))} for more information"
        error_msg_exit(msg)
    elif e.srcException is not None:
        if appLog.isVerbose() or [x for x in os.environ if x.startswith("VSCODE_")]:
            msg = "\n".join(
                [f"   [trace]: {x}" for x in getPrettyExceptionInfo(e.srcException)[1]]
            )
        elif getRunningApp() is not None:
            msg = f"Suggestion: {styling.asSuggestion(appInfo_cmdWithVariant({'verbosity':'details'}))} for more information"
        else:
            msg = ""
        error_msg_exit(f"{action}{emsgSuffix}\n{msg}")

    else:
        error_exit_withAutoSuggestion(
            f"{action}{emsgSuffix}",
            useAutoSuggestion=action.startswith("Missing value"),
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
        resultPart = resultFull

    else:
        resultPart = (
            resultFull
            if elementNameIfNotFull is None
            else DictUtils.get(resultFull, elementNameIfNotFull, type(None))
        )

    if resultPart is type(None):

        msg = f"Error[Internal]: Unable to return '{elementNameIfNotFull}'.  Available values are [{','.join(resultFull.keys())}]"

        suggestion = appInfo_cmdWithVariant({"output-format": "json-full"})
        if suggestion != "":
            msg += (
                f"\nSuggestion: {styling.asSuggestion(suggestion)} for more information"
            )

        error_msg_exit(f"{msg}")
    else:
        appLog.print_info(f"Output full: {Utils.asJsonStr(resultFull, indent=2)}")
        appLog.print_info(f"AAAA")

        if outputFormat in ["json", "json-full"]:
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


def error_msg_exit(msg: str, exception: Exception | None = None) -> NoReturn:

    return error_exit_withSuggestion(msg, "", "", exception)


def error_exit_withAutoSuggestion(
    msg: str, exception: Exception | None = None, useAutoSuggestion: bool = True
) -> NoReturn:

    return error_exit_withSuggestion(
        msg, "<auto>" if useAutoSuggestion else "", "", exception
    )


def error_exit_internalCause(
    msg: str,
    exception: Exception | None = None,
) -> NoReturn:
    return error_msg_exit("Error[Internal]: " + msg, exception)


def error_exit_withSuggestion(
    msg: str,
    suggestionText: str,
    extraNote: str = "",
    exception: Exception | None = None,
) -> NoReturn:
    # print_verbose(f"error_exit: {msg} | withAutoSuggestion={withSuggestion}")

    if suggestionText == "<auto>" and not "--help" in sys.argv:
        suggestionText = appInfo_getStr("name+actions") + " --help"
    else:
        suggestionText = ""

    if exception is not None:
        msg += f" | Exception: {str(exception)}"

    prefixOrNone = appLog.print_error(msg, noPrefix=True)
    if prefixOrNone is not None:
        if suggestionText != "":
            print(
                f"{prefixOrNone}Suggestion: {styling.asSuggestion(suggestionText)}{extraNote}",
                file=sys.stderr,
            )

    printVerbose_sysInfo()
    doHalt("Exiting with error")
    sys.exit(1)


# |x|def error_exit(
# |x|    msg: str, exception: Exception | None = None, withSuggestion: bool | str = True
# |x|) -> NoReturn:
# |x|    # print_verbose(f"error_exit: {msg} | withAutoSuggestion={withSuggestion}")
# |x|
# |x|    if exception is not None:
# |x|        msg += f" | Exception: {str(exception)}"
# |x|
# |x|    prefixOrNone = appLog.print_error(msg, noPrefix=True)
# |x|    if prefixOrNone is not None:
# |x|        if withSuggestion and not '\nSuggestion:' in msg:
# |x|            suggestionTxt = ""
# |x|            if isinstance(withSuggestion, str):
# |x|                suggestionTxt = withSuggestion.removeprefix("Suggest:").strip()
# |x|            elif not "--help" in sys.argv:
# |x|                suggestionTxt = appInfo_getStr("name+actions") + " --help"
# |x|
# |x|            if suggestionTxt != "":
# |x|                print(
# |x|                    f"{prefixOrNone}Suggestion: {styling.asSuggestion(suggestionTxt)}",
# |x|                    file=sys.stderr,
# |x|                )
# |x|
# |x|    printVerbose_sysInfo()
# |x|    doHalt("Exiting with error")
# |x|    sys.exit(1)


def doExitWithCode() -> NoReturn:
    printVerbose_sysInfo()

    if appLog.had_error():
        doHalt("Exiting: Had Error")
        sys.exit(1)
    else:
        doHalt("Exiting: No Error", suggestSilent=True)
        sys.exit(0)


#
#############################################################################################################################################


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
            error_msg_exit(f"Unable to uninstall {exeInfo_getName()}: {e}")
    return "PYAPP_INSTALL_SOURCE" in os.environ


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


def print_cyan(message: Any):
    if message is None:
        return
    if isinstance(message, str):
        messageTxt = message
    elif isinstance(message, list):
        for x in message:
            print_cyan(x)
        return
    else:
        messageTxt = Utils.asJsonStr(message, indent=2)

    print(styling.apply(messageTxt, "cyan+bold"), file=sys.stderr)
