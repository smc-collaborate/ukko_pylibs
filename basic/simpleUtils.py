import array
import base64
from collections import OrderedDict
import hashlib
import inspect
import json
import re
import sys
import textwrap
import time
import traceback
from typing import Any, Callable
from datetime import datetime as dt_datetime
from datetime import timezone as dt_timezone

################################################################################
#
# Add project root directory to system path

import os

import numpy as np


shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

################################################################################
#
pwdOnModuleLoad = os.getcwd()


def get_cwdOnStartup():
    cwdOnStartup = os.getenv("ORIG_PWD")

    if not cwdOnStartup:
        try:
            if sys.modules.get("ukko_pylibs.app.appSupport") is not None:
                from ukko_pylibs.app.appSupport import appInfo_get

                runningDir = appInfo_get("APP_DEFINITION.runningDir", "")
                cwdOnStartup = runningDir
        except Exception:
            pass

    if not cwdOnStartup:
        cwdOnStartup = pwdOnModuleLoad
    return cwdOnStartup


def print_error(msg, optional_extra_msg=None):

    msg_full = f"{msg}{optional_extra_msg if optional_extra_msg else ''}"

    try:
        if sys.modules.get("ukko_pylibs.app.appSupport") is not None:
            from ukko_pylibs.app.appSupport import appLog

            appLog.print_error(msg_full)
            return
    except BaseException:
        sys.stderr.write(f"❌ Error: {msg_full}\n")
    return


def print_warning(msg):

    try:
        if sys.modules.get("ukko_pylibs.app.appSupport") is not None:
            from ukko_pylibs.app.appSupport import appLog

            appLog.print_warning(msg)
            return
    except BaseException:
        sys.stderr.write(f"⚠️ Warning: {msg}\n")
    return


def print_tediousDetail(msg: str):

    try:
        if sys.modules.get("ukko_pylibs.app.appSupport") is not None:
            from ukko_pylibs.app.appSupport import appLog

            appLog.print_tediousDetail(msg)
            return
    except BaseException:
        pass
    sys.stderr.write(f"🔍  Detailed: {msg}\n")


def print_verbose(msg: str):

    try:
        if sys.modules.get("ukko_pylibs.app.appSupport") is not None:
            from ukko_pylibs.app.appSupport import appLog

            appLog.print_verbose(msg)
            return
    except BaseException:
        pass
    sys.stderr.write(f"ℹ️  Verbose: {msg}\n")


def print_info(msg: str):
    try:
        if sys.modules.get("ukko_pylibs.app.appSupport") is not None:
            from ukko_pylibs.app.appSupport import appLog

            appLog.print_info(msg)
            return
    except BaseException:
        pass
    sys.stderr.write(f"ℹ️  Info: {msg}\n")


class Utils:
    @staticmethod
    def is_iterable(obj) -> bool:
        try:
            iter(obj)
            return True
        except TypeError:
            return False

    @staticmethod
    def isStdoutText():
        stdout_is_tty_txt = (
            os.environ.get("STDOUT_IS_TTY", "1" if sys.stdout.isatty() else "0")
            .removeprefix('"')
            .removesuffix('"')
        )
        isConsoleOut = not (
            str(stdout_is_tty_txt).lower() in ["0", "", "none", "false"]
        )
        return isConsoleOut

    @staticmethod
    def pathDisplay(pathName: str) -> str:
        """Converts a path to a friendly display format."""
        return Utils.pathConvert(pathName, kind="friendly").removesuffix(os.sep)

    @staticmethod
    def pathConvert(pathName: str, kind: str = "friendly") -> str:
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
            options.append(Utils.pathConvert(path, "abs"))
            options.append(Utils.pathConvert(os.path.realpath(path), "abs"))
            options.append(Utils.pathConvert(path, "abs:~"))
            options.append(Utils.pathConvert(os.path.realpath(path), "abs:~"))
        elif kind == "abs:~":
            homedir = os.path.expanduser("~")

            path = os.path.abspath(path)
            if path == homedir:
                path = "~"
            elif path.startswith(homedir + os.sep):
                path = "~" + os.sep + path.removeprefix(homedir + os.sep)
            options.append(path)
        elif kind == "rel" or kind == "rel:real":
            cwdOnStartup = get_cwdOnStartup()

            if cwdOnStartup:
                if kind.endswith(":real"):
                    cwdOnStartup = os.path.realpath(cwdOnStartup)
                extra += f"[cwdOnStartup:{cwdOnStartup}]"
                path = os.path.relpath(path, cwdOnStartup)
            else:
                path = os.path.relpath(path)
            options.append(path)
        elif kind == "friendly":

            options.append(Utils.pathConvert(path, "abs:friendly"))
            options.append(Utils.pathConvert(path, "rel"))
            options.append(Utils.pathConvert(os.path.realpath(path), "abs:friendly"))
            options.append(Utils.pathConvert(os.path.realpath(path), "rel:real"))
            options.append(path)
        else:
            options.append(path)

        path = min(options, key=lambda x: len(x))

        # |Logging| print(f"----------")
        # |Logging| print(f"pathConvert[{kind}] {extra}\n: {pathName}\n→ {path}")
        # |Logging| print(f"----------")
        return path

    @staticmethod
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
        else:
            return f"[{type(data).__name__}]:{str(data)}"

    @staticmethod
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
            return print_error(f"Text File not found at '{file_path}'")
        except Exception as e:
            return print_error(f"An exception occurred: {e}")

    @staticmethod
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

    @staticmethod
    def json_load_dict_from_file(fname: str) -> dict[str, Any]:
        """
        Load a JSON dict from a file

        Args:
            fname (str): The name of the file to load

        Returns:
            dict: The loaded configuration as a dictionary.
        """
        result = Utils.json_load_from_file(fname, None)
        return result if isinstance(result, dict) else {}

    @staticmethod
    def json_loads(txt: str) -> Any | None:
        try:
            return json.loads(txt)
        except json.JSONDecodeError as e:
            txt = re.sub(r"\\x([0-9a-fA-F]{2})", r"\\u00\1", txt)

        return json.loads(
            txt
        )  # < Let the exception propagate this time - there isn't much more we can do

    @staticmethod
    def asJsonStr(obj, indent: int | str | None = None):
        """Safer version of json.dumps that can handle some extra types like bytes and avoids odd crashes"""

        def stripStartAndEnd(s: Any, prefix: str, suffix: str) -> str | None:
            if s is None:
                return None
            s = str(s).strip()
            if s.startswith(prefix) and s.endswith(suffix):
                return s[len(prefix) : -len(suffix)]
            else:
                return None

        class JsonEncoderExtended(json.JSONEncoder):
            def default(self, o):
                # return f"<Obj[{o.__class__.__name__}:{type(o)}]"
                try:
                    if isinstance(o, type):
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
                            returnThis = None
                            if str(k) == "__weakref__":
                                returnThis = stripStartAndEnd(
                                    str(v),
                                    "<attribute '__weakref__' of '",
                                    "' objects>",
                                )
                            if str(k) == "__str__":
                                returnThis = stripStartAndEnd(
                                    str(v), "<slot wrapper '__str__' of '", "' objects>"
                                )

                            if str(k) == "__doc__":
                                _topLine = str(v).strip().splitlines()[0]
                                if "->" in _topLine:
                                    returnThis = _topLine.split("->")[-1]

                            if returnThis is not None:
                                return f"«{returnThis}»"
                        return {"«type»": outResult}

                    if isinstance(o, bytes):
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
                            obj["hex"] = (
                                o[:TRUNCATION_LIMIT].hex()
                                + "…"
                                + o[-TRUNCATION_LIMIT:].hex()
                            )

                        if extra != "":
                            obj["_note"] = extra
                        return obj
                    elif o.__class__.__name__.startswith("numpy"):
                        import numpy as np

                        return np.array_str(o)
                    elif not isinstance(o, type) and hasattr(o, "asDict"):
                        return o.asDict()
                    elif hasattr(o, "__slots__"):
                        outResult = {}
                        for field_name in o.__slots__:
                            value = getattr(o, field_name, None)
                            outResult[f"{field_name}"] = f"{value}"
                            if str(field_name) == "__doc__":
                                _doc = str(value).strip()
                                if _doc != "None" and _doc != "":
                                    return f"<doc:{_doc.split()[0]}>"
                        return outResult
                    elif hasattr(o, "__dict__"):
                        return o.__dict__
                    else:
                        return str(o)
                except Exception as e:
                    return f"<Object[{o.__class__.__name__}:{type(o)}] (Note: {e})>"

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

    @staticmethod
    def toHexText(src: bytes, maxNumChars: int | None = 100) -> str:
        txt = src.hex()
        if (maxNumChars is not None) and (len(txt) > maxNumChars):
            suffix = f"… ({len(src)} bytes)"
            maxHexChars = maxNumChars - len(suffix)
            maxHexChars -= maxHexChars % 2
            txt = f"{txt[0:maxHexChars]}{suffix}"
        return txt

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
            txtSuffix = f"… ({len(data)} bytes total)"
            maxDataLenBytes = (maxLen_chars - len(txtSuffix)) // 2

            return data[:maxDataLenBytes].hex() + txtSuffix
        else:
            return data.hex() + txtSuffix

    @staticmethod
    def _make_jsonable(
        contents, base64_encoding=True
    ) -> list | dict[str, Any] | str | int | float | None:

        if contents is None:
            return None

        if hasattr(contents, "__slots__"):
            # This is a ROS message
            d = OrderedDict()

            for field_name, field_type in zip(contents.__slots__, contents.SLOT_TYPES):
                value = getattr(contents, field_name, None)

                # Remove leading underscore from field name
                d[field_name[1:]] = Utils._make_jsonable(value, base64_encoding)
            return d

        if (type(contents) is dict) or (type(contents) is OrderedDict):
            d = OrderedDict()
            try:
                for key in list(contents.keys()):
                    d[key] = Utils._make_jsonable(contents[key])
            except Exception as e:
                print("⚠️ Utils._make_jsonable(" + str(contents) + "): " + str(e))
            return d

        if isinstance(contents, bytes):
            if base64_encoding:
                # Encode the bytes to base64
                return base64.b64encode(contents).decode("utf-8")
            else:
                return "bytes(" + str(len(contents)) + ")"

        if isinstance(contents, bytearray):
            if base64_encoding:
                # Encode the bytes to base64
                return base64.b64encode(contents).decode("utf-8")
            else:
                return "bytearray(" + str(len(contents)) + ")"

        if isinstance(contents, (list, tuple, array.array, np.ndarray)):
            # Since arrays and ndarrays can't contain mixed types convert to list
            d = list()
            for x in contents:
                d.append(Utils._make_jsonable(x))
            return d

        return contents

    @staticmethod
    def msg_to_dict(
        msg, is_full: bool = True
    ) -> dict[str, Any] | OrderedDict[str, Any] | None:
        if msg is None:
            return None

        # |Quick| if isinstance(msg, AnnotatedData):
        # |Quick|     return msg.toFullJson(is_full)
        try:
            result = Utils._make_jsonable(
                msg, is_full
            )  # msgconverter.convert_ros_message_to_dictionary(msg,True)
            try:
                result = DictUtils.doCleanup(result)
            except Exception as e:
                print("⚠️ Utils.msg_to_dict(" + str(msg) + "): " + str(e))

            if not (type(result) is dict) and not (type(result) is OrderedDict):
                return {"value": result}
            else:
                return result

        except Exception as e:
            print("⚠️ Utils.msg_to_dict(" + str(msg) + "): " + str(e))
            print(traceback.format_exc())
            return {"msg_to_dict.ee": str(e)}

    @staticmethod
    def msg_to_json_text(msg, is_full: bool = False):
        if msg is None:
            return "null"

        try:
            result = Utils.msg_to_dict(msg, is_full)

            return Utils.asJsonStr(result)
        except Exception as e:
            print("⚠️ Utils.msg_to_json_text(" + str(type(msg)) + "): " + str(e))

            result = {"msg_to_json_text.ee": str(e)}
            return Utils.asJsonStr(result)

    @staticmethod
    def getIdSuffix(id):
        return "" if (id is None) or (id == "") else (str(id) + "/")


class PrettyText:
    @staticmethod
    def asClipped(
        text: Any,
        maxLen: int = 20,
        suffix: str = "…",
        formatter: Callable | None = None,
    ) -> str:
        _text = str(formatter(text)) if formatter else str(text)

        if len(_text) > maxLen:
            maxLen -= len(suffix)
            return _text[0:maxLen] + suffix
        else:
            return _text

    @staticmethod
    def asPrintableAscii(charCode: int) -> str:
        if (charCode < 32) or (charCode > 126):
            return f"\\x{charCode:02x}"
        else:
            return chr(charCode)

    @staticmethod
    def aOrAn(item: str) -> str:
        if item is not None and len(item) > 0 and item[0].lower() in "aeiou":
            # If the first letter is a vowel, return "an"
            return "an"
        else:
            return "a"

    @staticmethod
    def withAOrAn(item: str) -> str:
        return f"{PrettyText.aOrAn(item)} {item}"

    @staticmethod
    def pluralize(count: int | float, singular: str, plural: str | None = None):
        return f"{count} {PrettyText.pluralizeName(count, singular, plural)}"

    @staticmethod
    def pluralizeName(count: int | float, singular: str, plural: str | None = None):
        if singular == "":
            singular = "item"

        if count == 1:
            return singular
        elif plural is not None:
            return plural
        else:
            return PrettyText.pluralizeSingular(singular)

    @staticmethod
    def pluralizeSingular(singular: str):
        if singular == "":
            singular = "item"

        if singular.endswith("y"):
            plural = singular.removesuffix("y") + "ies"
        elif (singular.endswith("s")) or (singular.endswith("x")):
            plural = singular + "es"
        else:
            plural = singular + "s"

        return plural

    @staticmethod
    def UniLen_approx(s: str) -> int:
        # A simple approximation of the display width of a string, treating wide characters as 2 and narrow as 1
        # This is not perfect but should work reasonably well for most cases
        width = 0
        for ch in s:
            if ch in ["🔒", "❌", "✅", "⚠️", "ℹ️", "❓", "⭐", "🔍"]:
                width += 2
            else:
                width += 1
        return width

    @staticmethod
    def withSubstitutions(
        src: str, prefix: str, substitutions: dict[str, Any], suffix: str
    ) -> str:
        """Replaces all occurrences of prefix+key{:xxx}+suffix in src with the corresponding value from substitutions"""
        if prefix == "":
            raise ValueError("Prefix cannot be empty")

        _parts = src.split(prefix)
        if len(_parts) == 1:
            return src
        txtOut = _parts[0]
        for txt in _parts[1:]:
            _n = txt.find(suffix)
            substText: str | None = None
            if _n < 0:
                print_warning(
                    f"PrettyText.withSubstitutions({prefix}…{suffix}): Found prefix '{prefix}' without matching suffix '{suffix}'"
                )
            else:
                keyAndFormatting = txt[0:_n].split(":", 1)
                key = keyAndFormatting[0]

                if not (key in substitutions):
                    print_warning(
                        f"PrettyText.withSubstitutions({prefix}{':'.join(keyAndFormatting)}{suffix}): No substitution found for key '{key}'"
                    )
                elif len(keyAndFormatting) > 1:
                    formatSpec = keyAndFormatting[1]
                    try:
                        substText = format(substitutions[key], formatSpec)
                    except Exception as e:
                        print_warning(
                            f"PrettyText.withSubstitutions({prefix}{':'.join(keyAndFormatting)}{suffix}): Error formatting value '{substitutions[key]}' with format spec '{formatSpec}': {e}"
                        )
                else:
                    substText = str(substitutions[key])
            if substText is not None:
                txtOut += substText + txt[_n + len(suffix) :]
            else:
                txtOut += prefix + txt
        return txtOut

    @staticmethod
    def textWrapWithPrefixes(
        txt: str, maxWidth: int | None = None, prefixes: list[str] | None = None
    ) -> list[str]:
        if maxWidth is None or len(txt) < maxWidth:
            return [txt]

        prefixToAppend = ""
        otherPrefixes = ""
        if prefixes is not None:
            for prefix in prefixes:
                if txt.startswith(prefix):
                    txt = txt[len(prefix) :]
                    prefixToAppend = prefix
                    otherPrefixes = " " * len(prefix)
                    maxWidth -= len(prefix)
                    break
        parts = textwrap.wrap(txt, width=maxWidth)
        lines = []
        lines.append(prefixToAppend + parts.pop())
        for part in parts:
            lines.append(otherPrefixes + part)
        return lines


class DictUtils:
    @staticmethod
    def getWithDefaultValuesRemoved(
        dictIn: dict, defaultValues: dict[str, Any], recurseDicts: bool = False
    ) -> dict[str, Any]:
        """Removes keys from dictIn that have the same value as in defaultValues"""
        result = {}
        # | ExtraLogging print_verbose("------------------------------")
        # | ExtraLogging print_verbose(f"getWithDefaultValuesRemoved({Utils.asJsonStr(dictIn)},defaultValues: {Utils.asJsonStr(defaultValues)}):")
        for key, value in dictIn.items():
            if isinstance(value, dict) and (recurseDicts == True):
                defaultValue = defaultValues.get(key, None)
                if isinstance(defaultValue, dict) and (len(defaultValue) > 0):
                    value = DictUtils.getWithDefaultValuesRemoved(
                        value, defaultValue, recurseDicts=True
                    )
                    if value != {}:
                        result[key] = value
                        continue
            if key not in defaultValues or defaultValues[key] != value:
                # | ExtraLogging print_verbose(f"{key}:[default: {Utils.asJsonStr(defaultValues.get(key,None))}, actual: {Utils.asJsonStr(value)})]")
                result[key] = value
        # | ExtraLogging print_verbose(f"->{Utils.asJsonStr(result)}")
        # | ExtraLogging print_verbose("------------------------------")
        return result

    @staticmethod
    def extend(modifyThis: dict[str, Any], withThis: dict[str, Any] | None) -> None:
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
                    for x in v + [
                        None
                    ]:  # Add a None at the end to flush the last range
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
        obj_in: dict[str, Any] | list[Any] | None,
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

        obj_to_modify = DictUtils.get(obj, iterateList)

        if isinstance(obj_to_modify, dict) and key_to_modify in obj_to_modify:
            obj_to_modify.pop(key_to_modify, None)
            return True
        else:
            return False

    @staticmethod
    def deleteIfIs(obj: dict[str, Any], keys: str | list[str], value: Any) -> bool:
        iterateList = keys.split("/") if isinstance(keys, str) else keys.copy()

        key_to_modify = iterateList.pop()

        obj_to_modify = DictUtils.get(obj, iterateList)

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
                    f"⚠️  DictUtils.set(a): Expected dict, but got {type(obj)} for key '{key}' in {Utils.asJsonStr(obj)} - \n"
                )
                return False

            if not (k in obj):
                obj[k] = {}
            if not isinstance(obj[k], dict):
                sys.stderr.write(
                    f"⚠️  DictUtils.set(b): Expected dict, but got {type(obj[k])} for key '{k}' in {Utils.asJsonStr(obj)} - \n"
                )
                obj[k] = {}
            obj = obj[k]

        if isinstance(obj, dict):
            obj[key] = value
            return True
        else:
            sys.stderr.write(
                f"⚠️  DictUtils.set(c): Expected dict, but got {type(obj)} for key '{key}' in {Utils.asJsonStr(obj)} - \n"
            )
            return False

    @staticmethod
    def getInt(
        obj_in: dict[str, Any] | list[Any] | None,
        keys: str | list[str],
        defaultIfNotFound: int,
    ) -> int:
        try:
            result = DictUtils.get(obj_in, keys, defaultIfNotFound)

            if isinstance(result, int):
                return result

            sys.stderr.write(
                f"⚠️  DictUtils.getInt(): Expected int but got {type(result)}:{result}.  Returning default {defaultIfNotFound}\n"
            )
        except Exception as e:
            sys.stderr.write(f"⚠️  DictUtils.getInt(): Exception {e}\n")
        return defaultIfNotFound

    @staticmethod
    def getBool(
        obj: dict[str, Any] | None, key: str | list[str], defaultValue: bool
    ) -> bool:
        result = DictUtils.get(obj, key)
        return (
            defaultValue
            if (result is None) or (not isinstance(result, bool))
            else result
        )

    @staticmethod
    def getBoolOrFalse(obj: dict[str, Any] | None, key: str | list[str]) -> bool:
        return DictUtils.getBool(obj, key, False)

    @staticmethod
    def getIntOrNone(
        obj: dict[str, Any] | None,
        key: str | list[str],
        defaultValue: int | None = None,
    ) -> int | None:
        value = DictUtils.get(obj, key, None)
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
                f"⚠️  getIntOrNone(): Expected int or str, but got {type(value)} for key '{key}' in {Utils.asJsonStr(obj)}\n"
            )
            return defaultValue

    @staticmethod
    def getStr(obj: dict[str, Any], key: str | list[str], defaultValue: str) -> str:
        value = DictUtils.get(obj, key)
        if value is None:
            return defaultValue
        else:
            return str(value)

    @staticmethod
    def getStrOrNone(obj: dict[str, Any] | None, key: str | list[str]) -> str | None:
        value = DictUtils.get(obj, key, None)
        if value is None:
            return None
        else:
            return str(value)

    @staticmethod
    def getDict(
        obj_in: dict[str, Any] | None,
        keys: str | list[str],
        defaultIfNotFound: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        _defaultIfNotFound = defaultIfNotFound or {}
        try:
            result = DictUtils.get(obj_in, keys, _defaultIfNotFound)

            if result is None:
                return _defaultIfNotFound
            elif isinstance(result, dict):
                return result
            else:
                sys.stderr.write(
                    f"⚠️  DictUtils.getDict({keys}): Expected dict, but got {type(result)} in {Utils.asJsonStr(obj_in)}\n"
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
                return "new:" + Utils.asJsonStr(contents_new)
            if contents_new is None:
                return "removed: " + Utils.asJsonStr(contents_old)

            if type(contents_old) != type(contents_new):
                return (
                    Utils.asJsonStr(contents_old)
                    + " types:-> "
                    + Utils.asJsonStr(contents_new)
                )

            if (type(contents_old) is not dict) and (
                type(contents_old) is not OrderedDict
            ):
                return (
                    Utils.asJsonStr(contents_old)
                    + " -> "
                    + Utils.asJsonStr(contents_new)
                )

            result = dict()

            for key in list(contents_old.keys()):
                try:
                    diff = DictUtils.dict_diff(
                        contents_old.get(key, None), contents_new.get(key, None)
                    )
                    if diff is not None:
                        result[key] = diff
                except Exception as e:
                    result[key] = "⚠️ Utils.dict_diff(" + key + ").a: " + str(e)

            for key in list(contents_new.keys()):
                try:
                    if key not in contents_old:
                        result[key] = "New: " + Utils.asJsonStr(contents_new[key])
                except Exception as e:
                    result[key] = "⚠️ Utils.dict_diff(" + key + ").b: " + str(e)

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
                                # |x| print(f"ℹ️ DictUtils.doCleanup[{key}] = Type {type(value)}: a   ")
                                if len(value) > 0:
                                    # |x| print(f"ℹ️ DictUtils.doCleanup[{key}] = Type {type(value)}: ab    {type(value[0])}")

                                    if isinstance(value[0], int) or isinstance(
                                        value[0], np.integer
                                    ):  # |x| or isinstance(value[0],np.uint8):
                                        # |x| print(f"ℹ️ DictUtils.doCleanup[{key}] = Type {type(value)}: abc   ")
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

                        # |x| print(f"ℹ️ DictUtils.doCleanup[{key}] = Type {type(value)}: {value} = {valueAsText}")

                        # |Logging| print("!!! DictUtils.doCleanup(" + key + "): " + str(value))
                        if key.startswith("diag_json_") and (valueAsText is not None):
                            # |Logging| print("!! Interpreting diag_json: " + key + " = " + value)
                            if (valueAsText != "") and (valueAsText != "null"):
                                contents["diag_" + key.removeprefix("diag_json_")] = (
                                    Utils.json_loads(valueAsText)
                                )
                            del contents[key]
                        elif (key == "json") and (valueAsText is not None):
                            if (valueAsText != "") and (valueAsText != "null"):
                                contents["json_obj"] = Utils.json_loads(valueAsText)
                            del contents[key]
                        elif (type(value) is dict) or (type(value) is OrderedDict):
                            contents[key] = DictUtils.doCleanup(value)
                        elif key == "device_state":
                            contents[key + "_text"] = DeviceStateEnum.asText(value)
                            del contents[key]
                        elif (
                            key.endswith("_error_msg") or key.endswith("_err_msg")
                        ) and (valueAsText == ""):
                            del contents[key]

                    except Exception as e:
                        sys.stderr.write(f"⚠️ DictUtils.doCleanup({key}): {e}\n")
            except Exception as e:
                sys.stderr.write(f"⚠️ DictUtils.doCleanup({contents}): {e}\n")
        # |x| print(f"ℹ️ DictUtils.doCleanup[{__file__}] -> {contents}")

        return contents


class EscapeMgr:
    @staticmethod
    def fromEscapedText(value: str) -> str:
        valueOut: str = str(value)
        try:
            valueOut = json.loads(f'"{value}"')
        except Exception as e:
            print_warning(
                f"Error interpreting {json.dumps(str(value))} as escaped text: {e}"
            )
        print_tediousDetail(
            f"Interpreting value as escaped text: '{value}' -> json {json.dumps(valueOut)}"
        )
        return valueOut

    @staticmethod
    def unEscape(value: Any | None, defaultIfNone: Any | None = None) -> Any | None:

        if value is None:
            return defaultIfNone
        elif isinstance(value, str):
            return EscapeMgr.fromEscapedText(value)
        else:
            return str(value)

    @staticmethod
    def asEscapedText(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False).removeprefix('"').removesuffix('"')

    @staticmethod
    def escapeIfNeeded(value: Any) -> str:
        x = json.dumps(value, ensure_ascii=False)
        if x.startswith('"') and x.endswith('"') and ((" " in x) or ("\\" in x)):
            return x
        else:
            return x.removeprefix('"').removesuffix('"')

    @staticmethod
    def asOptionallyEscapedText(value: Any, applyEscaping: bool = True) -> Any:
        if applyEscaping and isinstance(value, str):
            return EscapeMgr.asEscapedText(str(value))
        else:
            return value

    @staticmethod
    def asBashParam(
        value: Any, name_optional: str = "", withEscaping: bool = True
    ) -> str:
        if value is None:
            return ""
        valueTxt = str(value)
        if withEscaping:
            valueTxt = EscapeMgr.asEscapedText(valueTxt)
        if name_optional == "":
            resultTxt = ""
        else:
            resultTxt = f"--{name_optional}="

        bashIssues = EscapeMgr.reviewForBashParams(valueTxt)
        if not bashIssues:
            resultTxt += valueTxt
        elif bashIssues == {"empty"} or not "singleQuotes" in bashIssues:
            resultTxt += f"'{valueTxt}'"
        elif not (bashIssues & {"backticks", "dollarSigns", "doubleQuotes"}):
            resultTxt += f'"{valueTxt}"'
        else:
            resultTxt += "'" + valueTxt.replace("'", "'\\''") + "'"

        print_tediousDetail(f"asBashParam({json.dumps(value)} -> {resultTxt})")
        return resultTxt

    @staticmethod
    def reviewForBashParams(value: str) -> set[str]:
        result = set[str]()

        if value == "":
            result.add("empty")
        if "'" in value:
            result.add("singleQuotes")
        if '"' in value:
            result.add("doubleQuotes")
        if " " in value:
            result.add("spaces")
        if "`" in value:
            result.add("backticks")
        if "$" in value:
            result.add("dollarSigns")
        if "|" in value:
            result.add("pipes")
        if "<" in value:
            result.add("lessThan")
        if ">" in value:
            result.add("greaterThan")
        if "&" in value:
            result.add("ampersands")
        if "(" in value:
            result.add("openParens")
        if ")" in value:
            result.add("closeParens")
        if "{" in value:
            result.add("openBraces")
        if "}" in value:
            result.add("closeBraces")
        if "[" in value:
            result.add("openBrackets")
        if "]" in value:
            result.add("closeBrackets")
        if "\\" in value:
            result.add("backslashes")
        if (value < " ") or (value > "~"):
            result.add("requiresEscaping")

        print_tediousDetail(
            f"Reviewing value for bash parameters: json:{json.dumps(value)} -> {result}"
        )
        return result


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


class ImageInfo:
    @staticmethod
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

    @staticmethod
    def isStandardImageFormat(ext: str) -> bool:
        return ImageInfo.asStandardImageFormatOrNone(ext) is not None

    @staticmethod
    def makeImageFormatExt(ext: str) -> str:
        ext = ext.strip().removeprefix(".").lower()
        return "." + ("" if ImageInfo.isStandardImageFormat(ext) else "raw_") + ext

    @staticmethod
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


first_ns: int | None = None


class LineNumber:
    def __str__(self):
        x = inspect.currentframe()
        if (x is None) or (x.f_back is None):
            return "?"
        else:
            return str(x.f_back.f_lineno)


__line__ = LineNumber()


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


def diff_from_start_ns(time_ns: int):
    global first_ns

    time_ns = time.monotonic_ns()
    if first_ns is None:
        first_ns = time_ns
        return "0 ms [Start]"
    else:
        diff_ms = (time_ns - first_ns) / 1_000_000  # Convert to milliseconds
        return f"{diff_ms:.1f} msᵀ"  # ᵀ marker indicates a warning - assuming time is synced perfectly between the spacecraft and this system


def logTimed(msg: str):
    """
    Log a message with a timestamp.
    """
    print(f"{diff_from_start_ns(time.monotonic_ns())} ms : {msg}")


def time_ns_toText(ns: int):
    now_ns = time.monotonic_ns()
    diff_from_start_ns(now_ns)

    return f"{diff_from_start_ns(ns)} ago"
