import hashlib
import json
import sys
from typing import Any
from datetime import datetime as dt_datetime
from datetime import timezone as dt_timezone

################################################################################
#
# Add project root directory to system path

import os


shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

################################################################################
#


class HandledException(Exception):
    """An exception that is expected to occur in normal operation - simply look at 'msg'"""

    def __init__(self, msg: str, doLog: bool = True):
        super().__init__(msg)
        if doLog:
            sys.stderr.write(f"⚠️  CreatedHandledException: {msg}\n")
        self.msg = msg


class Utils:
    @staticmethod
    def asJsonStr(obj, indent: int | str | None = None):
        """Safer version of json.dumps that can handle some extra types like bytes and avoids odd crashes"""

        class JsonEncoderExtended(json.JSONEncoder):
            def default(self, o):
                # return f"<Obj[{o.__class__.__name__}:{type(o)}]"
                try:
                    if isinstance(o, bytes):
                        return f"<{len(o)} bytes>"
                    elif o.__class__.__name__ == "mappingproxy":
                        return f"<Object[{o.__class__.__name__}]>"
                    elif o.__class__.__name__.startswith("numpy"):
                        import numpy as np

                        return np.array_str(o)
                    elif hasattr(o, "__dict__"):
                        return o.__dict__
                    else:
                        return str(o)
                except Exception:
                    return f"<Object[{o.__class__.__name__}:{type(o)}]"

        return json.dumps(
            obj,
            indent=indent,
            skipkeys=True,
            separators=None if indent else (",", ":"),
            ensure_ascii=False,
            cls=JsonEncoderExtended,
        )

    @staticmethod
    def rangeAsText(
        minVal: Any | None,
        maxVal: Any | None,
        optionalPrefixIfRanged: str = "",
        quoteValuesWith: str = "`",
    ) -> str:
        def quoteIfNeeded(val: Any) -> str:
            return f"{quoteValuesWith}!{val}{quoteValuesWith}"

        if (minVal is not None) and (maxVal is not None):
            txt = f"{optionalPrefixIfRanged}{quoteIfNeeded(minVal)}"
            if minVal != maxVal:
                txt += f" … {quoteIfNeeded(maxVal)}"
            return txt
        elif minVal is not None:
            return f"{optionalPrefixIfRanged} ≥ {quoteIfNeeded(minVal)}"
        elif maxVal is not None:
            return f"{optionalPrefixIfRanged} ≤ {quoteIfNeeded(maxVal)}"
        else:
            return f""

    @staticmethod
    def fill_withText(dest, text: str):
        """Fills a byte array or string with the given text (truncating if needed)"""
        if isinstance(dest, str):
            dest = text
        else:
            if isinstance(dest, int):
                dest = bytearray(dest)
            bytesOut = text.encode("utf-8", errors="replace")
            for x in range(dest.__len__()):
                dest[x] = 0 if (x >= len(bytesOut)) else bytesOut[x]
        return dest

    @staticmethod
    def list_removeDuplicates(src: list):
        try:
            return list(dict.fromkeys(src))
        except Exception:
            # Fallback to slower method if 'src' contains non hashable values
            unique_list = []
            for item in src:
                if item not in unique_list:
                    unique_list.append(item)
            return unique_list

    @staticmethod
    def list_removeDuplicatesAndNulls(src: list):
        unique_list = []
        for item in src:
            if (item is not None) and item not in unique_list:
                unique_list.append(item)
        return unique_list

    @staticmethod
    def makeImageFormatExt(ext: str) -> str:
        ext = ext.strip().removeprefix(".").lower()
        return "." + ("" if isStandardImageFormat(ext) else "raw_") + ext

    @staticmethod
    def entry_deleteIfFound(obj: dict[str, Any], keys: str | list[str]) -> bool:
        iterateList = keys.split("/") if isinstance(keys, str) else keys.copy()

        key_to_modify = iterateList.pop()

        obj_to_modify = entry_get(obj, iterateList)

        if isinstance(obj_to_modify, dict) and key_to_modify in obj_to_modify:
            obj_to_modify.pop(key_to_modify, None)
            return True
        else:
            return False

    @staticmethod
    def entry_deleteIfIs(
        obj: dict[str, Any], keys: str | list[str], value: Any
    ) -> bool:
        iterateList = keys.split("/") if isinstance(keys, str) else keys.copy()

        key_to_modify = iterateList.pop()

        obj_to_modify = entry_get(obj, iterateList)

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
    def md5_of_file(fname: str) -> str:
        with open(fname, "rb") as file:
            raw_bytes = file.read()
            md5hash_value = hashlib.md5(raw_bytes).hexdigest()
        return md5hash_value

    @staticmethod
    def md5_of_string(txt: str) -> str:
        raw_bytes = txt.encode("utf-8")
        md5hash_value = hashlib.md5(raw_bytes).hexdigest()
        return md5hash_value

    @staticmethod
    def toHex(data: bytes, maxLen_chars: int = 60) -> str:
        if len(data) == 1:
            txtSuffix = " (Single byte only)"
        elif len(data) == 0:
            txtSuffix = "(Empty data)"
        else:
            txtSuffix = f" ({len(data)} bytes)"
        maxDataLenBytes = (maxLen_chars - len(txtSuffix)) // 2
        if len(data) > maxDataLenBytes:
            txtSuffix = f"... ({len(data)} bytes total)"
            maxDataLenBytes = (maxLen_chars - len(txtSuffix)) // 2

            return data[:maxDataLenBytes].hex() + txtSuffix
        else:
            return data.hex() + txtSuffix


def flattenObj(obj_in: dict[str, Any], sep: str = ".") -> dict[str, Any]:
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


def extendDict(modifyThis: dict[str, Any], withThis: dict[str, Any] | None) -> None:
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


def asPrintableAscii(charCode: int) -> str:
    if (charCode < 32) or (charCode > 126):
        return f"\\x{charCode:02x}"
    else:
        return chr(charCode)


def aOrAn(item: str) -> str:
    if item is not None and len(item) > 0 and item[0].lower() in "aeiou":
        # If the first letter is a vowel, return "an"
        return "an"
    else:
        return "a"


def withAOrAn(item: str) -> str:
    return f"{aOrAn(item)} {item}"


def pluralize(count: int, singular: str, plural: str | None = None):
    if plural is None:
        if singular.endswith("y"):
            plural = singular.removesuffix("y") + "ies"
        elif (singular.endswith("s")) or (singular.endswith("x")):
            plural = singular + "es"
        else:
            plural = singular + "s"
    return f"{count} {singular}" if count == 1 else f"{count} {plural}"


def entry_get(
    obj_in: dict[str, Any] | list[Any] | None,
    keys: str | list[str],
    defaultIfNotFound: Any = None,
) -> Any | None:
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
            return defaultIfNotFound
    return obj


def entry_getStrOrNone(obj: dict[str, Any] | None, key: str | list[str]) -> str | None:
    value = entry_get(obj, key, None)
    if value is None:
        return None
    else:
        return str(value)


def entry_deleteIfFound(obj: dict[str, Any], keys: str | list[str]) -> bool:
    iterateList = keys.split("/") if isinstance(keys, str) else keys.copy()

    key_to_modify = iterateList.pop()

    obj_to_modify = entry_get(obj, iterateList)

    if isinstance(obj_to_modify, dict) and key_to_modify in obj_to_modify:
        obj_to_modify.pop(key_to_modify, None)
        return True
    else:
        return False


def entry_deleteIfIs(obj: dict[str, Any], keys: str | list[str], value: Any) -> bool:
    iterateList = keys.split("/") if isinstance(keys, str) else keys.copy()

    key_to_modify = iterateList.pop()

    obj_to_modify = entry_get(obj, iterateList)

    if (
        isinstance(obj_to_modify, dict)
        and key_to_modify in obj_to_modify
        and obj_to_modify[key_to_modify] == value
    ):
        obj_to_modify.pop(key_to_modify, None)
        return True
    else:
        return False


def entry_set(obj: dict[str, Any], key: str | list[str], value: Any) -> bool:
    iterateList = []
    if isinstance(key, str):
        iterateList = key.split("/")
    else:
        iterateList = key.copy()

    key = iterateList.pop()

    for k in iterateList:
        if not isinstance(obj, dict):
            sys.stderr.write(
                f"⚠️  entry_set(a): Expected dict, but got {type(obj)} for key '{key}' in {Utils.asJsonStr(obj)} - \n"
            )
            return False

        if not (k in obj):
            obj[k] = {}
        if not isinstance(obj[k], dict):
            sys.stderr.write(
                f"⚠️  entry_set(b): Expected dict, but got {type(obj[k])} for key '{k}' in {Utils.asJsonStr(obj)} - \n"
            )
            obj[k] = {}
        obj = obj[k]

    if isinstance(obj, dict):
        obj[key] = value
        return True
    else:
        sys.stderr.write(
            f"⚠️  entry_set(b): Expected dict, but got {type(obj)} for key '{key}' in {Utils.asJsonStr(obj)} - \n"
        )
        return False


def entry_getInt(
    obj: dict[str, Any] | None, key: str | list[str], defaultValue: int
) -> int:
    result = entry_getIntOrNone(obj, key)
    return defaultValue if (result is None) or (not isinstance(result, int)) else result


def entry_getBool(
    obj: dict[str, Any] | None, key: str | list[str], defaultValue: bool
) -> bool:
    result = entry_get(obj, key, None)
    return (
        defaultValue if (result is None) or (not isinstance(result, bool)) else result
    )


def entry_getBoolOrFalse(obj: dict[str, Any] | None, key: str | list[str]) -> bool:
    return entry_getBool(obj, key, False)


def entry_getIntOrNone(
    obj: dict[str, Any] | None, key: str | list[str], defaultValue: int | None = None
) -> int | None:
    value = entry_get(obj, key, None)
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
            f"⚠️  getEntry_int(): Expected int or str, but got {type(value)} for key '{key}' in {Utils.asJsonStr(obj)}\n"
        )
        return defaultValue


def entry_getStr(obj: dict[str, Any], key: str | list[str], defaultValue: str) -> str:
    value = entry_get(obj, key, None)
    if value is None:
        return defaultValue
    else:
        return str(value)


def strToInt(value: str, defaultValue: int, context: str | None = None) -> int:
    try:
        if (value == "") and context is None:
            return defaultValue  # < If expected to fail, avoid an exception to aide debugging where we halt on all exceptions
        return int(value.strip())
    except ValueError:
        if (context is not None) and (len(context) > 0):
            sys.stderr.write(
                f"⚠️  strToInt(): Failed to convert '{value}' to int in {context}\n"
            )
        return defaultValue


def imageFormatTextToSpec(specStr: str) -> dict[str, Any]:
    """Image format spec str:   'png','jpg','bmp','mono8_16x16','mono12_32x32+15' etc"""
    _parts_format = specStr.split("_", maxsplit=1) + [""]
    _parts_size = (_parts_format + [""])[1].split("+", maxsplit=1)

    _parts_wid_height = (_parts_size[0] + "x").split("x")

    format = _parts_format[0].strip()

    width = strToInt(_parts_wid_height[0], 0, f"width from {specStr}")
    height = strToInt(_parts_wid_height[1], 0, f"height from {specStr}")
    offset = strToInt((_parts_size + [""])[1], 0)

    result: dict[str, Any] = {"format": format}

    if width != 0:
        result["width"] = width
    if height != 0:
        result["height"] = height
    if offset != 0:
        result["offset"] = offset

    # appLog.print_verbose(f"imageFormatTextToSpec({specStr}) -> {result}")
    return result


def isStandardImageFormat(ext: str) -> bool:
    return asStandardImageFormatOrNone(ext) is not None


def asStandardImageFormatOrNone(ext: str) -> str | None:
    ext = ext.strip().removeprefix(".").lower()

    if not ext in ["png", "jpg", "jpeg", "bmp", "gif", "tiff"]:
        return None
    if ext == "jpg":
        return "jpeg"
    return ext


def timestampObj_from_ns(ns: int) -> dict[str, Any] | None:
    """
    Converts a timestamp in nanoseconds to a safe dictionary format (Schema: $timestamp.json)
    | {
    |   "type": "object",
    |   "properties": {
    |     "utc": {
    |         "type": "number",
    |         "description": "The UTC timestamp in seconds since the epoch - For full precision use part_sec and part_ns",
    |         "example": 1750298403.1234567,
    |         "minimum":0
    |      },
    |     "part_sec": { "type": "integer", "description": "The seconds part of the timestamp", "minimum":0},
    |     "part_ns" : { "type": "integer", "description": "The nanoseconds part of the timestamp",
    |                                      "minimum":0,"maximum":999999999}
    |   },
    |   "required": ["part_ns", "part_sec"],
    |   "additionalProperties": false
    | }
    """
    if ns <= 0:
        return None

    part_sec = ns // 1_000_000_000
    part_ns = ns % 1_000_000_000

    utc_when = dt_datetime.fromtimestamp(part_sec, dt_timezone.utc)

    part_ns_txt = f"{part_ns:09d}"
    while part_ns_txt.endswith("0"):
        part_ns_txt = part_ns_txt[:-1]
    if part_ns_txt != "":
        part_ns_txt = "." + part_ns_txt
    formatted = utc_when.strftime("%Y-%m-%dT%H:%M:%S") + part_ns_txt + "+Z"

    return {
        "utc": (
            part_sec if part_ns_txt == "" else round(ns / 1_000_000_000, 6)
        ),  # For full precision use part_sec and part_ns
        "utc_full": f"{part_sec}{part_ns_txt}",
        "part_sec": part_sec,
        "part_ns": part_ns,
        "ns": ns,
        "text": formatted,
    }
