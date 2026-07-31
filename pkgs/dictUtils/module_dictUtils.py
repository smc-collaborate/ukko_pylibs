import array
import base64

from collections import OrderedDict
from copy import deepcopy
import hashlib
import inspect
import json
import re
import os
import sys
import textwrap
import time
import traceback
from typing import Any, Callable, Tuple
from datetime import datetime as dt_datetime
from datetime import timezone as dt_timezone
import numpy as np
from pathlib import Path


################################################################################
#
# Ensure shared Packages are available
#

packages_dir = str((Path(__file__).parent.parent.parent / "pkgs").absolute())
if not packages_dir.endswith("/pkgs") or not os.path.exists(packages_dir):
    exit(f"❌  {__file__}\n    Misconfigured: [/path/to]/pkgs is not {packages_dir}")

if packages_dir not in sys.path:
    sys.path.append(packages_dir)
#
################################################################################

from ukkoUtils import asJsonStr, json_loads, makeJsonable, DeviceStateEnum


def appendStr(
    obj: dict[str, Any], key: str, newValue: str | None, separator: str = ","
):

    if newValue is None:
        return

    if not isinstance(obj.get(key, None), str):
        obj[key] = ""
    if newValue != "":
        obj[key] += separator
    obj[key] += str(newValue)


@staticmethod
def getWithDefaultValuesRemoved(
    dictIn: dict, defaultValues: dict[str, Any], recurseDicts: bool = False
) -> dict[str, Any]:
    """Removes keys from dictIn that have the same value as in defaultValues"""
    result = {}
    # | ExtraLogging print_verbose("------------------------------")
    # | ExtraLogging print_verbose(f"getWithDefaultValuesRemoved({ukkoUtils.asJsonStr(dictIn)},defaultValues: {ukkoUtils.asJsonStr(defaultValues)}):")
    for key, value in dictIn.items():
        if isinstance(value, dict) and (recurseDicts == True):
            defaultValue = defaultValues.get(key, None)
            if isinstance(defaultValue, dict) and (len(defaultValue) > 0):
                value = getWithDefaultValuesRemoved(
                    value, defaultValue, recurseDicts=True
                )
                if value != {}:
                    result[key] = value
                    continue
        if key not in defaultValues or defaultValues[key] != value:
            # | ExtraLogging print_verbose(f"{key}:[default: {ukkoUtils.asJsonStr(defaultValues.get(key,None))}, actual: {ukkoUtils.asJsonStr(value)})]")
            result[key] = value
    # | ExtraLogging print_verbose(f"->{ukkoUtils.asJsonStr(result)}")
    # | ExtraLogging print_verbose("------------------------------")
    return result


@staticmethod
def extendWithoutOverwrite(
    modifyThis: dict[str, Any], withThis: dict[str, Any] | None
) -> None:
    if (withThis is None) or (len(withThis) == 0):
        return

    for key, newValue in withThis.items():
        oldValue = modifyThis.get(key, None)

        if newValue == oldValue:
            pass
        elif oldValue is None:
            modifyThis[key] = newValue
        elif isinstance(oldValue, list):
            modifyThis[key].extend(newValue)
        else:
            modifyThis[key] = [oldValue, newValue]


@staticmethod
def getFlattened(obj_in: dict[str, Any], sep: str = ".") -> dict[str, Any]:
    """Flattens a nested dictionary into a single level dictionary with keys joined by sep"""
    obj_out: dict[str, Any] = {}

    def _recurse(o: dict[str, Any], prefix: str = ""):
        for k, v in o.items():
            if isinstance(v, dict):
                _recurse(v, f"{prefix}{k}{sep}")
            elif isinstance(v, list) and all(isinstance(i, int) for i in v):
                last = None
                first = None
                txt_ranges = []
                for x in v + [None]:  # Add a None at the end to flush the last range
                    if last is None:
                        first = x
                        last = x
                    elif x == last + 1:
                        last = x
                    else:
                        if first == last:
                            txt_ranges.append(f"{first}")
                        else:
                            txt_ranges.append(f"{first}-{last}")
                        first = x
                        last = x
                obj_out[f"{prefix}{k}"] = ",".join(txt_ranges)
            else:
                obj_out[f"{prefix}{k}"] = v

    _recurse(obj_in)
    return obj_out


@staticmethod
def get(
    obj_in: dict[str, Any] | list[Any] | Any | None,
    keys: str | list[str],
    defaultIfNotFound: Any = None,
    getDeepestFound: bool = False,
) -> Any | None:
    try:
        if obj_in is None:
            return defaultIfNotFound
        iterateList = keys.split("/") if isinstance(keys, str) else keys.copy()
        obj: Any | None = obj_in
        for k in iterateList:
            if isinstance(obj, dict) and k in obj:
                obj = obj[k]
            elif isinstance(obj, list) and k.isdigit() and (0 <= int(k) < len(obj)):
                obj = obj[int(k)]
            else:
                return defaultIfNotFound if getDeepestFound == False else obj
        return obj
    except Exception as e:
        sys.stderr.write(f"⚠️  DictUtils.get(): Exception {e}\n")
        return defaultIfNotFound


@staticmethod
def deleteIfFound(obj: dict[str, Any], keys: str | list[str]) -> bool:
    iterateList = keys.split("/") if isinstance(keys, str) else keys.copy()

    key_to_modify = iterateList.pop()

    obj_to_modify = get(obj, iterateList)

    if isinstance(obj_to_modify, dict) and key_to_modify in obj_to_modify:
        obj_to_modify.pop(key_to_modify, None)
        return True
    else:
        return False


@staticmethod
def deleteIfIs(obj: dict[str, Any], keys: str | list[str], value: Any) -> bool:
    iterateList = keys.split("/") if isinstance(keys, str) else keys.copy()

    key_to_modify = iterateList.pop()

    obj_to_modify = get(obj, iterateList)

    if (
        isinstance(obj_to_modify, dict)
        and key_to_modify in obj_to_modify
        and obj_to_modify[key_to_modify] == value
    ):
        obj_to_modify.pop(key_to_modify, None)
        return True
    else:
        return False


@staticmethod
def set(obj: dict[str, Any], key: str | list[str], value: Any) -> bool:
    iterateList = []
    if isinstance(key, str):
        iterateList = key.split("/")
    else:
        iterateList = key.copy()

    key = iterateList.pop()

    for k in iterateList:
        if not isinstance(obj, dict):
            sys.stderr.write(
                f"⚠️  DictUtils.set(a): Expected dict, but got {type(obj)} for key '{key}' in {asJsonStr(obj)} - \n"
            )
            return False

        if not (k in obj):
            obj[k] = {}
        if not isinstance(obj[k], dict):
            sys.stderr.write(
                f"⚠️  DictUtils.set(b): Expected dict, but got {type(obj[k])} for key '{k}' in {asJsonStr(obj)} - \n"
            )
            obj[k] = {}
        obj = obj[k]

    if isinstance(obj, dict):
        obj[key] = value
        return True
    else:
        sys.stderr.write(
            f"⚠️  DictUtils.set(c): Expected dict, but got {type(obj)} for key '{key}' in {asJsonStr(obj)} - \n"
        )
        return False


@staticmethod
def getInt(
    obj_in: Any | None,
    keys: str | list[str],
    defaultIfNotFound: int,
) -> int:
    try:
        result = get(obj_in, keys, defaultIfNotFound)

        if isinstance(result, int):
            return result

        sys.stderr.write(
            f"⚠️  DictUtils.getInt(): Expected int but got {type(result)}:{result}.  Returning default {defaultIfNotFound}\n"
        )
    except Exception as e:
        sys.stderr.write(f"⚠️  DictUtils.getInt(): Exception {e}\n")
    return defaultIfNotFound


@staticmethod
def getBool(obj: Any | None, key: str | list[str], defaultValue: bool) -> bool:
    result = get(obj, key)
    return (
        defaultValue if (result is None) or (not isinstance(result, bool)) else result
    )


@staticmethod
def getBoolOrFalse(obj: Any | None, key: str | list[str]) -> bool:
    return getBool(obj, key, False)


@staticmethod
def getIntOrNone(
    obj: Any | None,
    key: str | list[str],
    defaultValue: int | None = None,
) -> int | None:
    value = get(obj, key, None)
    if value is None:
        return defaultValue
    elif isinstance(value, int):
        return value
    elif isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return defaultValue
    else:
        sys.stderr.write(
            f"⚠️  getIntOrNone(): Expected int or str, but got {type(value)} for key '{key}' in {asJsonStr(obj)}\n"
        )
        return defaultValue


@staticmethod
def getStr(obj: Any | None, key: str | list[str], defaultValue: str) -> str:
    value = get(obj, key)
    if value is None:
        return defaultValue
    else:
        return str(value)


@staticmethod
def getStrOrNone(obj: Any | None, key: str | list[str]) -> str | None:
    value = get(obj, key, None)
    if value is None:
        return None
    else:
        return str(value)


@staticmethod
def getDict(
    obj_in: Any | None,
    keys: str | list[str],
    defaultIfNotFound: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _defaultIfNotFound = defaultIfNotFound or {}
    try:
        result = get(obj_in, keys, _defaultIfNotFound)

        if result is None:
            return _defaultIfNotFound
        elif isinstance(result, dict):
            return result
        else:
            sys.stderr.write(
                f"⚠️  DictUtils.getDict({keys}): Expected dict, but got {type(result)} in {asJsonStr(obj_in)}\n"
            )
            return _defaultIfNotFound
    except Exception as e:
        sys.stderr.write(f"⚠️  DictUtils.getDict({keys}): Exception {e}\n")
        return _defaultIfNotFound


@staticmethod
def dict_diff(contents_old, contents_new):
    # This can be removed for a release version - it is to make our lives easier for diagnostics
    try:

        if contents_old == contents_new:
            return None

        if contents_old is None:
            return "new:" + asJsonStr(contents_new)
        if contents_new is None:
            return "removed: " + asJsonStr(contents_old)

        if type(contents_old) != type(contents_new):
            return asJsonStr(contents_old) + " types:-> " + asJsonStr(contents_new)

        if (type(contents_old) is not dict) and (type(contents_old) is not OrderedDict):
            return asJsonStr(contents_old) + " -> " + asJsonStr(contents_new)

        result = dict()

        for key in list(contents_old.keys()):
            try:
                diff = dict_diff(
                    contents_old.get(key, None), contents_new.get(key, None)
                )
                if diff is not None:
                    result[key] = diff
            except Exception as e:
                result[key] = "⚠️ dictUtils.dict_diff(" + key + ").a: " + str(e)

        for key in list(contents_new.keys()):
            try:
                if key not in contents_old:
                    result[key] = "New: " + asJsonStr(contents_new[key])
            except Exception as e:
                result[key] = "⚠️ dictUtils.dict_diff(" + key + ").b: " + str(e)

        if len(result) == 0:
            return None
        else:
            return result
    except Exception as e:
        return "⚠️ " + str(e)


@staticmethod
def doCleanup(contents):
    # This can be removed for a release version - it is to make our lives easier for diagnostics
    if (contents is not None) and (
        (type(contents) is dict) or (type(contents) is OrderedDict)
    ):
        try:
            for key in list(contents.keys()):
                try:
                    value = contents[key]
                    valueAsText: str | None = str(value)
                    try:
                        if type(value) in [
                            bytes,
                            bytearray,
                            list,
                            tuple,
                            array.array,
                            np.ndarray,
                        ]:
                            if len(value) > 0:
                                if isinstance(value[0], int) or isinstance(
                                    value[0], np.integer
                                ):
                                    valueAsText = (
                                        bytes(value)
                                        .decode("utf-8", errors="replace")
                                        .rstrip("\x00")
                                    )
                    except Exception as e:
                        print(
                            f"⚠️ BytesConversionFailure(Type {type(value)}): {value} = {e}"
                        )
                        valueAsText = None

                    if key.startswith("diag_json_") and (valueAsText is not None):
                        if (valueAsText != "") and (valueAsText != "null"):
                            contents["diag_" + key.removeprefix("diag_json_")] = (
                                json_loads(valueAsText)
                            )
                        del contents[key]
                    elif (key == "json") and (valueAsText is not None):
                        if (valueAsText != "") and (valueAsText != "null"):
                            contents["json_obj"] = json_loads(valueAsText)
                        del contents[key]
                    elif (type(value) is dict) or (type(value) is OrderedDict):
                        contents[key] = doCleanup(value)
                    elif key == "device_state":
                        contents[key + "_text"] = DeviceStateEnum.asText(value)
                        del contents[key]
                    elif (key.endswith("_error_msg") or key.endswith("_err_msg")) and (
                        valueAsText == ""
                    ):
                        del contents[key]

                except Exception as e:
                    sys.stderr.write(f"⚠️ DictUtils.doCleanup({key}): {e}\n")
        except Exception as e:
            sys.stderr.write(f"⚠️ DictUtils.doCleanup({contents}): {e}\n")

    return contents


def msg_to_dict(
    msg, is_full: bool = True
) -> dict[str, Any] | OrderedDict[str, Any] | None:
    if msg is None:
        return None

    # |Quick| if isinstance(msg, AnnotatedData):
    # |Quick|     return msg.toFullJson(is_full)
    try:
        result = makeJsonable(
            msg, is_full
        )  # msgconverter.convert_ros_message_to_dictionary(msg,True)
        try:

            result = doCleanup(result)
        except Exception as e:
            print("⚠️ dictUtils.msg_to_dict(" + str(msg) + "): " + str(e))

        if not (type(result) is dict) and not (type(result) is OrderedDict):
            return {"value": result}
        else:
            return result

    except Exception as e:
        print("⚠️ dictUtils.msg_to_dict(" + str(msg) + "): " + str(e))
        print(traceback.format_exc())
        return {"msg_to_dict.ee": str(e)}


def msg_to_json_text(msg, is_full: bool = False):
    if msg is None:
        return "null"

    try:
        result = msg_to_dict(msg, is_full)

        return asJsonStr(result)
    except Exception as e:
        print("⚠️ dictUtils.msg_to_json_text(" + str(type(msg)) + "): " + str(e))

        result = {"msg_to_json_text.ee": str(e)}
        return asJsonStr(result)
