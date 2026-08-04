#########################################################################
#
# appHelp
from copy import deepcopy
import os

from typing import Any, Tuple


from .appChoices import AppChoices
from .class_Configuration import Configuration
from . import appSupport as app
from .class_ParamSpec import (
    ParamSpec,
    ParamSpecList,
    ValueHelpSummaries,
)


from appLogging import appLog

import prettyText
import ukkoUtils

from ukkoStyling import styling


from prettyData import PrettyData


def appDoco_replaceTemplateMarkers(appChoices: AppChoices, docoWithMarkers: Any) -> str:

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
                newValue = ukkoUtils.pathAsDisplay(newValue)
            if oldValue.endswith("_FILE"):
                if not os.path.isdir(newValue):
                    appLog.print_warning(f"Missing <{oldValue}> file: {newValue}")
                newValue = ukkoUtils.pathAsDisplay(newValue)
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

    # |Logging| from appAssist import print_cyan
    # |Logging| print_cyan(visibleParams)

    # |if _customisedChoiceNext:
    # |    shorterVersion=True

    titleAndUsageTable = PrettyData.Contents()

    titleAndUsageTable.appendRowList(
        [
            styling.asBold(exeNameDecorated),
            styling.asBold(verText),
            ": " + styling.asBold(appChoices.appValue("description")),
        ]
    )
    if not shorterVersion:
        for x in appChoices.appValue("versions_extra") or []:
            titleAndUsageTable.appendRowList(["", "", "  " + styling.asBold(x)])
    titleAndUsageTable.appendRowBlank()

    _examplesOut = deepcopy(appChoices.appValue("examples") or [])

    #########################################
    #

    usageSuggestions = getUsageSuggestions(appChoices, visibleParams)

    prefix = f"Usage: "
    for usage in usageSuggestions:
        if isinstance(usage, str):
            titleAndUsageTable.appendRowList([prefix + styling.asSuggestion(usage)])
        else:
            titleAndUsageTable.appendRowList(
                [
                    prefix + styling.asSuggestion(usage[0]),
                    styling.asSuggestion(usage[1]),
                    usage[2],
                ]
            )
        prefix = prettyText.asSpaces(prefix)

    _examplesOut.extend(
        customisedChoicePart_getTopSuggestions(appChoices.customisingChoices_next)
    )

    lines_out: list[str] = []
    lines_out.extend(PrettyData.Rendered(titleAndUsageTable).asTextLines())
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
        titleNote = str(_g).removesuffix(" Options")

        if "_" in titleNote or titleNote.islower():
            titleNote = titleNote.replace("_", " ").title()

        titleNote += " Options"

        optionSummaries.appendItem(titleNote, paramObj)

    #
    # Done
    #
    lines_out.extend(optionSummaries.asTextLines())

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

            for line in PrettyData.Rendered(examplesTable, tableStyling).asTextLines():
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
) -> Tuple[PrettyData.Contents, Any]:

    examplesTableOut = PrettyData.Contents()
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
    customisedChoiceEntry: dict[str, Any] | None,
) -> list[str | list[str]]:

    _examplesOut = []
    if not (customisedChoiceEntry):
        return _examplesOut

    for action, entry in customisedChoiceEntry.items():

        actionSuggestions: list[str | list[str]] = []

        if "topSuggestion" in entry:
            actionSuggestions.append(entry["topSuggestion"])
        else:
            kindExamples = entry.get("examples", [])
            if len(kindExamples) > 0:
                actionSuggestions.append(kindExamples[0])

        if "options" in entry:
            for x in entry["options"]:
                actionSuggestions.extend(
                    customisedChoicePart_getTopSuggestions(x.get("customising"))
                )

        for _suggestion in actionSuggestions:
            suggestion = replaceWithin(
                _suggestion,
                "<exeName+action>",
                "<exeName+action> "
                + action,  # (' '.join([escapeIfNeeded(action) for action in actions_depth]))
            )
            if isinstance(suggestion, str):
                suggestion = suggestion.strip()

                _restyle = suggestion.startswith("<exeName+action>")
            else:
                _restyle = False

            if _restyle and isinstance(suggestion, str):

                comment_suffix = ""
                x = suggestion.split("#")
                if len(x) > 1:
                    comment_suffix = " # " + x.pop()
                    suggestion = "#".join(x).strip()

                suggestion = suggestion.split(" ") + [comment_suffix]

            if isinstance(suggestion, str):
                _examplesOut.append(suggestion)
            elif isinstance(suggestion, list):
                _examplesOut.append(suggestion)

    return _examplesOut


def getUsageSuggestions(appChoices, visibleParams) -> list[Tuple[str, str, str] | str]:
    """Returns a list of [namePlus,params,description]"""

    _customisedChoiceNext = appChoices.customisingChoices_next

    exeName = appChoices.appValue("exeName")

    #########################################
    #  Calculate: `mentionOtherOptions`  (to use with 'params_txt' in the usage line)
    #
    params_base_text, params_extra_text, _mentioned = (
        appChoices.getOverviewAsTextAndParams()
    )

    _unmentioned = [
        x.name()
        for x in visibleParams
        if not x.name() in _mentioned and (x.get("source") != "~appAuto")
    ]

    _usageGroups: list[dict | None] = []
    if _customisedChoiceNext is None:
        _usageGroups.append(
            {"options": _unmentioned, "_extraParams": params_extra_text}
        )
    else:
        for key, paramObj in _customisedChoiceNext.items():
            _usageGroups.append(
                {
                    "name": key,
                    "description": paramObj.get("description", ""),
                    "options": paramObj.get("options", None),
                }
            )
        _usageGroups.append(None)
        _usageGroups.append(
            {
                "name": "<action> --help",
                "description": "Gives help information on the action (From the above list)",
            }
        )
    lines_out: list[Tuple[str, str, str] | str] = []

    for _entry in _usageGroups:
        if _entry is None:
            lines_out.append("")
        else:
            _description = _entry.get("description", "")
            _extraParams = _entry.get("_extraParams", "")

            _base = " ".join(
                f"{exeName} {params_base_text} {_entry.get('name','')}".split()
            )

            lines_out.append(
                (
                    styling.asSuggestion(_base),
                    styling.asSuggestion(
                        "[options …]" if _entry.get("options", None) else ""
                    ),
                    styling.asSuggestion(_extraParams)
                    + ("" if _description == "" else f"| {_description}"),
                )
            )

    return lines_out


def _popLastFromText(txt: str, suffixMarker: str) -> tuple[str, str]:
    x = txt.split(suffixMarker)
    suffix = ""
    if len(x) > 1:
        suffix = suffixMarker + " " + x.pop().strip()
        txt = "#".join(x).strip()
    return txt, suffix
