import json
import os
import sys
from typing import Any

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)


from ukko_pylibs.basic import fileUtils
from ukko_pylibs.basic.simpleUtils import PrettyText
from ukko_pylibs.basic.class_HandledException import HandledException
import ukko_pylibs.basic.escapeFormatting as escapeFormatting

#
################################################################################


def _asProvidedToFname(asProvided: str) -> str | None:
    """Returns filename -or- None"""
    txt = asProvided.strip()
    prefixes = ["file:", "@"]
    for prefix in prefixes:
        if txt.startswith(prefix):
            return txt.removeprefix(prefix)
    return None


class JsonDict:
    def __init__(
        self,
        value: str,
        formatIn: str | None = None,
        fname_provided: str = "",
    ):
        self.contents: dict = {}
        self.asProvided: str = value.strip()

        self.formatIn: str = "JSON" if not formatIn else formatIn
        self.fname_provided = fname_provided
        self.jsonText = ""

        self._doLoadExtendedData()  # < Can modify .interpretAs & .format

    def asTrimmed(self) -> str:
        if self.fname_provided:
            return f"Contents of '{self.fname_provided}'"
        else:
            return PrettyText.asClipped(
                escapeFormatting.asEscapeMethod(self.fname_provided, "bash")
            )

    def _doLoadExtendedData(self):
        fname = _asProvidedToFname(self.asProvided)
        if fname is not None:
            self.jsonText = fileUtils.loadTextFromFile_orHandledException(
                fname, self.formatIn
            )
        else:
            self.jsonText = self.asProvided

        try:
            import json5

            params = json5.loads(self.jsonText)
            if isinstance(params, dict):
                self.contents = params
            else:
                raise HandledException(
                    f"Parsed {self.asTrimmed()} into a non-dictionary type: {type(params)}"
                )
        except Exception as e:
            raise HandledException(f"Unable to parse: {self.asTrimmed()} ({e})")

    def asParamTxt(self) -> str:
        return self.asProvided

    def asDict(self) -> dict[str, Any]:
        out = {
            "asProvided": self.asProvided,
            "contents": self.contents,
            "format": self.formatIn,
        }

        if self.fname_provided:
            out["filename"] = self.fname_provided

        return out
