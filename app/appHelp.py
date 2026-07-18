#########################################################################
#
# appHelp
import os
import sys
from typing import Any

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import (
    PrettyTable,
    PrettyText,
    EscapeMgr,
)
from ukko_pylibs.basic.logger import appLog
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

    lines_out: list[str] = []

    exeName = str(appChoices.appValue("exeName"))
    exeNameDecorated = exeName + appChoices.customisingChoicesMade_withLeadingSpace

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
    _customisedChoiceNext: dict[str, Any] | None = appChoices.customisingChoices_next

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
                    exeName if _entry.get("noDecoration", False) else exeNameDecorated
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
                    exeName if _entry.get("noDecoration", False) else exeNameDecorated
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
                txt, comment_suffix = _popLastFromText(
                    _exeSubstitute(s, exeName, exeNameDecorated), "#"
                )
                # txt, pipe_suffix = _popLastFromText(textSubstitute(s), "|")
                examplesOut.appendRow([styling.asSuggestion(txt)])
                commentsOut.append(comment_suffix)
                # pipeOut.append(pipe_suffix)
            elif isinstance(s, dict):
                if "colWidths" in s:
                    tableColWidths = s.get("colWidths")

            else:
                line_out = [
                    _exeSubstitute(str(x), exeName, exeNameDecorated).strip() for x in s
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


def _popLastFromText(txt: str, suffixMarker: str) -> tuple[str, str]:
    x = txt.split(suffixMarker)
    suffix = ""
    if len(x) > 1:
        suffix = suffixMarker + " " + x.pop().strip()
        txt = "#".join(x).strip()
    return txt, suffix


def _exeSubstitute(txt: str, exeName: str, exeNameDecorated: str) -> str:
    txt = txt.replace("<exeName>", exeName)
    txt = txt.replace("<exeName+action>", exeNameDecorated)
    return txt
