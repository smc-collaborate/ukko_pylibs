import array
import base64

from collections import OrderedDict

import hashlib
import inspect
import json
from pathlib import Path
import re
import os
import sys

from typing import Any, Literal, Tuple
from datetime import datetime as dt_datetime
from datetime import timezone as dt_timezone


NameValuePair = Tuple[str, Any | None]
NameValuePairList = list[NameValuePair]


from appLogging import appLog

################################################################################
#


def toBool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    txt = str(value).strip().lower()
    if txt in ["true", "1", "yes", "y", "on"]:
        return True
    elif txt in ["false", "0", "no", "n", "off"]:
        return False
    return None


def hasRemovedPrefix(value: str, prefix: str) -> tuple[bool, str]:
    if not value.startswith(prefix):
        return False, value
    else:
        return True, value[len(prefix) :]


def hasReplacedPrefix(
    value: str, prefixBefore: str, prefixAfter: str
) -> tuple[bool, str]:
    if not value.startswith(prefixBefore):
        return False, value
    else:
        return True, prefixAfter + value[len(prefixBefore) :]


def hasRemovedSuffix(value: str, suffix: str) -> tuple[bool, str]:
    if not value.endswith(suffix):
        return False, value
    else:
        return True, value[: -len(suffix)]


def is_iterable(obj) -> bool:
    try:
        iter(obj)
        return True
    except TypeError:
        return False


def isStdoutText():
    stdout_is_tty_txt = (
        os.environ.get("STDOUT_IS_TTY", "1" if sys.stdout.isatty() else "0")
        .removeprefix('"')
        .removesuffix('"')
    )
    isConsoleOut = not (str(stdout_is_tty_txt).lower() in ["0", "", "none", "false"])
    return isConsoleOut


PathConvertOptions = Literal[
    "friendly",
    "abs:friendly",
    "rel",
    "abs:friendly",
    "rel:real",
    "abs",
    "abs:~",
]


def pathAsDisplay(pathName: str | Path, kind: PathConvertOptions = "friendly") -> str:
    """Converts a path to a friendly display format."""

    return pathConvert(str(pathName), kind=kind).removesuffix(os.sep)


def pathDisplay(pathName: str) -> str:
    appLog.deprecationWarningRename("pathDisplay", "pathAsDisplay")
    return pathAsDisplay(pathName)


pwdOnModuleLoad = os.getcwd()


def getStartupPath() -> str:
    try:
        cwdOnStartup = os.getenv("ORIG_PWD")

        if not cwdOnStartup:
            cwdOnStartup = pwdOnModuleLoad
        return cwdOnStartup
    except:
        return ""


def pathConvert(pathName: str, kind: PathConvertOptions = "friendly") -> str:
    """Converts a path to [abs, abs:friendly, rel, friendly, raw] format.  If conversion isn't available then returns the pathName given"""

    path = pathName
    extra = ""
    try:
        appModule = sys.modules["__main__"]
        if hasattr(appModule, "PATHS"):
            path_lookup = appModule.PATHS
            pathNameKey = pathName.removeprefix("[").removesuffix("]")
            if pathNameKey in path_lookup:
                path = str(path_lookup[pathNameKey])
                extra += f"[{pathNameKey}→{path}]"
    except Exception:
        pass  # < Silently handle - This defaults to pathName if any issue occurs

    options = []
    if kind == "abs":
        options.append(os.path.abspath(path))
    elif kind == "abs:friendly":
        options.append(pathConvert(path, "abs"))
        options.append(pathConvert(os.path.realpath(path), "abs"))
        options.append(pathConvert(path, "abs:~"))
        options.append(pathConvert(os.path.realpath(path), "abs:~"))
    elif kind == "abs:~":
        homedir = os.path.expanduser("~")

        path = os.path.abspath(path)
        if path == homedir:
            path = "~"
        elif path.startswith(homedir + os.sep):
            path = "~" + os.sep + path.removeprefix(homedir + os.sep)
        options.append(path)
    elif kind == "rel" or kind == "rel:real":
        cwdOnStartup = getStartupPath()

        if cwdOnStartup:
            if kind.endswith(":real"):
                cwdOnStartup = os.path.realpath(cwdOnStartup)
            extra += f"[cwdOnStartup:{cwdOnStartup}]"
            path = os.path.relpath(path, cwdOnStartup)
        else:
            path = os.path.relpath(path)
        options.append(path)
    elif kind == "friendly":

        options.append(pathConvert(path, "abs:friendly"))
        options.append(pathConvert(path, "rel"))
        options.append(pathConvert(os.path.realpath(path), "abs:friendly"))
        options.append(pathConvert(os.path.realpath(path), "rel:real"))
        options.append(path)
    else:
        options.append(path)

    path = min(options, key=lambda x: len(x))
    return path


def asUtf8orBytesOrNone(data: Any) -> str | bytes | None:

    result = asUtf8orBytes(data)
    return result if result != "" else None


def asUtf8orBytes(data: Any) -> str | bytes:

    data_b = None
    if isinstance(data, bytes):
        data_b = data
    elif isinstance(data, list):
        data_b = bytes(data)

    if isinstance(data_b, bytes):
        try:
            earlyPart = data_b[:100]
            if not (0 in earlyPart) and not (
                0xFF in earlyPart
            ):  # < Just a check to avoid trying to decode obviously non-text data - this is not perfect but should avoid annoyances when trapping raised exceptions
                return data_b.decode("utf-8")
        except Exception:
            pass
        return data_b
    if data is None:
        return ""
    elif isinstance(data, str):
        return data
    elif isinstance(data, dict):
        return asJsonStr(data)
    else:
        return f"❓  [{type(data).__name__}]:{str(data)}"


def load_file_to_text(file_path):
    """
    Loads the content of a file into a text string.

    Args:
        file_path (str): The path to the file.

    Returns:
        str: The content of the file as a string, or None if an error occurs.
    """
    try:
        with open(file_path, "r") as file:
            text = file.read()
        return text
    except FileNotFoundError:
        print(os.environ)
        return appLog.print_error(f"Text File not found at '{file_path}'")
    except Exception as e:
        return appLog.print_error(f"An exception occurred: {e}")


def json_load_from_file(fname: str, defaultValue=None):
    """
    Load a JSON dict from a file

    Args:
        fname (str): The name of the file to load

    Returns:
        dict: The loaded configuration as a dictionary.
    """

    try:
        data = json.loads(open(fname).read())
        data["_src"] = "file[" + fname + "]"
        return data
    except Exception as e:
        if defaultValue is None:
            print("Error loading JSON from file(" + fname + "): " + str(e))
        return defaultValue


def json_load_dict_from_file(fname: str) -> dict[str, Any]:
    """
    Load a JSON dict from a file

    Args:
        fname (str): The name of the file to load

    Returns:
        dict: The loaded configuration as a dictionary.
    """
    result = json_load_from_file(fname, None)
    return result if isinstance(result, dict) else {}


def json_loads(txt: str) -> Any | None:
    try:
        return json.loads(txt)
    except json.JSONDecodeError as e:
        txt = re.sub(r"\\x([0-9a-fA-F]{2})", r"\\u00\1", txt)

    return json.loads(
        txt
    )  # < Let the exception propagate this time - there isn't much more we can do


def dictFromJsonLikeStr(
    txt: str, warningPrefixOnFailure: str | None, defaultValue: dict | None
) -> dict | None:
    try:
        return json_loads(txt)
    except Exception as e:
        if warningPrefixOnFailure is not None:
            appLog.print_warning_withException(e, f"{warningPrefixOnFailure}")
        return defaultValue


def asJsonStr(obj, indent: int | None = None, sortKeys: bool = False) -> str:
    """Safer version of json.dumps that can handle some extra types like bytes and avoids odd crashes"""

    try:

        class JsonEncoderExtended(json.JSONEncoder):
            def default(self, o):
                return makeJsonable(o)

        return json.dumps(
            obj,
            indent=indent,
            sort_keys=sortKeys,
            cls=JsonEncoderExtended,
            separators=None if indent else (",", ":"),
            ensure_ascii=False,
            skipkeys=True,
        )
    except Exception as e:
        appLog.print_warning_withException(e, "Utils.asJsonStr")
        return asJsonStr(
            {"error": "Unable to create JSON Text", "exception": {e}},
            indent=indent,
            sortKeys=sortKeys,
        )


def asJsonRStr(obj, indent: int | None = None, sortKeys: bool = False) -> str:
    """Safer version of json.dumps that can handle some extra types like bytes and avoids odd crashes"""
    try:
        import json5

        if (
            json5.VERSION != "0.9.14"
        ):  # < Totally optional debugging hack to avoid throwing a pointless warning message in a particular test scenario.  No difference to functionality

            class Json5EncoderExtended(json5.JSON5Encoder):
                def default(self, obj):
                    return makeJsonable(obj)

            return json5.dumps(
                obj,
                indent=indent,
                sort_keys=sortKeys,
                cls=Json5EncoderExtended,
                separators=None if indent else (",", ":"),
                ensure_ascii=False,
                quote_keys=False,
                skipkeys=True,
            )
    except Exception as e:
        appLog.print_warning_withException(e, "Utils.asJsonRStr")

    return asJsonStr(obj, indent)


def asStr(obj) -> str:
    try:
        if obj is None:
            return ""

        if isinstance(obj, str):
            return obj

        if isinstance(obj, list):
            return "[" + ",".join([asStr(x) for x in obj]) + "]"
        else:
            return asJsonRStr(obj).removeprefix("{").removesuffix("}")
    except Exception as e:
        appLog.print_error_withException(e, "Utils.asStr()")
        return asJsonStr(obj)


def makeJsonable(
    contents, base64_encoding=True, recursionDepth: int = 0
) -> list | dict[str, Any] | OrderedDict | str | int | float | None:
    try:
        if contents is None:
            if recursionDepth > 0:
                return None
            else:
                return "⚠️  «None»"  # <- This should never happen - as 'None' -> Null is normally handled elsewhere.  Return this to warn

        if contents is None:
            return None

        if type(contents) in [str, int, float, bool]:
            return contents
        if isinstance(contents, type):
            return {"«type»": _makeJsonable_fromType(contents)}

        if str(contents) == "<class 'builtin_function_or_method'>":
            return "«builtin_function_or_method»"

        if recursionDepth >= 20:
            return f"⚠️  Unable to makeJsonable([{type(contents)}]: Recursion depth of {recursionDepth} reached"

        if hasattr(contents, "__slots__"):
            # This is a ROS message
            d = OrderedDict()
            for field_name, field_type in zip(contents.__slots__, contents.SLOT_TYPES):
                value = getattr(contents, field_name, None)
                d[field_name.removeprefix("_")] = makeJsonable(
                    value, base64_encoding, recursionDepth=recursionDepth + 1
                )
            return d

        if (type(contents) is dict) or (type(contents) is OrderedDict):
            d = OrderedDict()
            try:
                for key in list(contents.keys()):
                    d[key] = makeJsonable(
                        contents[key],
                        base64_encoding,
                        recursionDepth=recursionDepth + 1,
                    )
            except Exception as e:
                print("⚠️ ukkoUtils.makeJsonable(" + str(contents) + "): " + str(e))
            return d
        if isinstance(contents, bytes):
            if base64_encoding:
                # Encode the bytes to base64
                return base64.b64encode(contents).decode("utf-8")
            else:
                return _makeJsonable_fromBytes(contents)
        if isinstance(contents, bytearray):
            if base64_encoding:
                # Encode the bytes to base64
                return base64.b64encode(contents).decode("utf-8")
            else:
                return "bytearray(" + str(len(contents)) + ")"
        if isinstance(contents, (list, tuple, array.array)):
            # Since arrays and ndarrays can't contain mixed types convert to list
            d = list()
            for x in contents:
                d.append(
                    makeJsonable(x, base64_encoding, recursionDepth=recursionDepth + 1)
                )
            return d
        if hasattr(contents, "asJsonable"):
            return contents.asJsonable()
        if hasattr(contents, "asDict"):
            return contents.asDict()
        try:
            import numpy as np

            if isinstance(contents, (np.ndarray)):
                # Since arrays and ndarrays can't contain mixed types convert to list
                d = list()
                for x in contents:
                    d.append(
                        makeJsonable(
                            x, base64_encoding, recursionDepth=recursionDepth + 1
                        )
                    )
                return d
            if contents.__class__.__name__.startswith("numpy"):
                return np.array_str(contents)

            if hasattr(contents, "T"):
                return contents.T

        except Exception as e:
            appLog.print_verbose(f"ukkoUtils.makeJsonable: numpy issue: {e}")

        if hasattr(contents, "__dict__"):
            outResult = {}
            for name, value in contents.__dict__.items():
                outResult[name] = makeJsonable(
                    value, base64_encoding, recursionDepth=recursionDepth + 1
                )
            return outResult

        return f"{contents}"  # ⚠️  Unable to makeJsonable([{type(contents)}]={contents} - No conversion found"

    except Exception as e:
        return (
            f"⚠️  Unable to makeJsonable([{type(contents)}]={contents} - Exception {e}"
        )


# |Alternative|
# |Alternative|         if hasattr(o, "items"):  # < Must have type + common first
# |Alternative|             _showHint("_items")
# |Alternative|             _items = o.items()
# |Alternative|             obj_out: dict[str, Any] = {}
# |Alternative|             for _name, _value in _items:
# |Alternative|                 obj_out[_name] = makeJsonable(
# |Alternative|                     _value, currentDepth + 1, hint + _name + "."
# |Alternative|                 )
# |Alternative|             return obj_out


# |Alternative| def makeJsonable(
# |Alternative|     o: Any | None, currentDepth: int = 0, hint: str = ""
# |Alternative| ) -> dict | str | int | float | bool | list | Any:
# |Alternative|     if o is None:
# |Alternative|         return "⚠️  «None»"  # <- This should never happen - as 'None' -> Null is normally handled elsewhere.  Return this to warn
# |Alternative|
# |Alternative|     if currentDepth >= 20:
# |Alternative|         return f"⚠️  Unable to convert {hint}[{type(o)}]: Recursion depth of {currentDepth} reached"
# |Alternative|
# |Alternative|     def _showHint(msg: str):
# |Alternative|         pass
# |Alternative|         # if currentDepth <=3 and not msg.startswith("⚠️"):
# |Alternative|         #    print(f"makeJsonable: {hint}Type[{type(o)}] : Depth={currentDepth} : {msg}")
# |Alternative|
# |Alternative|     _showHint(f" --- Start")
# |Alternative|
# |Alternative|     if type(o) in [str, int, float, bool]:
# |Alternative|         _showHint(f" = Direct {o}")
# |Alternative|         return o
# |Alternative|     if str(o) == "<class 'builtin_function_or_method'>":
# |Alternative|         _showHint(f" = «builtin_function_or_method»")
# |Alternative|         return "«builtin_function_or_method»"
# |Alternative|
# |Alternative|     try:
# |Alternative|         if isinstance(o, type):
# |Alternative|             _showHint("type")
# |Alternative|             return {"«type»": _makeJsonable_fromType(o)}
# |Alternative|
# |Alternative|         if isinstance(o, list):
# |Alternative|             _showHint("list")
# |Alternative|             list_out: list[Any] = []
# |Alternative|             for index in range(len(o)):
# |Alternative|                 list_out.append(
# |Alternative|                     makeJsonable(
# |Alternative|                         o[index],
# |Alternative|                         currentDepth + 1,
# |Alternative|                         hint.removesuffix(".") + "[" + str(index) + "].",
# |Alternative|                     )
# |Alternative|                 )
# |Alternative|             return list_out
# |Alternative|
# |Alternative|         if isinstance(o, dict) or isinstance(o, OrderedDict):
# |Alternative|             _showHint("dictionary")
# |Alternative|             result: dict[str, Any] = {}
# |Alternative|             for key, value in o.items():
# |Alternative|                 result[key] = makeJsonable(
# |Alternative|                     value, currentDepth + 1, hint + key + "."
# |Alternative|                 )
# |Alternative|             return result
# |Alternative|
# |Alternative|         if isinstance(o, bytes):
# |Alternative|             _showHint("bytes")
# |Alternative|             return _makeJsonable_fromBytes(o)
# |Alternative|
# |Alternative|         if o.__class__.__name__.startswith("numpy"):
# |Alternative|             _showHint("numpy")
# |Alternative|
# |Alternative|             import numpy as np
# |Alternative|
# |Alternative|             return np.array_str(o)
# |Alternative|         if hasattr(o, "asDict"):
# |Alternative|             _showHint("asDict()")
# |Alternative|             return o.asDict()
# |Alternative|
# |Alternative|         if hasattr(o, "items"):  # < Must have type + common first
# |Alternative|             _showHint("_items")
# |Alternative|             _items = o.items()
# |Alternative|             obj_out: dict[str, Any] = {}
# |Alternative|             for _name, _value in _items:
# |Alternative|                 obj_out[_name] = makeJsonable(
# |Alternative|                     _value, currentDepth + 1, hint + _name + "."
# |Alternative|                 )
# |Alternative|             return obj_out
# |Alternative|
# |Alternative|         if hasattr(o, "__slots__"):
# |Alternative|             _showHint("slots")
# |Alternative|             outResult = {}
# |Alternative|             for field_name in o.__slots__:
# |Alternative|                 value = getattr(o, field_name, None)
# |Alternative|                 outResult[f"{field_name}"] = f"{value}"
# |Alternative|                 if str(field_name) == "__doc__":
# |Alternative|                     _doc = str(value).strip()
# |Alternative|                     if _doc != "None" and _doc != "":
# |Alternative|                         return f"<doc:{_doc.split()[0]}>"
# |Alternative|             return outResult
# |Alternative|         if hasattr(o, "__dict__"):
# |Alternative|             outResult = {}
# |Alternative|             for name,value in o.__dict__.items():
# |Alternative|                 outResult[name]=makeJsonable(value)
# |Alternative|             return outResult
# |Alternative|
# |Alternative|         _showHint("⚠️  Other")
# |Alternative|
# |Alternative|         return str(o)
# |Alternative|     except Exception as e:
# |Alternative|         _showHint("⚠️  Unable to convert {e}")
# |Alternative|         return f"⚠️  Unable to convert {hint}[{type(o)}]: {e}"
# |Alternative|

# |Alternative| def make_jsonable(
# |Alternative|     contents, base64_encoding=True
# |Alternative| ) -> list | dict[str, Any] | str | int | float | None:
# |Alternative|
# |Alternative|     if contents is None:
# |Alternative|         return None
# |Alternative|
# |Alternative|     if hasattr(contents, "__slots__"):
# |Alternative|         # This is a ROS message
# |Alternative|         d = OrderedDict()
# |Alternative|
# |Alternative|         for field_name, field_type in zip(contents.__slots__, contents.SLOT_TYPES):
# |Alternative|             value = getattr(contents, field_name, None)
# |Alternative|
# |Alternative|             # Remove leading underscore from field name
# |Alternative|             d[field_name[1:]] = make_jsonable(value, base64_encoding)
# |Alternative|         return d
# |Alternative|
# |Alternative|     if (type(contents) is dict) or (type(contents) is OrderedDict):
# |Alternative|         d = OrderedDict()
# |Alternative|         try:
# |Alternative|             for key in list(contents.keys()):
# |Alternative|                 d[key] = make_jsonable(contents[key])
# |Alternative|         except Exception as e:
# |Alternative|             print("⚠️ ukkoUtils.make_jsonable(" + str(contents) + "): " + str(e))
# |Alternative|         return d
# |Alternative|
# |Alternative|     if isinstance(contents, bytes):
# |Alternative|         if base64_encoding:
# |Alternative|             # Encode the bytes to base64
# |Alternative|             return base64.b64encode(contents).decode("utf-8")
# |Alternative|         else:
# |Alternative|             return "bytes(" + str(len(contents)) + ")"
# |Alternative|
# |Alternative|     if isinstance(contents, bytearray):
# |Alternative|         if base64_encoding:
# |Alternative|             # Encode the bytes to base64
# |Alternative|             return base64.b64encode(contents).decode("utf-8")
# |Alternative|         else:
# |Alternative|             return "bytearray(" + str(len(contents)) + ")"
# |Alternative|
# |Alternative|     if isinstance(contents, (list, tuple, array.array, np.ndarray)):
# |Alternative|         # Since arrays and ndarrays can't contain mixed types convert to list
# |Alternative|         d = list()
# |Alternative|         for x in contents:
# |Alternative|             d.append(make_jsonable(x))
# |Alternative|         return d
# |Alternative|
# |Alternative|     return contents


def rangeAsText(
    minVal: Any | None,
    maxVal: Any | None,
    optionalPrefixIfRanged: str = "",
    quoteValuesWith: str = "`",
) -> str:
    def quoteIfNeeded(val: Any) -> str:
        return f"{quoteValuesWith}{val}{quoteValuesWith}"

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


def toHex(src: bytes, maxNumChars: int | None = 60) -> str:
    txt = src.hex()
    if (maxNumChars is not None) and (len(txt) > maxNumChars):
        suffix = f"… ({len(src)} bytes)"
        maxHexChars = maxNumChars - len(suffix)
        maxHexChars -= maxHexChars % 2
        txt = f"{txt[0:maxHexChars]}{suffix}"
    return txt


# |x|def toHex(data: bytes, maxLen_chars: int = 60) -> str:
# |x|    if len(data) == 1:
# |x|        txtSuffix = " (Single byte only)"
# |x|    elif len(data) == 0:
# |x|        txtSuffix = "(Empty data)"
# |x|    else:
# |x|        txtSuffix = f" ({len(data)} bytes)"
# |x|    maxDataLenBytes = (maxLen_chars - len(txtSuffix)) // 2
# |x|    if len(data) > maxDataLenBytes:
# |x|        txtSuffix = f"… ({len(data)} bytes total)"
# |x|        maxDataLenBytes = (maxLen_chars - len(txtSuffix)) // 2
# |x|
# |x|        return data[:maxDataLenBytes].hex() + txtSuffix
# |x|    else:
# |x|        return data.hex() + txtSuffix


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


def list_removeDuplicatesAndNulls(src: list):
    unique_list = []
    for item in src:
        if (item is not None) and item not in unique_list:
            unique_list.append(item)
    return unique_list


def md5_of_file(fname: str) -> str:
    with open(fname, "rb") as file:
        raw_bytes = file.read()
        md5hash_value = hashlib.md5(raw_bytes).hexdigest()
    return md5hash_value


def md5_of_string(txt: str) -> str:
    raw_bytes = txt.encode("utf-8")
    md5hash_value = hashlib.md5(raw_bytes).hexdigest()
    return md5hash_value


def getIdSuffix(id):
    return "" if (id is None) or (id == "") else (str(id) + "/")


def typeOfAsStr(obj) -> str:
    return typeAsStr(type(obj), withBrackets=True)


def typeAsStr(dataType, withBrackets: bool = False) -> str:
    txt = str(dataType).removeprefix("<class '").removesuffix("'>")
    if withBrackets:
        return "«" + txt + "»"
    else:
        return txt


def _makeJsonable_fromType(o: type) -> str:
    try:
        # if o.__class__.__name__ != "mappingproxy":
        #    return o.__class__.__name__
        if hasattr(o, "__dict__"):
            _items = o.__dict__.items()
        elif hasattr(o, "items"):
            _items = o.items()
        else:
            _items = inspect.getmembers(o)

        outResult = {}
        for k, v in _items:
            outResult[f"{k}"] = f"{v}"
            returnThis: str | None = None
            removeSurroundings: None | Tuple[str, str] = None
            if str(k) == "__weakref__":
                removeSurroundings = ("<attribute '__weakref__' of '", "' objects>")
                returnThis = str(k)
            elif str(k) == "__str__":
                removeSurroundings = ("<slot wrapper '__str__' of '", "' objects>")
                returnThis = str(k)
            elif str(k) == "__doc__":
                _topLine = str(v).strip().splitlines()[0]
                if "->" in _topLine:
                    returnThis = _topLine.split("->")[-1]

            if returnThis is not None:
                returnThis = returnThis.strip()
                if removeSurroundings is not None:
                    _prefix = removeSurroundings[0]
                    _suffix = removeSurroundings[1]
                    if returnThis.startswith(_prefix) and returnThis.endswith(_suffix):
                        returnThis = returnThis[len(_prefix) : -len(_suffix)].strip()
                return f"«{returnThis}»"
        return f"⚠️  Unknown TypeConversion: {str(o)}"
    except Exception as e:
        return f"⚠️  Invalid TypeConversion: {e}"


def _makeJsonable_fromBytes(o: bytes) -> dict[str, Any] | str:

    # UTF-8 is the most common encoding for byte data, so we will try to decode it as UTF-8 first. If that fails, we will fall back to a hex representation.
    _len = len(o)
    if _len == 0:
        return ""
    extra = ""
    try:
        earlyPart = o[:100]
        if not (0 in earlyPart) and not (
            0xFF in earlyPart
        ):  # Just a check to avoid trying to decode obviously non-text data - this is not perfect but should avoid annoyances when trapping raised exceptions
            return {"utf-8": o.decode("utf-8")}
    except UnicodeDecodeError:
        pass
    except Exception as e:
        extra = f" (decoding error: {e})"
    TRUNCATION_LIMIT = None

    obj: dict[str, Any] = {"kind": "bytes", "len": _len}
    if TRUNCATION_LIMIT is None:
        obj["hex"] = o.hex()
    elif _len <= TRUNCATION_LIMIT * 2:
        obj["hex"] = o.hex()
    else:
        obj["truncated"] = TRUNCATION_LIMIT
        obj["hex"] = o[:TRUNCATION_LIMIT].hex() + "…" + o[-TRUNCATION_LIMIT:].hex()

    if extra != "":
        obj["_note"] = extra
    return obj


def _makeJsonable_fromOther(src: Any, kind: str):
    result: dict[str, Any] = {}
    try:
        for key in ["__name__", "__package__", "__file__"]:
            value = src.get(key)
            if value is not None:
                valueText = str(value)
                if valueText:
                    result[key.removeprefix("__").removesuffix("__")] = valueText
        if not result:
            result["_keys"] = list(src.keys())
    except Exception as ee:
        result["error"] = f"⚠️  [Other]: {ee}"

    fullResult: dict[str, Any] = {
        "type": kind.removeprefix("<class '").removesuffix("'>")
    }
    fullResult.update(result)
    return fullResult


class DeviceStateEnum:
    DEVICE_STATE_OFF = 0
    DEVICE_STATE_ENABLED = 1
    DEVICE_STATE_ENABLE_FAILED = 2
    DEVICE_STATE_ACTIVE_RUNNING = 3

    @staticmethod
    def asText(state):
        txt = ""
        if state == DeviceStateEnum.DEVICE_STATE_OFF:
            txt = "OFF"
        elif state == DeviceStateEnum.DEVICE_STATE_ENABLED:
            txt = "ENABLED"
        elif state == DeviceStateEnum.DEVICE_STATE_ENABLE_FAILED:
            txt = "❌ ENABLE_FAILED"
        elif state == DeviceStateEnum.DEVICE_STATE_ACTIVE_RUNNING:
            txt = "ACTIVE_RUNNING"
        else:
            txt = "❌ UNKNOWN"

        return txt + " (" + str(state) + ")"


class LineNumber:
    def __str__(self):
        x = inspect.currentframe()
        if (x is None) or (x.f_back is None):
            return "?"
        else:
            return str(x.f_back.f_lineno)


__line__ = LineNumber()


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
