#########################################################################
#
# app.define- a helper class for command line applications
#             It basically is the 'app.definition'
#

import math
import os

from typing import Any
from .class_ParamSpec import (
    ParamSpecAndValue,
    ParamSpecList,
)
from ukkoDataFormats import JsonDict, DataContents
import sysInfo

#
################################################################################


class AppChoices:
    """This is the final results of what the user has chosen, after parsing the command line arguments and applying any defaults
    See AppParameterParsing for details of HOW this is generated - but the results are deliberately kept separate to avoid the messiness.
    """

    def __init__(
        self,
        params: dict[str, Any],
        appValues: dict[str, Any],
        defaults_used: list[str],
        nextCustomisationAvailForChoice: dict[str, Any] | None,
        customisingChoicesMade_withLeadingSpace: str,
    ):
        self.params = params
        self.appValues = appValues
        self.defaultsUsed = defaults_used
        self.customisingChoices_next = nextCustomisationAvailForChoice
        self.customisingChoicesMade_withLeadingSpace = (
            customisingChoicesMade_withLeadingSpace
        )

    def appValue(self, name: str) -> Any | None:

        from .appSupport import appValueOrDefault

        return appValueOrDefault(self.appValues, name)

    def paramChoice(self, name: str, default: Any | None = None) -> Any | None:
        return self.params.get(name, default)

    def asDict(self) -> dict[str, Any]:

        obj: dict[str, Any] = {
            "params": self.params,
            "appValues": self.appValues,
        }
        if self.customisingChoicesMade_withLeadingSpace != "":
            obj["customisingChoices_made"] = (
                self.customisingChoicesMade_withLeadingSpace.removeprefix(" ")
            )
        if self.defaultsUsed:
            obj["defaultsUsed"] = self.defaultsUsed
        if self.customisingChoices_next:
            obj["customisingChoices_next"] = self.customisingChoices_next
        return obj

    def __getitem__(self, key):
        return self.paramChoice(key)

    def param_asDict(self, name) -> dict:
        _value = self.paramChoice(name)
        if _value is None:
            return {}
        else:
            return _value.contents if isinstance(_value, JsonDict) else _value

    def param_asDictOrNone(self, name) -> dict | None:
        _value = self.paramChoice(name)
        if _value is None:
            return None
        else:
            return _value.contents if isinstance(_value, JsonDict) else _value

    def asStr(self, name) -> str:
        _value = self.paramChoice(name)
        return "" if _value is None else str(_value)

    def asList(self, name) -> list[Any]:
        _value = self.paramChoice(name)
        return [] if _value is None else list(_value)

    def asInt(self, name) -> int:
        _value = self.paramChoice(name)
        return 0 if _value is None else int(_value)

    def asBool(self, name) -> bool:
        _value = self.paramChoice(name)
        return False if _value is None else bool(_value)

    def asFloat(self, name) -> float:
        _value = self.paramChoice(name)
        return math.nan if _value is None else float(_value)

    def get(self, key, default=None):
        return self.paramChoice(key, default)

    def getDataContents_orNone(self, key) -> DataContents | None:
        return self.paramChoice(key, None)

    def getOverviewAsTextAndParams(self) -> tuple[str, str, list[str]]:
        param_info = ""
        summarisedParams: list[str] = []
        for spec in self.getOptions():
            usage = spec.getHelpSummary()
            if usage and usage.summaryAdd_param:
                param_info += usage.summaryAdd_param
                summarisedParams.append(spec.name())

        additionalParams = self.appValues.get("additional_parameters", None)
        return (
            param_info.strip(),
            ("" if not additionalParams else f" -- {additionalParams}"),
            summarisedParams,
        )

    def getOptions(self) -> ParamSpecList:
        return ParamSpecList(self.appValues.get("options", []))


class AppParamParseResults:
    def __init__(
        self,
        paramSpec_chosen: dict[str, ParamSpecAndValue],
        errors: list[str],
        paramSpec_avail: ParamSpecList,
        appChoices: AppChoices,
    ):
        self.paramSpec_chosen = paramSpec_chosen
        self.errors = errors
        self.paramSpec_avail = paramSpec_avail
        self.appChoices = appChoices
        self.runEnvironment = {
            "runningDir": os.getcwd(),
            "python": sysInfo.pyInfo_asDict(),
        }

    def asBashParams(self) -> dict[str, str]:
        results: dict[str, str] = {}
        for paramChosen in self.paramSpec_chosen.values():
            if len(paramChosen.asProvidedArg) > 0:
                results[paramChosen.name()] = " ".join(
                    [
                        paramChosen.spec.asBashParam(arg)
                        for arg in paramChosen.asProvidedArg
                    ]
                )

        return results

    def asDict(self) -> dict[str, Any]:
        obj = {
            "paramSpec_chosen": {
                k: v.asDict() for k, v in self.paramSpec_chosen.items()
            },
            "paramSpec_avail": [x.asDict() for x in self.paramSpec_avail],
            "appChoices": self.appChoices.asDict(),
        }

        if self.errors:
            obj["errors"] = self.errors

        return obj
