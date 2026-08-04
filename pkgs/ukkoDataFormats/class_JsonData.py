from typing import Any


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
            import prettyText, escapeFormatting

            return prettyText.asClipped(
                escapeFormatting.asEscapeMethod(self.fname_provided, "bash")
            )

    def _doLoadExtendedData(self):
        from ukkoUtils import HandledException
        from fileUtils import loadTextFromFile_orHandledException

        fname = _asProvidedToFname(self.asProvided)
        if fname is not None:
            self.jsonText = loadTextFromFile_orHandledException(fname, self.formatIn)
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
