##################################
# Styling
#


import sys, os
from typing import Any, Tuple


################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import PrettyText, EscapeMgr, Utils
from ukko_pylibs.basic.logger import appLog

g_appColoursAreEnabled = True


def isSupported() -> bool:
    # These are safe, known options that should always work. If this doesn't give different text - styling is not supported in this environment
    output, error = _applyAlways("test", "silent:blue")

    def disableReason(reason: str) -> bool:
        appLog.print_info(
            f"Styling is not supported in this environment - disabling styling.\n{reason}"
        )
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


# First is always the colour, the rest are attributes (eg: bold, underline, etc)
#
def _applyAlways(text: str, styleText: str) -> Tuple[str, str | None]:
    isSilent, styleText = Utils.removePrefix(styleText, "silent:")

    x = styleText.split("+")

    color: str | None = ""
    on_color: str | None = ""
    attrs: list[str] | None = []

    try:
        import termcolor

        color = x.pop(0)

        while len(x) > 0:
            attr = x.pop(0)
            if attr.startswith("on_"):
                on_color = attr
            else:
                attrs.append(attr)

        return (
            termcolor.colored(
                PrettyText.removeAnsiCodes(text),  # < Remove existing styling
                color=color or None,
                on_color=on_color or None,
                attrs=attrs or None,
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

    if not value:
        return ""

    return _applyAlways(str(value), styleText)[0] if isEnabled() else str(value)


def asSuggestion(value: Any | None) -> str:
    return apply(value, "blue+bold")


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


def asSuggestionList(values: list[Any], quoteIfNeeded: bool = False) -> str:

    if quoteIfNeeded:
        return ", ".join(
            [asSuggestion(EscapeMgr.escapeIfNeeded(str(x))) for x in values]
        )
    else:
        return ", ".join([asSuggestion(str(x)) for x in values])


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


def doDisable(disable: bool | None):
    global g_appColoursAreEnabled
    if disable:
        g_appColoursAreEnabled = False
