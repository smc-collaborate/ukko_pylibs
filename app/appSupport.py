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
from ukko_pylibs.basic.simpleUtils import Utils, PrettyText, EscapeMgr, DictUtils
from ukko_pylibs.basic.logger import appLog
from ukko_pylibs.basic.class_HandledException import HandledException
from ukko_pylibs.basic import styling
from ukko_pylibs.app.class_Configuration import Configuration
from ukko_pylibs.app.class_ParamSpec import (
    ParamSpec,
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
    # |x| print(f"appInfo_set({name})={value}")
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
        return g_runningApp.options_chosen.get(name, default)
    else:
        return default


class AppParameters:
    def __init__(self, structWithOptions: dict[str, Any]):
        self.orig_options = structWithOptions.get("options", [])
        self.options = deepcopy(self.orig_options)
        self.avail = (
            ParamSpecList()
        )  # < Really 'availableParametersWithTheseParticularChoices' .. but that's too long a name
        self.choices_made = {}
        self.customisedChoicesWalked: list[dict[str, Any]] = [
            deepcopy(structWithOptions)
        ]
        self.parsedSettingsOut = {}
        # |x|self.loadedParams = {}

    def optionInsert(self, spec: dict[str, Any] | None) -> Any | None:
        if spec is not None:
            self.options.insert(0, spec)
            return ParamSpec(spec).cheatPeekAtValue()
        return None

    def getWalkedValue(self, name: str, default: Any = None) -> Any | None:
        """
        Get the value of a parameter that was set during the 'walk' through the app definition
        (ie: when an action was chosen)
        :param name: The name of the parameter to get
        :param default: The default value to return if the parameter was not set
        :return: The value of the parameter, or the default if it was not set
        """

        found = default
        for entry in self.customisedChoicesWalked:
            if name in entry:
                found = entry[name]

        return found

    def getOverviewAsText(self) -> str:
        # print_extra(["getOverviewAsText(): Avail:",self.avail])
        param_info = ""
        for paramObj in self.avail:
            usage = paramObj.getHelpSummary()
            param_info += usage.summaryAdd_param if usage else ""

        additionalParams = self.getWalkedValue("additional_parameters", None)
        if additionalParams:
            param_info += f" -- {additionalParams}"
        return param_info

    def getCustomisationChoicesAsText(self) -> str:
        _choices = self.choices_made.get("customisedChoicesMade", [])
        _result = ""
        for x in _choices:
            _result += f" {x}"
        return _result

    # |x|def getCustomisingOptions(self) -> list[dict[str, Any]]:
    # |x|    directPrefixes = []
    # |x|    for paramObj in self.avail.doFilterByAttr("isCustomising"):
    # |x|        directPrefixes.extend([{'name': key, 'description': value} for key, value in paramObj.spec.get('descriptions',{}).items()])
    # |x|    return directPrefixes

    class ProcessingPartialInfo:
        def __init__(self, app_definition: dict[str, Any], args: list[str]):
            self.escapeArguments: bool = False
            self.nextActionOptions = None

            self.nonOptionArgs = []
            self.nonOptionArgIndex = 0
            _addAll = False
            for arg in args:
                if not arg.startswith("-") or _addAll:
                    self.nonOptionArgs.append(arg)
                elif arg == "--":
                    _addAll = True

            self.chosenActions = []
            self.actionsWalked = [app_definition]
            self.nextActionOptions: dict[str, Any] | None = None

    def doParsing(self, app_definition: dict[str, Any], args: list[str]):

        appInfo_set("APP_AS_USED.paramsArray", args)

        for x in args:
            appInfo_appendStr("APP_AS_USED.allParams", EscapeMgr.asBashParam(x))

        self.parsedDescription = ""
        self.parsedExamples: list[str] = []

        #################
        #
        # Build 'self.avail' - the list of available parameters, based on the app definition and the arguments provided
        #
        _partialInfo = AppParameters.ProcessingPartialInfo(app_definition, args)
        self._groupInfoUpdate(_partialInfo)

        for x in self.options:

            _customisations = x.get("customising", None)
            if (_customisations is not None) and isinstance(_customisations, dict):
                for _value in self._processCustomisingEntry(
                    _customisations, x, _partialInfo
                ):
                    self.avail.append(ParamSpec(_value, _partialInfo.escapeArguments))
            else:
                self.avail.append(ParamSpec((x)))

        # |x| ######################################
        # |x|
        # |x|  Build 'self.loadedParams'
        # |x| self.loadedParams = {}
        # |x| for x in self.avail:
        # |x|     self.loadedParams[x.name()] = x.cheatPeekAtValue(args)

        if len(_partialInfo.chosenActions) > 0:
            self.choices_made["customisedChoicesMade"] = _partialInfo.chosenActions
        if _partialInfo.nextActionOptions is not None:
            self.choices_made["customisedChoicesNext"] = _partialInfo.nextActionOptions
        self.customisedChoicesWalked = _partialInfo.actionsWalked

        # self.app_definition["options"] = options_out

    def _processCustomisingEntry(
        self,
        _customisations: dict[str, Any],
        x: dict[str, Any],
        _partialInfo: ProcessingPartialInfo,
    ) -> list[dict[str, Any]]:
        x["usage"] = "next"
        extra_options = []
        x["mustBeDirect"] = True

        _partialInfo.nextActionOptions = _customisations
        if _partialInfo.nonOptionArgIndex < len(_partialInfo.nonOptionArgs):

            chosenAction = _partialInfo.nonOptionArgs[
                _partialInfo.nonOptionArgIndex
            ].strip()

            if chosenAction in _customisations:

                _partialInfo.actionsWalked.append(_customisations[chosenAction])
                _partialInfo.chosenActions.append(chosenAction)
                self._groupInfoUpdate(_partialInfo)

                x["isChosen"] = True
                x["usage"] = "isChosen"
                x["group"] = chosenAction
                _func_callback = _customisations[chosenAction].get(
                    "_func_callback", None
                )
                if _func_callback is not None:
                    self.choices_made["functionCallback"] = _func_callback
                    self.choices_made["functionCallback_Reason"] = "+".join(
                        _partialInfo.chosenActions
                    )
                actionInfo = _customisations[chosenAction]
                appInfo_appendStr("APP_AS_USED.post_exe", f" {chosenAction}")
                self.parsedSettingsOut.update(actionInfo.get("settings", {}))

                extra_options = actionInfo.get("options", [])

        action_descriptions = {}
        action_keys = list(_customisations.keys())

        for key in _customisations:
            action_descriptions[key] = _customisations[key].get("description", "")
        x["descriptions"] = action_descriptions
        x["lookup"] = action_keys

        options_to_append = []
        if x.get("usage", None) is not None:
            options_to_append.append(x)
            for xx in extra_options:
                xx["group"] = "+".join(
                    [_action.title() for _action in _partialInfo.chosenActions]
                )
                options_to_append.append(xx)
        return options_to_append

    def _groupInfoUpdate(
        self,
        updateThis: ProcessingPartialInfo,
    ):
        groupInfo = updateThis.actionsWalked[-1]
        self.parsedSettingsOut.update(deepcopy(groupInfo.get("settings", {})))
        _bool = groupInfo.get("escapeArguments", None)
        if isinstance(_bool, bool):
            updateThis.escapeArguments = _bool

        if "description" in groupInfo:
            if self.parsedDescription != "":
                self.parsedDescription += " - "
            self.parsedDescription += str(groupInfo["description"])
        if "examples" in groupInfo:
            examples = groupInfo["examples"]
            if isinstance(examples, list):
                self.parsedExamples.extend([str(x) for x in examples])
            else:
                self.parsedExamples.append(str(examples))
        updateThis.nextActionOptions = None


class Define:

    def __init__(self, _app_definition: dict[str, Any]):
        self.app_definition = _app_definition

        ###############
        #
        self.app_definition["runningDir"] = os.getcwd()
        if "version" not in self.app_definition:
            self.app_definition["version"] = "0.0.0"
        if "description" not in self.app_definition:
            self.app_definition["description"] = "No description provided"

        ###############
        #
        self.appParameters = AppParameters(self.app_definition)
        self.appParameters.optionInsert(
            {
                "name": "help",
                "group": "~appAuto",
                "shortName": "",
                "description": "Gives help",
            }
        )

        self.appParameters.optionInsert(
            {
                "name": "version",
                "group": "~appAuto",
                "shortName": "",
                "description": f"Gives version information for this app: v{self.app_definition['version']}",
            }
        )

        _verbosityChoice = self.appParameters.optionInsert(
            {
                "name": "verbosity",
                "group": "~appAuto",
                "lookup": entries,
                "default": default,
                "defaultEnvVar": "UAPP_VERBOSITY",
                "description": "Set verbosity of messaging",
            }
        )
        appLog.setVerbosity(
            _verbosityChoice, silentOnFailure=True
        )  # < Ensures we get the detailed logging during parameter review

        #############################
        #
        # Styling
        #
        if self.app_definition.get("enableStyling", True) and styling.isSupported():
            styling.doDisable(
                self.appParameters.optionInsert(
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
                == "disable"
            )
        else:
            styling.doDisable(True)

        #############################
        #
        appConfig._reload(self.app_definition)

        self.orig_app_definition = deepcopy(self.app_definition)
        appInfo_set("APP_DEFINITION", deepcopy(self.app_definition))

    def getCallbackAndParams(self, args) -> Tuple[Any, dict[str, Any]]:
        params = self.parseParams(args)

        _actionFunction = self.appParameters.choices_made.get("functionCallback", None)

        if _actionFunction is None:
            error_exit(
                f"No action function found for the given arguments (AppDefinition appears to be incorrectly configured)"
            )

        appLog.print_info(
            f"Running {self.appParameters.choices_made.get('functionCallback_Reason',None)}"
        )

        return _actionFunction, params

    def giveHelp(self, file_dest=sys.stdout):
        for x in self.getHelp():
            file_dest.write(x.rstrip() + "\n")
        printVerbose_sysInfo()

    def getHelp(self) -> list[str]:

        lines_out: list[str] = []

        exeName = getExeName()
        exeNameDecorated = self.getExeName_decorated()

        verText = f"v{self.app_definition['version']}"

        params_txt = f" {self.appParameters.getOverviewAsText()}".strip()

        _customisedChoiceNext: dict[str, Any] | None = (
            self.appParameters.choices_made.get("customisedChoicesNext", None)
        )
        # customisedChoicesNext
        if not _customisedChoiceNext:
            lines_out.append(
                f"{PrettyText.padToWidth(exeNameDecorated, 32)} {PrettyText.padToWidth(verText, 13)} : {PrettyText.padToWidth(self.appParameters.parsedDescription, 90)}"
            )
            lines_out.append("")
            lines_out.append(
                f"Usage: {exeNameDecorated} [options] {params_txt}"
            )  # + {self.appParameters.getCustomisationChoicesAsText()}
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
                PrettyText.padToWidth(
                    exeNameDecorated, maxLen + len(prefix) + 2 + extrasLen
                )
                + " │ "
                + PrettyText.padToWidth(self.app_definition.get("description", ""), 90)
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
                        f"{prefix} {PrettyText.padToWidth(_nameToUse, maxLen)} {PrettyText.padToWidth(_params_out, extrasLen)}{suffix}"
                    )
                    prefix = " " * len(prefix)

        lines_out.append("")

        optionSummaries = ValueHelpSummaries()

        ############################################
        #
        # Add:  ['settings']: 'Setting Options'
        #
        shouldShowConfig = self.appParameters.getWalkedValue("show-config")
        if shouldShowConfig:

            appSettings = self.app_definition.get("settings", None)

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
        _nonDirect = [x for x in self.appParameters.avail if not (x.mustBeDirect())]
        otherName = "Basic Options"
        for paramObj in _nonDirect:
            _g = paramObj.get("group")
            if _g and (_g != "~appAuto"):
                optionSummaries.appendItem(f"{_g} Options", paramObj)
                otherName = "Common Options"

        # < Ensure '~appAuto' are last
        for paramObj in _nonDirect:
            _g = paramObj.get("group", None)
            if not _g:
                optionSummaries.appendItem(otherName, paramObj)

        for paramObj in _nonDirect:
            _g = paramObj.get("group", None)
            if _g == "~appAuto":
                optionSummaries.appendItem("Tailoring Options", paramObj)

        ############################################
        #
        # Print the options
        #
        lines_out.extend(optionSummaries.asLines())

        subscripts = ""
        for d in _nonDirect:
            subscripts += d.getValueHelpSubscripts()
        lines_out.extend(ParamSpec.getValueHelpExtraInfoFromSubscripts(subscripts))

        ############################################
        #
        # Add examples
        #

        if self.appParameters.parsedExamples:
            examplesOut: list[list[str]] = []

            for s in self.appParameters.parsedExamples:
                txt = exeName.join(s.split("<exeName>"))
                txt = exeNameDecorated.join(txt.split("<exeName+action>"))
                comment_suffix = ""
                x = txt.split("#")
                if len(x) > 1:
                    comment_suffix = " # " + x.pop()
                    txt = "#".join(x).strip()
                examplesOut.append(
                    [f" • {styling.asSuggestion(txt.strip())}", comment_suffix]
                )

            lines_out.append("")
            lines_out.append("Examples:")
            lines_out.extend(PrettyText.tableAsLines(examplesOut, dividers=" "))

        return lines_out

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

    def parseParams(self, args: list[str] | None = None) -> dict[str, Any]:
        global g_runningApp
        g_runningApp = self

        if args is None:
            args = sys.argv[1:]

        if "--version" in args:
            self.dumpVersion()
            doHalt("Version Info - Exiting", suggestSilent=True)
            sys.exit()

        self.app_definition = deepcopy(self.orig_app_definition)

        self.appParameters.doParsing(self.app_definition, args)

        if appConfig.hasContents() and self.appParameters.getWalkedValue("show-config"):
            if self.app_definition.get(
                "show-config", None
            ) == self.appParameters.getWalkedValue("show-config"):
                groupName = "~appAuto"
            else:
                groupName = "+".join(
                    [
                        _action.title()
                        for _action in self.appParameters.choices_made[
                            "customisedChoicesMade"
                        ]
                    ]
                )

            self.appParameters.avail.append(
                ParamSpec(
                    {
                        "name": "config-view",
                        "group": groupName,
                        "shortName": "C",
                        "description": "Gives the current configuration",
                    }
                )
            )

        ####################################
        #

        # |x|if len(settings_out) > 0:
        # |x|    self.app_definition["settings"] = settings_out
        # |x|else:
        # |x|    self.app_definition.pop("settings", None)

        if "--debug-option=app-info" in args:
            obj = {"appDefinition": self.app_definition}
            print(Utils.asJsonStr(obj, indent=2))
            exit(0)

        ######################################
        #
        # Basic parameter review
        self._reviewParams(args)

        return self.options_chosen

    def _reviewParams(
        self,
        args,
    ):
        limitedExtraParams: int | str | None = self.app_definition.get(
            "additional_parameters", 0
        )
        appValue_escapeArguments: bool = self.app_definition.get(
            "escapeArguments", False
        )

        returnNoneInsteadOfThrowingError = False
        help_marker = "?" if self.appParameters.avail.containsShortName("-h") else "h"

        options_chosen: dict[str, Any] = {}
        non_option_args = []
        force_non_options = False

        loadIntoSpec: ParamSpec | None = None
        spec = None
        arg_cleaned = ""
        giveHelp = False

        if appConfig.hasContents():
            configOptions = appConfig
        else:
            configOptions = None

        for _arg in args:
            arg_cleaned = str(_arg)

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
            elif not arg_cleaned.startswith("-") or (force_non_options):
                non_option_args.append(arg_cleaned)
            elif arg_cleaned in (("-" + help_marker), "--help"):
                giveHelp = True
                returnNoneInsteadOfThrowingError = True
            elif configOptions is not None and (
                (arg_cleaned == "--config-view") or (arg_cleaned == "-C")
            ):
                print(configOptions.asText())
                returnNoneInsteadOfThrowingError = True
            else:
                #
                # Process option
                argMatched = False

                if (
                    configOptions is not None
                    and (arg_cleaned.startswith("--"))
                    and ("=" in arg_cleaned)
                ):
                    argMatched = configOptions.setting_applyIfMatches(
                        arg_cleaned.removeprefix("--").split("=", 1),
                        returnNoneInsteadOfThrowingError,
                    )

                if not argMatched:
                    spec, _value = self.appParameters.avail.getMatchedSpecAndValue(
                        arg_cleaned
                    )
                    if spec is not None:
                        argMatched = True
                        _name: str = spec.name()
                        if _value is None:
                            loadIntoSpec = spec
                        elif isinstance(_value, bool) and _value is True:
                            options_chosen[_name] = _value
                        else:
                            options_chosen[_name] = spec.load(
                                _value,
                                options_chosen.get(_name, None),
                                returnNoneInsteadOfThrowingError,
                            )

                if not (argMatched) and not (returnNoneInsteadOfThrowingError):
                    action_suffix = appInfo_get("APP_AS_USED.post_exe", "")
                    if action_suffix is None or (str(action_suffix).strip() == ""):
                        action_suffix = ""

                    error_exit(f"Unknown{action_suffix} option: {arg_cleaned}")

        if loadIntoSpec is not None:
            error_exit(f"Missing value for option: {arg_cleaned}")

            # |Logging| print_verbose(f"arg: {arg}")

        ##################################################################################################
        # Load non_option_args - either into _options ('mayBeDirect/mustBeDirect') or into 'remaining_args'
        #
        remaining_args = []
        for arg in non_option_args:
            remaining_arg = arg
            for spec in self.appParameters.avail:
                _name: str = spec.name()
                permit_direct = (spec.mayBeDirect() or spec.mustBeDirect()) and (
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
        for spec in self.appParameters.avail:
            _name: str = spec.name()
            if _name not in options_chosen:
                if "default" in spec:
                    _used_defaults.append(_name)
                    options_chosen[_name] = spec.defaultValue()
                elif spec.type() is type(None):
                    # Special case - the existance of it is the value - so if it is included we set it to True (eg: --verbosity=details)
                    # but if it is not included, we set it to False
                    _used_defaults.append(_name)
                    options_chosen[_name] = False
                elif not returnNoneInsteadOfThrowingError:

                    exampleOrNone = spec.getExample()
                    if exampleOrNone is not None:
                        try:
                            error_exit(
                                f"Missing required parameter: {styling.asError(spec.getParamFormat())}",
                                withSuggestion=appInfo_cmdWithVariant(
                                    spec, exampleOrNone
                                ),
                            )
                        except Exception:
                            pass

                    valueHelp = spec.getValueHelp(ParamSpec.InfoStyle.EXPECTED_SENTENCE)
                    if valueHelp == "":
                        valueHelp = spec.getParamFormat()

                    error_exit(
                        f"Missing required parameter: {styling.asError(valueHelp)}",
                        withSuggestion=True,
                    )
        if len(_used_defaults) > 0:
            appLog.print_tediousDetail(
                f"Used defaults for: {', '.join(_used_defaults)}"
            )

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

        appLog.print_tediousDetail(
            f"AS USED: " + Utils.asJsonStr(options_chosen, indent=2)
        )
        appLog.print_tediousDetail(f"Remaining Arguments: {remaining_args}")

        self.choices_made = {}
        self.choices_made["default_parameters"] = _used_defaults
        self.options_chosen = options_chosen
        appLog.print_tediousDetail(
            f"Choices made: {Utils.asJsonStr(self.choices_made, indent=2)}"
        )
        appLog.print_tediousDetail(
            f"ParsedParams: {Utils.asJsonStr(self.appParameters.avail, indent=2)}"
        )

        if giveHelp:
            self.giveHelp(sys.stdout)
            doHalt("Help Info Provided - Exiting", suggestSilent=True)
            sys.exit()


g_runningApp: Define | None = None

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


def getPrettyExceptionInfo(e: BaseException) -> Tuple[str, list[str]]:
    """summaryText,TraceLines"""
    traceLines = (
        "\n".join(traceback.format_exception(type(e), e, e.__traceback__))
    ).split(
        "\n"
    )  # < Some of the lines already have newlines, so we split them into separate lines

    summary = []
    for _line in traceLines:
        line = _line.strip()
        if line.startswith('File "'):
            summary = []
        elif line:
            summary.append(_line)

    sourceLeft = []
    if len(summary) >= 2:
        kind = summary[-1]
        _untrimmed = summary[0].rstrip()

        source = _untrimmed.lstrip()
        prefixToStrip = _untrimmed[: (len(_untrimmed) - len(source))]
        for x in summary[1:-1]:
            sourceLeft.append(x.removeprefix(prefixToStrip))
    else:
        kind = str(e)
        source = ""

    msg = f"Unexpected Error `{styling.asError(kind)}`"
    if source:
        msg += " from `"
        prefix = PrettyText.asSpaces(msg)
        msg += styling.asError(source) + "`"

        for x in sourceLeft:
            msg += "\n" + prefix + styling.asError(x)

    return msg, traceLines[:-3]


def exitOnException(e: BaseException, action: str | None = None) -> NoReturn:

    # |Logging| sys.stderr.write(f"\n⚠️  {type(e)}:{e} {e}\n")
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
    elif isHandled:
        error_exit(
            f"{action}{emsgSuffix}", withSuggestion=action.startswith("Missing value")
        )
    else:

        msg, traceLines = getPrettyExceptionInfo(e)
        msg += "\n"
        if appLog.isVerbose() or [x for x in os.environ if x.startswith("VSCODE_")]:
            msg += "\n".join([f"   [trace]: {x}" for x in traceLines])

        elif g_runningApp is not None:
            msg += f"Suggestion: {styling.asSuggestion(appInfo_cmdWithVariant(g_runningApp.appParameters.avail.get('verbosity'),'details'))} for more information"
        error_exit(msg, withSuggestion=False)


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
        if not withSuggestion:
            suggestionTxt = ""
        elif isinstance(withSuggestion, str):
            suggestionTxt = withSuggestion.removeprefix("Suggest:").strip()
        else:
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
