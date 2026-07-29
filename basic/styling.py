##################################
# Styling
#


import sys, os
from typing import Any, Iterable, Tuple
from importlib.metadata import version


################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import PrettyText, Utils
from ukko_pylibs.basic.logger import appLog
import ukko_pylibs.basic.escapeFormatting as escapeFormatting

g_appColoursAreEnabled = True

g_stylingDisableReason: str = ""


def noteSupport(reason: str | None = None):
    global g_stylingDisableReason

    if reason is not None:
        g_stylingDisableReason = reason
    elif g_stylingDisableReason:
        appLog.print_info(
            f"Styling is not supported in this environment - disabling styling.\n{g_stylingDisableReason}"
        )


def isSupported() -> bool:
    # These are safe, known options that should always work. If this doesn't give different text - styling is not supported in this environment
    output, error = _applyAlways("test", "silent:blue")

    def disableReason(reason: str) -> bool:
        noteSupport(reason)
        doDisable(True)

        return False

    if error:
        # Styling is not supported in this environment due to error
        return disableReason(f"Reason: {error}")
    elif output == "test":
        # Styling is not supported in this environment
        return disableReason(
            "This may be due to running in a non-terminal environment (eg: IDE, Jupyter, etc) or a terminal that does not support ANSI codes."
        )
    else:
        return True


def asStylingRemoved(src: str | list[str] | Any | None) -> str:
    if src is None:
        return ""
    if isinstance(src, str):
        return PrettyText.removeAnsiCodes(src)
    if isinstance(src, list):
        return "\n".join([asStylingRemoved(x) for x in src])
    return PrettyText.removeAnsiCodes(str(src))


# First is always the colour, the rest are attributes (eg: bold, underline, etc)
#
def _applyAlways(text: str, styleTextPlus: str) -> Tuple[str, str | None]:
    isSilent, styleText = Utils.hasRemovedPrefix(styleTextPlus, "silent:")

    x = styleText.split("+")

    colour: str | None = ""
    on_colour: str | None = ""
    attrs: list[str] | None = []

    try:
        import termcolor

        colour = x.pop(0)

        while len(x) > 0:
            attr = x.pop(0)
            if attr.startswith("on_"):
                on_colour = attr
            else:
                attrs.append(attr)

        if version("termcolor").startswith("1."):
            return (
                termcolor.colored(
                    PrettyText.removeAnsiCodes(text),  # < Remove existing styling
                    color=colour or None,
                    on_color=on_colour or None,
                    attrs=attrs or None,
                ),
                None,
            )
        else:
            return (
                termcolor.colored(
                    PrettyText.removeAnsiCodes(text),  # < Remove existing styling
                    color=colour or None,
                    on_color=on_colour or None,
                    attrs=attrs or None,
                    force_color=True,
                ),
                None,
            )

    except Exception as e:
        # Don't use appLog here as appLog may choose to use styling at some point in the future
        if not isSilent:
            print(
                f"⚠️  Unable to style  text: {text} (style:{styleText}) {e}",
                file=sys.stderr,
            )
        return text, str(e)


def isEnabled() -> bool:
    global g_appColoursAreEnabled
    return g_appColoursAreEnabled


# First is always the colour, the rest are attributes (eg: bold, underline, etc)
#
def apply(value: Any | None, styleText: str) -> str:

    if (value == "") or (value is None):
        return ""

    if not styleText or not isEnabled():
        return str(value)

    return _applyAlways(str(value), styleText)[0]


def isStyled(text: str) -> bool:
    return PrettyText.containsAnsiCode(text)


def asSuggestion(value: Any | None) -> str:
    return apply(value, "blue+bold")


def asUnderlinedSuggestion(value: Any | None) -> str:
    return apply(value, "blue+bold+underline")


def asExceptFor(
    value: Any | None,
    styleName: str,
    exceptFor: list[str],
    prefix: str = "{",
    suffix: str = "}",
) -> str:

    txtOut = apply(value, styleName)

    if exceptFor:

        styleOn, styleOff = apply(f"|", styleName).split("|")

        if styleOn != "" or styleOff != "":
            subst: dict[str, str] = {}
            for x in exceptFor:
                subst[x] = styleOff + prefix + x + suffix + styleOn

            txtOut = PrettyText.withSubstitutions(txtOut, subst, prefix, suffix)

    return txtOut


def asSuggestionExceptFor(
    txt: str, exceptFor: list[str], prefix: str = "{", suffix: str = "}"
) -> str:
    return asExceptFor(txt, "blue+bold", exceptFor, prefix, suffix)


def asUnderline(value: Any | None) -> str:
    return apply(value, "+underline")


def asBoldUnderline(value: Any | None) -> str:
    return apply(value, "+underline+bold")


def asBold(value: Any | None) -> str:
    return apply(value, "+bold")


def asExpectedOneOf(entries, butHave):
    return f"Expected one of {asSuggestionList(entries)} but have {asError(butHave)}"


def asSuggestionList(
    values: Iterable[Any], escapeMethod: str = "", separator: str = ", "
) -> str:

    return separator.join(
        [asSuggestion(escapeFormatting.asEscapeMethod(x, escapeMethod)) for x in values]
    )


def asOption(value: Any) -> str:
    if not isinstance(value, str) and isinstance(value, (list, tuple)):
        return "/".join([asOption(x) for x in value])
    else:
        return asBold(escapeFormatting.escapeIfNeeded(str(value)))


def asError(value: Any | None) -> str:
    return apply(value, "red+bold")


def asErrorList(values: list[Any], singularUnit: str = "") -> str:
    if len(values) == 0:
        return asError(PrettyText.pluralize(len(values), singularUnit))
    else:
        return (
            PrettyText.pluralizeName(len(values), singularUnit)
            + ": "
            + ", ".join([asError(str(x)) for x in values])
        )


def doDisable(disable: bool | None) -> bool:
    global g_appColoursAreEnabled

    prevValue = g_appColoursAreEnabled
    if disable:
        g_appColoursAreEnabled = False
    return prevValue != g_appColoursAreEnabled
