#########################################################################
#
# appHelp
from copy import deepcopy
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

from ukko_pylibs.basic.logger import appLog

from ukko_pylibs.basic.simpleUtils import PrettyText, EscapeMgr, Utils
from ukko_pylibs.basic.prettyTable import PrettyTable


from ukko_pylibs.basic import styling
from ukko_pylibs.app.class_ParamSpec import (
    ParamSpec,
    ParamSpecList,
    ValueHelpSummaries,
)
from ukko_pylibs.app.appChoices import AppChoices
from ukko_pylibs.app.class_Configuration import Configuration

#
################################################################################


def appDoco_replaceTemplateMarkers(appChoices: AppChoices, docoWithMarkers: Any) -> str:
    from ukko_pylibs.app.appSupport import app  # < Avoid circular import

    if docoWithMarkers is None:
        return ""
    txt = str(docoWithMarkers)

    REPLACEMENTS = {
        "SAMPLES_DIR": os.path.abspath(f"{app.getMainDir()}/samples"),
        "exeName": str(appChoices.appValue("exeName")),
        "exeName+action": str(appChoices.appValue("exeName"))
        + appChoices.customisingChoicesMade_withLeadingSpace,
    }

    for oldValue, newValue in REPLACEMENTS.items():
        _parts = txt.split("<" + oldValue + ">")
        if len(_parts) > 1:
            if oldValue.endswith("_DIR"):
                if not os.path.isdir(newValue):
                    appLog.print_warning(f"Missing <{oldValue}> directory: {newValue}")
                newValue = Utils.pathAsDisplay(newValue)
            if oldValue.endswith("_FILE"):
                if not os.path.isdir(newValue):
                    appLog.print_warning(f"Missing <{oldValue}> file: {newValue}")
                newValue = Utils.pathAsDisplay(newValue)
            txt = newValue.join(_parts)

    return txt


def getAppHelp_asLines(
    appChoices: AppChoices,
    availParams: ParamSpecList,
    appConfig: Configuration,
    shorterVersion=False,
) -> list[str]:
    #
    # Full done from only:
    #   * self.appChoices
    #   * self.availParams

    #
    visibleParams = [
        x
        for x in availParams
        if x.isNotHidden() and not (x.isCustomisingOptions() or x.isCustomisingChoice())
    ]

    exeName = str(appChoices.appValue("exeName"))
    exeNameDecorated = exeName + appChoices.customisingChoicesMade_withLeadingSpace

    verText = f"v{appChoices.appValue('version')}"

    # |Logging| from ukko_pylibs.app.appSupport import print_cyan
    # |Logging| print_cyan(visibleParams)

    # |if _customisedChoiceNext:
    # |    shorterVersion=True

    titleAndUsageTable = PrettyTable.Table()

    titleAndUsageTable.appendRowList(
        [
            styling.asBold(exeNameDecorated),
            styling.asBold(verText),
            ": " + styling.asBold(appChoices.appValue("description")),
        ]
    )
    if not shorterVersion:
        for x in appChoices.appValue("versions_extra") or []:
            titleAndUsageTable.appendRowList(["", "", "| " + styling.asBold(x)])
    titleAndUsageTable.appendRowBlank()

    _examplesOut = deepcopy(appChoices.appValue("examples") or [])

    #########################################
    #

    usageSuggestions = getUsageSuggestions(
        appChoices, getUsageSuggestions
    )  # < list[ (namePlus,options,description] :

    if appChoices.customisingChoices_next:
        for action, entry in appChoices.customisingChoices_next.items():
            _examplesOut.extend(customisedChoicePart_getTopSuggestions(action, entry))

    prefix = f"Usage: "
    for usage in usageSuggestions:
        titleAndUsageTable.appendRowList(
            [
                prefix + styling.asSuggestion(usage[0]),
                styling.asSuggestion(usage[1]),
                usage[2],
            ]
        )

    lines_out: list[str] = []
    lines_out.extend(PrettyTable.Rendered(titleAndUsageTable).asLines())
    lines_out.append("")

    ############################################
    #
    # Option Summaries
    #
    optionSummaries = ValueHelpSummaries()

    #
    # Step 1: ['settings']: 'Setting Options'
    #
    shouldShowConfig = appChoices.appValue("show-config")
    if shouldShowConfig:

        appSettings = appChoices.appValue("settings")

        if appSettings:
            for entry_name, entry_params in appSettings.items():
                _spec = {
                    "group": "settings",
                    "name": entry_name,
                    "shortName": "",
                    "position": 10,
                }
                _spec.update(entry_params)
                _spec["default"] = appConfig.setting_getPreUser(
                    entry_name
                )  # < After update to overwrite it
                optionSummaries.appendItem("Setting Options", _spec)

    #
    # Step 2 - Visible Parameters
    #
    for paramObj in visibleParams:
        _g = paramObj.get("group")
        if not _g:
            _g = "Basic"
        elif _g == "~appAuto":
            _g = "Tailoring Options"
        titleNote = (
            str(_g).title().removesuffix(" Options").replace("_", " ") + " Options"
        )
        optionSummaries.appendItem(titleNote, paramObj)

    #
    # Done
    #
    lines_out.extend(optionSummaries.asLines())

    subscripts = ""
    for d in visibleParams:
        subscripts += d.getValueHelpSubscripts()
    lines_out.extend(ParamSpec.getValueHelpExtraInfoFromSubscripts(subscripts))

    #
    ############################################

    ############################################
    #
    # Add examples
    #
    if shorterVersion:
        lines_out.append("")
    else:
        examplesTable, tableStyling = examplesTableAndRenderOptions_create(
            appChoices, _examplesOut
        )

        if examplesTable.hasData():

            lines_out.append("")
            lines_out.append("Examples:")
            # |x| print(Utils.asJsonStr(examplesOut.asDict(),indent=2))

            # |x| print(Utils.asJsonStr(examplesOut.asDict(),indent=2))
            for line in PrettyTable.Rendered(examplesTable, tableStyling).asLines():
                lines_out.append(f" • {line}")

    return [line.replace("\xa0", " ").rstrip() for line in lines_out]


def popLastFromList(entries: list[str], suffixMarker: str) -> str:
    if len(entries) == 0:
        return ""
    last = entries[-1]
    if not last.startswith(suffixMarker):
        return ""
    return entries.pop()


def examplesTableAndRenderOptions_create(
    appChoices, _examplesOut: list[list[str]]
) -> Tuple[PrettyTable.Table, Any]:

    examplesTableOut = PrettyTable.Table()
    tableStyling: list[int | None] | None = None

    if not _examplesOut:
        return examplesTableOut, tableStyling

    commentsOut: list[str | None] = []
    # pipeOut: list[str] = []
    for s in _examplesOut:
        if isinstance(s, str):
            txt, comment_suffix = _popLastFromText(
                appDoco_replaceTemplateMarkers(appChoices, s), "#"
            )
            # txt, pipe_suffix = _popLastFromText(textSubstitute(s), "|")
            examplesTableOut.appendRowList([styling.asSuggestion(txt)])
            commentsOut.append(comment_suffix)
            # pipeOut.append(pipe_suffix)
        elif isinstance(s, dict):
            tableStyling = s.get("colWidths")

        else:
            line_out = [
                appDoco_replaceTemplateMarkers(appChoices, x).strip() for x in s
            ]

            comment = popLastFromList(line_out, "#")
            # pipe=popLastFromList(line_out,'|')
            commentsOut.append(comment)
            examplesTableOut.appendRowList([styling.asSuggestion(x) for x in line_out])
            # pipeOut.append(pipe)

    examplesTableOut.appendColList(commentsOut)
    return examplesTableOut, tableStyling


def replaceWithin(txt: str | list[str], needle: str, replacement: str):
    if isinstance(txt, str):
        return txt.replace(needle, replacement)
    elif isinstance(txt, list):
        return [replaceWithin(x, needle, replacement) for x in txt]
    else:
        return txt


def customisedChoicePart_getTopSuggestions(
    action: str, entry: dict[str, Any]
) -> list[str | list[str]]:

    results = []

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
        results.append(topSuggestion)
    elif isinstance(topSuggestion, list):
        results.append(topSuggestion)

    return results


def getUsageSuggestions(appChoices, visibleParams) -> list[list[str]]:
    """Returns a list of [namePlus,params,description]"""

    _customisedChoiceNext = appChoices.customisingChoices_next

    lines_out = []
    exeName = appChoices.appValue("exeName")
    if _customisedChoiceNext is None:

        #########################################
        #  Calculate: `mentionOtherOptions`  (to use with 'params_txt' in the usage line)
        #
        params_txt, _mentioned = appChoices.getOverviewAsTextAndParams()

        _unmentioned = [
            x
            for x in visibleParams
            if not x.name() in _mentioned and (x.get("group") != "~appAuto")
        ]
        mentionOtherOptions = "" if len(_unmentioned) == 0 else " [options]"

        lines_out.append(
            [
                [
                    str(exeName)
                    + appChoices.customisingChoicesMade_withLeadingSpace
                    + mentionOtherOptions
                    + " "
                    + params_txt
                ]
            ]
        )

    else:
        directPrefixes = [
            {
                "name": key,
                "description": paramObj.get("description", ""),
                "options": paramObj.get("options", None),
            }
            for key, paramObj in _customisedChoiceNext.items()
        ]

        directPrefixes.append({"blankLine": True})
        directPrefixes.append(
            {
                "name": "<action> --help",
                "options": None,
                "description": "Gives help information on the action (From the above list)",
            }
        )

        for _entry in directPrefixes:
            if _entry.get("blankLine", False):
                lines_out.append(["", "", ""])
            else:

                _nameToUse = exeName
                if _entry.get("noDecoration", False):
                    _nameToUse += appChoices.customisingChoicesMade_withLeadingSpace

                _nameToUse = _nameToUse + " " + _entry.get("name", "")
                _params_out = "[options …]" if _entry.get("options", None) else ""
                _value = _entry.get("description", "")

                lines_out.append(
                    [
                        styling.asSuggestion(_nameToUse),
                        styling.asSuggestion(_params_out),
                        "" if _value == "" else f"| {_value}",
                    ]
                )

    return lines_out


def _popLastFromText(txt: str, suffixMarker: str) -> tuple[str, str]:
    x = txt.split(suffixMarker)
    suffix = ""
    if len(x) > 1:
        suffix = suffixMarker + " " + x.pop().strip()
        txt = "#".join(x).strip()
    return txt, suffix
