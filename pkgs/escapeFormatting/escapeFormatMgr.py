import re
import json

from typing import Any


import ukkoUtils
from appLogging import appLog

################################################################################
#

_VALID_ESCAPE_RE = re.compile(r'\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4})')


def asJsonStr(obj: Any | None) -> str:

    return ukkoUtils.asJsonStr(obj)


def _sanitize_for_json_string(s: str) -> str:
    out = []
    i, n = 0, len(s)
    while i < n:
        ch = s[i]
        if ch == "\\":
            m = _VALID_ESCAPE_RE.match(s, i)
            if m:
                out.append(m.group())  # valid escape, keep as-is
                i = m.end()
            else:
                out.append("\\\\")  # stray backslash -> escape it
                i += 1
        elif ch == '"':
            out.append('\\"')  # unescaped quote -> escape it
            i += 1
        elif ch in ("\n", "\r", "\t"):
            out.append({"\n": "\\n", "\r": "\\r", "\t": "\\t"}[ch])
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def unescape_json_like(txt_param: str) -> str:
    safe = _sanitize_for_json_string(txt_param)
    return json.loads(f'"{safe}"')


def fromEscapedText(value: str) -> str:
    valueOut: str = str(value)
    try:
        valueOut = unescape_json_like(value)
    except Exception as e:
        appLog.print_warning(
            f"Unable to interpret {json.dumps(str(value))} as escaped text: {e}"
        )
    appLog.print_tediousDetail(
        f"Interpreting value as escaped text: '{value}' -> json {json.dumps(valueOut)}"
    )
    return valueOut


def unEscape(value: Any | None, defaultIfNone: Any | None = None) -> Any | None:

    if value is None:
        return defaultIfNone
    elif isinstance(value, str):
        return fromEscapedText(value)
    else:
        return str(value)


def asEscapedText(value: Any) -> str:
    return value.encode("unicode_escape").decode(
        "utf-8"
    )  # json.dumps(value, ensure_ascii=False).removeprefix('"').removesuffix('"').replace('\\"', '"').replace("\\'", "'")


def asEscapeMethod(value: Any, style: str = "none") -> str:
    if style == "escape":
        return escapeIfNeeded(value)
    elif style == "bash":
        return asBashParam(value)
    elif style in ["direct", ""]:
        return str(value)
    else:
        appLog.print_warning(
            "escapeStyle(" + asJsonStr(style) + "): Expected escape,bash,direct,''"
        )
        return str(value)


def escapeIfNeeded(value: Any) -> str:
    x = json.dumps(value, ensure_ascii=False)
    if x.startswith('"') and x.endswith('"') and ((" " in x) or ("\\" in x)):
        return x
    else:
        return x.removeprefix('"').removesuffix('"')


def asOptionallyEscapedText(value: Any, applyEscaping: bool = True) -> Any:
    if applyEscaping and isinstance(value, str):
        return asEscapedText(str(value))
    else:
        return value


def asBashParam(value: Any, name_optional: str = "", withEscaping: bool = True) -> str:
    if value is None:
        return ""
    valueTxt = str(value)
    if withEscaping:
        valueTxt = asEscapedText(valueTxt)
    if name_optional == "":
        resultTxt = ""
    else:
        resultTxt = f"--{name_optional}="

    bashIssues = reviewForBashParams(valueTxt)
    if not bashIssues:
        resultTxt += valueTxt
    elif bashIssues == {"empty"} or not "singleQuotes" in bashIssues:
        resultTxt += f"'{valueTxt}'"
    elif not (bashIssues & {"backticks", "dollarSigns", "doubleQuotes"}):
        resultTxt += f'"{valueTxt}"'

    else:

        resultTxt += "'" + valueTxt.replace("'", "'\\''") + "'"

    appLog.print_tediousDetail(
        f"asBashParam({asJsonStr(value)} -> {resultTxt}) [issues: {bashIssues}]"
    )
    return resultTxt


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

    appLog.print_tediousDetail(
        f"Reviewing value for bash parameters: json:{json.dumps(value)} -> {result}"
    )
    return result
