#########################################################################
#
# A helper class
#
import json
import os
import sys
from typing import Any, Tuple
from copy import deepcopy
from pathlib import Path

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{Path(__file__).parent}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import DictUtils, Utils
from ukko_pylibs.basic.class_SimpleLogger import SimpleLogger
from ukko_pylibs.basic.class_HandledException import HandledException
from ukko_pylibs.appAssist.class_ParamSpec import ParamSpec
from ukko_pylibs.basic import styling

#
################################################################################


def _recursive_merge(dict1: dict, dict2: dict) -> dict:
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _recursive_merge(result[key], value)
        else:
            result[key] = value
    return result


class Configuration:

    def __init__(self, logger: SimpleLogger, configDict: dict[str, Any] | None = None):

        self.__logger = logger
        self._reload(configDict)

    def _reload(self, configDict: dict[str, Any] | None = None):
        self.__logger.print_verbose(f"Reloading configuration from {configDict}")
        self._defaults = deepcopy(DictUtils.getDict(configDict, "config/defaults"))
        self._settingsSpec = DictUtils.getDict(configDict, "settings")
        for key, value in self._settingsSpec.items():
            if "default" in value:
                DictUtils.set(self._defaults, ["settings", key], value["default"])

        _loadedFromFile = {}

        config_fname = DictUtils.get(configDict, "config/fname")
        self.notes: list[str] = []
        if config_fname is not None:
            self.__logger.print_verbose(
                f"Loading configuration from file {config_fname}"
            )

            try:
                with open(config_fname, "r", encoding="utf-8") as f:
                    _loadedFromFile = json.load(f)
                    self.notes.append(
                        f"Loaded config file '{Utils.pathAsDisplay(config_fname)}'"
                    )
            except Exception as e:
                self.log_error(f"Unable to load config file '{config_fname}'", e)
                self.notes.append(
                    f"Unable to load from config file '{Utils.pathAsDisplay(config_fname)}'"
                )
        self.BEFORE_USER_CUSTOMISING = _recursive_merge(self._defaults, _loadedFromFile)
        self.CONFIG_USED = deepcopy(self.BEFORE_USER_CUSTOMISING)

    def hasContents(self) -> bool:
        """Even if the contents is just an error message say WHY we didn't have contents"""
        return len(self.CONFIG_USED) > 0 or len(self.notes) > 0

    def asText(self) -> str:
        if not self.hasContents():
            return ""

        txt = "Current configuration:\n"
        txt += json.dumps(self.CONFIG_USED, indent=4) + "\n"
        txt += "\n".join(self.notes)
        return txt

    def config_get(self, key: str | list[str] = "") -> Any:
        if key == "":
            return self.CONFIG_USED

        result = DictUtils.get(self.CONFIG_USED, key, None)
        if result is None:
            self.log_error(f"Config key '{key}' not found - nor found in defaults")
        return result

    def setting_get_default(self, key: str) -> Any:

        result = DictUtils.get(self._defaults, "settings/" + key, "!!NOT_FOUND!!")

        if result == "!!NOT_FOUND!!":
            if not key.startswith("!"):
                self.log_error(f"Default setting for key '{key}' not found")
            result = None

        return result

    def setting_applyOnMatch(
        self,
        name_valueTuple: tuple[str, str] | list[str],
    ) -> bool:
        resultWithErrMsg = self.setting_applyIfMatchesWithErrMsg(name_valueTuple)

        if resultWithErrMsg[1] is not None:
            _errmsg = resultWithErrMsg[1]
            raise HandledException(_errmsg)

        return resultWithErrMsg[0]

    def hasKey(self, name: str) -> bool:
        if not name:
            return False
        return name in self._settingsSpec

    def setting_applyIfMatchesWithErrMsg(
        self,
        name_valueTuple: tuple[str, str] | list[str],
    ) -> Tuple[bool, str | None]:
        argName, argValue = name_valueTuple[0], name_valueTuple[1]

        setting_params = DictUtils.getDict(self._settingsSpec, argName)
        if not setting_params:
            return False, None
        spec = ParamSpec(setting_params)

        _value, _help = spec.convertArg_orGiveHelp(argValue)

        if _value is None:

            if argValue == "":
                _errmsg = f"Missing value for {styling.asSuggestion(argName)}\n{_help}"
            else:
                _errmsg = f"Invalid value for {styling.asSuggestion(argName)}: {json.dumps(argValue)}\n{_help}"

            return True, _errmsg
        else:
            self._setting_value_direct(argName, _value)

            return True, None

    def _setting_value_direct(self, key: str, value: Any):
        if not "settings" in self.CONFIG_USED:
            self.CONFIG_USED["settings"] = {}
        self.CONFIG_USED["settings"][key] = value

    def setting_set_int(
        self,
        key: str,
        value: str | int,
        minValue: int | None = None,
        maxValue: int | None = None,
    ):
        if not key.startswith("!"):
            defaultValue = self.setting_get_default(key)

            if (defaultValue is not None) and (not isinstance(defaultValue, int)):
                self.log_error(
                    f"Default setting for key '{key}' is {json.dumps(defaultValue)}: Not an integer"
                )

            if not isinstance(value, int):
                try:
                    value = int(value)
                except Exception as e:
                    self.log_warning(
                        f"Setting[{key}]={value} is not an integer - Using default {defaultValue}"
                    )
                    return
            if (minValue is not None) and (value < minValue):
                self.log_warning(
                    f"Setting[{key}] : Clipping {value} to minimum {minValue}"
                )
                value = minValue

            if (maxValue is not None) and (value > maxValue):
                self.log_warning(
                    f"Setting[{key}] : Clipping {value} to maximum {maxValue}"
                )
                value = maxValue

        self._setting_value_direct(key, value)

    def setting_set_bool(self, key: str, value: str | bool):

        defaultValue = self.setting_get_default(key)

        if (defaultValue is not None) and (not isinstance(defaultValue, bool)):
            self.log_warning(
                f"Default setting for key '{key}' is {defaultValue}: Not boolean"
            )

        if not isinstance(value, bool):
            if isinstance(value, str):
                v = value.strip().lower()
                if v in ("true", "yes", "1", "on"):
                    value = True
                elif v in ("false", "no", "0", "off"):
                    value = False
                else:
                    self.log_warning(
                        f"Setting[{key}]={value} is not a boolean - Using default {defaultValue}"
                    )
                    return
            else:
                self.log_warning(
                    f"Setting[{key}]={value} is not a boolean - Using default {defaultValue}"
                )
                return
        self._setting_value_direct(key, value)

    def setting_get(self, key: str) -> Any:
        return self._setting_get(self.CONFIG_USED, key)

    def setting_getPreUser(self, key: str) -> Any:
        return self._setting_get(self.BEFORE_USER_CUSTOMISING, key)

    def _setting_get(self, source: dict[str, Any], key: str) -> Any:

        configKey = "settings/" + key
        result = DictUtils.get(source, configKey, None)
        if key.startswith("!"):
            return result

        if result is None:
            self.log_error(f"Setting '{key}' not found - nor found in CONFIG_DEFAULTS")
        else:

            defaultValue = self.setting_get_default(key)
            expectedType = type(defaultValue)
            if not isinstance(result, expectedType):
                self.log_warning(
                    f"Type mismatch for setting '{key}': expected {expectedType}, got {type(result)}"
                )

        return result

    def setting_get_bool(self, key: str, defaultOnUtterFailure: bool = False) -> Any:
        value = self.setting_get(key)

        type_default = type(defaultOnUtterFailure)
        if value is None:
            return defaultOnUtterFailure  # < Error already noted
        elif isinstance(value, type_default):
            return value
        else:
            self.log_error(f"Setting[{key}] = {value} : Expected {type_default}")
            return defaultOnUtterFailure

    def setting_get_int(self, key: str, defaultOnUtterFailure: int = 0) -> Any:

        value = self.setting_get(key)

        type_default = type(defaultOnUtterFailure)
        if value is None:
            return defaultOnUtterFailure  # < Error already noted
        elif isinstance(value, type_default):
            return value
        elif not key.startswith("!"):
            self.log_error(f"Setting[{key}] = {value} : Expected {type_default}")
            return defaultOnUtterFailure
        else:
            return defaultOnUtterFailure

    def asDict(self) -> dict[str, Any]:
        return {
            "used": self.CONFIG_USED,
            "notes": self.notes,
            "_settingsSpec": self._settingsSpec,
            "_defaults": self._defaults,
        }

    def log_error(self, message: str, ExceptionObj: Exception | None = None):
        self.notes.append(f"❌  Error: {message}")
        if ExceptionObj is not None:
            self.__logger.print_error_withException(ExceptionObj, message)
        else:
            self.__logger.print_error(message)

    def log_warning(self, message: str):
        self.notes.append(f"⚠️  Warning: {message}")
        self.__logger.print_warning(message)
