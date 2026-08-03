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


NameValuePair = Tuple[str, Any | None]
NameValuePairList = list[NameValuePair]


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


def pluralize(count: int | float, singular: str, plural: str | None = None):
    return f"{count} {pluralizeName(count, singular, plural)}"


def pluralizeName(count: int | float, singular: str, plural: str | None = None):
    if singular == "":
        singular = "item"

    if count == 1:
        return singular
    elif plural is not None:
        return plural
    else:
        return pluralizeSingular(singular)


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


def uniLen_approx(s: str) -> int:
    """A simple approximation of the display width of a string, treating wide characters as 2 and narrow as 1
    This is not intended to be perfect (thus the '_approx' in the name) but works well for our use cases
    """
    width = 0
    for ch in removeAnsiCodes(s):
        if ch in ["🔒", "❌", "✅", "⚠️", "ℹ️", "❓", "⭐", "🔍", "↩", "↤"]:
            width += 2
        else:
            width += 1
    return width


def asSpaces(s: str) -> str:
    return " " * uniLen_approx(s)


def padToWidth(value: Any, width: int, direction: str = "<") -> str:
    """Direction can be '>' (text on right), '^' (text center), or '<' (text on left) (default)
    Think of this being equivalent to '{:<width}', '{:>width}', or '{:^width}' in python's format specifiers, but this handles wide unicode characters and ANSI codes
    """
    text = str(value)
    vis = uniLen_approx(text)
    padLen = max(0, width - vis)
    if direction == ">":
        return (" " * padLen) + text
    elif direction == "^":
        left = padLen // 2
        right = padLen - left
        return (" " * left) + text + (" " * right)
    else:  # direction == "<"
        return text + (" " * padLen)


def withSubstitutions(
    src: str,
    substitutions_: dict[str, Any],
    prefix: str = "{",
    suffix: str = "}",  # < These defaults make it compatible with python's 'parse' function
) -> str:
    substitutions = deepcopy(substitutions_)
    warning_format = substitutions.pop(
        "[warning_format]", "PrettyText.withSubstitutions({keyNote}): {msg}"
    )

    def giveWarning(key: str, msg: str):

        from appLogging import appLog

        appLog.print_warning(
            warning_format.format(keyNote=prefix + key + suffix, key=key, msg=msg)
        )

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
            giveWarning(
                "…Missing:",
                f"Found prefix '{prefix}' without matching suffix '{suffix}'",
            )
        else:
            keySource = txt[0:_n]
            keyAndFormatting = keySource.split(":", 1)
            key = keyAndFormatting[0]

            if not (key in substitutions):
                giveWarning(keySource, f"{key} not in {substitutions}")
            elif len(keyAndFormatting) > 1:
                formatSpec = keyAndFormatting[1]
                try:
                    substText = format(substitutions[key], formatSpec)
                except Exception as e:
                    giveWarning(
                        keySource,
                        f"Error formatting value '{substitutions[key]}' with format spec '{formatSpec}': {e}",
                    )
            else:
                substText = str(substitutions[key])
        if substText is not None:
            txtOut += substText + txt[_n + len(suffix) :]
        else:
            txtOut += prefix + txt
    return txtOut


def doParseText(format: str, input: str | None) -> dict[str, Any]:
    """
    Parses `input` according to a template `format` string containing
    {field_name} placeholders, and returns a dict of the extracted values.

    Example:
        PrettyText.doParseText("Hi {name}, today is {day}","Hi Fred, today is Tuesday")
        -> {'success':True,'values':{'name': 'Fred', 'day': 'Tuesday'}}
        PrettyText.doParseText("Hi {name}, today is {day}",None)
        -> {'success':True,'values':{'name': '{name}', 'day': '{day}'}}
    """
    if input is None:
        input = format
    try:
        import re

        token_pattern = re.compile(r"\{(\w+)\}")

        regex_parts: list[str] = []
        last_end = 0

        for m in token_pattern.finditer(format):
            # Escape the literal text that comes before this placeholder
            literal = format[last_end : m.start()]
            regex_parts.append(re.escape(literal))

            field_name = m.group(1)
            # Non-greedy capture group named after the field
            regex_parts.append(f"(?P<{field_name}>.+?)")

            last_end = m.end()

        # Escape any trailing literal text after the last placeholder
        regex_parts.append(re.escape(format[last_end:]))

        pattern = "^" + "".join(regex_parts) + "$"
        match = re.match(pattern, input)

        if not match:
            return {
                "success": False,
                "error": f"Input {input!r} does not match format {format!r}",
            }
        else:
            return {"success": True, "values": match.groupdict()}

    except Exception as e:
        return {"success": False, "error": "Exception: " + str(e)}


def removeAnsiCodes(text: str, doStrip: bool = True) -> str:
    # Matches ANSI escape sequences
    if doStrip:
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)
    else:
        return text


def containsAnsiCode(text: str) -> bool:
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return bool(ansi_escape.search(text))


def textWrap(txt: str, maxWidth: int | None = None) -> list[str]:
    return textWrapWithPrefixes(txt, maxWidth, prefixes=False)


class SlashTextWrapper(textwrap.TextWrapper):
    """Custom wrapper that treats slashes as breaking boundaries."""

    # Overriding the default word-splitting regex to include slashes
    wordsep_re = re.compile(
        r"(\s+|"  # Whitespace
        r"(?<=[\w\!\"\'\&\.\,\?])-{2,}(?=\w)|"  # Em-dash
        # r"(?<=\w)-(?=\w)|"  # Hyphenated words
        #        r'(?<=[/])|(?=[/]))'                       # Break right before or after a slash
        r"(?<=[/]))"  # Break immediately after a slash
    )


def textWrapWithPrefixes(
    _txt: str, maxWidth: int | None = None, prefixes: list[str] | bool | None = True
) -> list[str]:
    """prefixes=True:  Use the first part of the line up to the first '=' or ':' as a prefix for wrapping
    prefixes=False: Don't use any prefix for wrapping
    prefixes=[list of strings]: Use the first matching prefix from the list for wrapping
    """
    if _txt == "":
        return [""]
    linesIn = _txt.splitlines()

    if maxWidth is None:
        return linesIn
    maxWid_ = maxWidth
    if max([uniLen_approx(line) for line in linesIn], default=0) <= maxWidth:
        return linesIn

    linesOut: list[str] = []
    for txt in linesIn:
        prefixToAppend = ""
        otherPrefixes = ""
        if prefixes == True and (uniLen_approx(txt) > maxWid_):
            n = min([x for x in [txt.find("="), txt.find(":")] if x >= 0], default=-1)
            if n >= 0:
                while n + 1 < len(txt) and txt[n + 1] in [" "]:
                    n += 1
                prefixes = [txt[: n + 1]]

        if isinstance(prefixes, list):
            for prefix in prefixes:
                if txt.startswith(prefix):
                    txt = txt[len(prefix) :]
                    wid = uniLen_approx(prefix)
                    prefixToAppend = prefix
                    otherPrefixes = " " * wid
                    maxWid_ -= wid
                    break

        parts = None if maxWid_ <= 0 else SlashTextWrapper(width=maxWid_).wrap(txt)

        if not parts:
            linesOut.append(prefixToAppend.rstrip() if prefixToAppend else "")
        else:
            linesOut.append(prefixToAppend + parts.pop(0))
            for part in parts:
                linesOut.append(otherPrefixes + part.strip())

    return linesOut


def bulletPoints(msgs: list[str] | str, prefix: str = " • ") -> str:
    theList: list[str] = []
    if isinstance(msgs, str):
        theList = msgs.splitlines()
    else:
        theList = "\n".join(
            msgs
        ).splitlines()  # Ensure we cope with individual lines having newlines!

    txtOut = ""
    for msg in theList:
        if msg.strip() != "":
            txtOut += f"{prefix}{msg.strip()}\n"
    return txtOut
