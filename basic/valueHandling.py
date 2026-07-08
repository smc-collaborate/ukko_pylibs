from copy import deepcopy
import json
from typing import Any, Tuple
import sys

################################################################################
#
# Add project root directory to system path

import os

shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)


from ukko_pylibs.basic.simpleUtils import Utils
from ukko_pylibs.app.appSupport import appLog

################################################################################


class ValueLimitations:
    def __init__(
        self,
        kind: str | None = None,
        minValue: float | None = None,
        maxValue: float | None = None,
    ):
        self.kind: str | None = kind
        self.minValue: float | None = minValue
        self.maxValue: float | None = maxValue
        self._errors = []
        if not self._recalc():
            self._appendError(f"Unable to create {self.asDict()}")

    def _asText(self) -> str:

        myKindRange = ValueLimitations.kind_numericInfo(self.kind)
        if myKindRange == (self.minValue, self.maxValue):
            return self.kind or "Unknown"
        if self.minValue is not None and self.maxValue is not None:
            return f"{self.kind if self.kind not in ['float',None] else ''} [{self.minValue}…{self.maxValue}]".strip()
        elif self.minValue is not None:
            return f"{self.kind if self.kind not in ['float',None] else ''} ≥ {self.minValue}".strip()
        elif self.maxValue is not None:
            return f"{self.kind if self.kind not in ['float',None] else ''} ≤ {self.maxValue}".strip()
        elif self.kind:
            return self.kind
        else:
            return "Any"

    def asDict(self) -> dict[str, Any] | str:
        obj: dict[str, Any] = {}

        if not self._errors:
            return self._asText()
        else:
            obj["asText"] = self._asText()
            if self.kind is not None:
                obj["kind"] = self.kind
            if self.minValue is not None:
                obj["minValue"] = self.minValue
            if self.maxValue is not None:
                obj["maxValue"] = self.maxValue
            if self._errors:
                obj["errors"] = self._errors
            return obj

    def doValidateValue(self, value: Any) -> Tuple[str | None, Any]:
        """Returns (errorMsg, refinedValue)"""

        def returnFailure(msg: str) -> Tuple[str, Any]:
            return f"{Utils.asJsonStr(value)} is {msg}. Valid: {self._asText()}", value

        if self.kind == "float":
            try:
                valueOut = float(value)
            except Exception:
                return returnFailure("not numeric")
        elif self.kind == "bool":
            if isinstance(value, bool):
                return None, value
            elif isinstance(value, (int, float)) and value in (0, 1):
                return None, bool(value)
            elif isinstance(value, str) and value.lower() in ("true", "false"):
                return None, (value.lower() == "true")
            else:
                return returnFailure("not boolean (0,1,true,false)")
        elif self.isNumeric():
            try:
                valueOut = int(value)
            except Exception:
                return returnFailure("not an integer")
        elif self.kind:
            return returnFailure(f"not a recognized type `{self.kind}`")
        else:
            return None, value
        #
        # Now 'valueOut' is numeric, and we can check the range
        #
        if self.minValue is not None and valueOut < self.minValue:
            return returnFailure(f"less than minimum {self.minValue}")
        if self.maxValue is not None and valueOut > self.maxValue:
            return returnFailure(f"greater than maximum {self.maxValue}")
        # @todo: Add validation of time_ns and time_n|immediate types

        return None, valueOut

    def isNumeric(self) -> bool:
        return self.kind in ValueLimitations.NUMERIC_RANGES

    def merge(self, other: "ValueLimitations"):
        self._limitRange(other.minValue, other.maxValue)

        _otherRange = ValueLimitations.kind_numericInfo(other.kind)
        if _otherRange:
            self._limitRange(_otherRange[0], _otherRange[1])

        #####################
        # Merge Kinds
        if other.kind and (self.kind != other.kind):
            if not self.kind:
                self.kind = other.kind

        if not self._recalc():
            self._appendError(f"Unable to merge: {other} -> {self}")

    def _recalc(self) -> bool:
        _numericRange = ValueLimitations.kind_numericInfo(self.kind)
        if _numericRange is None:
            return True

        self._limitRange(_numericRange[0], _numericRange[1])
        _newKind = ValueLimitations.kind_getSmallestEnclosingRange(
            self.minValue, self.maxValue
        )
        if _newKind is None:
            return False
        self.kind = _newKind
        return True

    ##################
    #
    def _appendError(self, msg: str):
        if msg and not msg in self._errors:
            self._errors.append(msg)

    @staticmethod
    def kind_getSmallestEnclosingRange(min: Any | None, max: Any | None) -> str | None:
        if min is None and max is None:
            return None

        for kind, (kindMin, kindMax) in ValueLimitations.NUMERIC_RANGES.items():
            if (min is None or min >= kindMin) and (max is None or max <= kindMax):
                return kind

        return None

    #######################################################
    # This smallest to largest
    #
    NUMERIC_RANGES = {
        "bool": (0, 1),
        "u8": (0, 2**8 - 1),
        "s8": (-(2**7), 2**7 - 1),
        "u16": (0, 2**16 - 1),
        "s16": (-(2**15), 2**15 - 1),
        "u32": (0, 2**32 - 1),
        "s32": (-(2**31), 2**31 - 1),
        "timestamp_ns": (1, 2**64 - 2),
        "timestamp_ns|immediate": (0, 2**64 - 2),
        "u64": (0, 2**64 - 1),
        "s64": (-(2**63), 2**63 - 1),
        "uint": (0, 2**64 - 1),
        "int": (-(2**63), 2**63 - 1),
        "float": (float("-inf"), float("inf")),
    }

    @staticmethod
    def kind_numericInfo(kind: str | None) -> Tuple[float, float] | None:
        return (
            ValueLimitations.NUMERIC_RANGES[kind]
            if kind and kind in ValueLimitations.NUMERIC_RANGES
            else None
        )

    def _limitRange(self, otherMin: float | None, otherMax: float | None):
        if otherMin is not None:
            if self.minValue is None or otherMin > self.minValue:
                self.minValue = otherMin
        if otherMax is not None:
            if self.maxValue is None or otherMax < self.maxValue:
                self.maxValue = otherMax


class ValueInfo:
    def __init__(
        self,
        limitations: ValueLimitations | None = None,
        defaultValue: Any | None = None,
    ):
        self.limitations: ValueLimitations | None = limitations
        self.defaultValue: Any | None = defaultValue

    def asDict(self):
        obj: dict[str, Any] = {}
        if self.limitations is not None:
            obj["limitations"] = self.limitations.asDict()
        if self.defaultValue is not None:
            obj["defaultValue"] = self.defaultValue
        return obj

    def merge(self, other: "ValueInfo"):
        if self.limitations is None:
            self.limitations = deepcopy(other.limitations)
        elif other.limitations is not None:
            self.limitations.merge(other.limitations)

        if self.defaultValue is None:
            self.defaultValue = deepcopy(other.defaultValue)
        elif other.defaultValue is not None and self.defaultValue != other.defaultValue:
            appLog.print_warning(
                f"Unable to merge default values: {self.defaultValue} <- {other.defaultValue}"
            )


class ValueGroup(dict[str, ValueInfo]):

    def asDict(self):
        outObj = {}
        for name, value in self.items():
            if isinstance(value, ValueInfo):
                outObj[name] = value.asDict()
            else:
                outObj[name] = "???"

        return outObj

    def merge(self, other: "ValueGroup"):
        for name, value in other.items():
            if name not in self:
                self[name] = deepcopy(value)
            elif isinstance(value, ValueInfo) and isinstance(self[name], ValueInfo):
                self[name].merge(value)
            else:
                appLog.print_warning(
                    f"Unable to merge values for '{name}': {Utils.asJsonStr(self[name])} <- {Utils.asJsonStr(value)}"
                )


def parseNamedParams_orErrMsg(paramsTxt: str) -> dict[str, Any] | str:

    if (paramsTxt != "") and (not paramsTxt.startswith("{")):
        paramsTxt = "{" + paramsTxt + "}"

    if paramsTxt == "":
        return {}

    try:
        import json5

        params = json5.loads(paramsTxt)
        if isinstance(params, dict) and all(isinstance(k, str) for k in params.keys()):
            return params
        return f"Parsed `{paramsTxt}` as a non-dictionary type: {type(params)}"
    except Exception as e:
        return f"Unable to parse: `{paramsTxt}` ({e})"
