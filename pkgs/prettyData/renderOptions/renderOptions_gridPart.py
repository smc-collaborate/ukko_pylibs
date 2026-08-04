from typing import Any, Union


################################################################################


class RenderOptions_GridPart:
    """Options to Render a PrettyTable column or cell
    Note that all widths are 'visual widths' - which can include wider icons, remove ANSI codes etc
    """

    def __init__(
        self,
        lockedMaxVisWidth: int | None = None,
        prefixesToWrapWith: (
            list[str] | bool | None
        ) = True,  # < True = Auto  Anything before *=
        isWrap: bool = True,
        styleAndColour: str = "",
    ):
        self.lockedMaxVisWidth: int | None = (
            lockedMaxVisWidth  # < None = Auto-calculate
        )
        self.isWrap = isWrap  # < Wrap on visual Width
        self._calcWidth: list[int] | None = None
        self.prefixesToWrapWith = prefixesToWrapWith
        self.styleAndColour = styleAndColour

    def export_toJsonDict(self) -> dict[str, Any]:
        obj: dict[str, Any] = {}

        if self.lockedMaxVisWidth is None:
            obj = {
                "skip": {
                    "isWrap": self.isWrap,
                    "prefixesToWrapWith": self.prefixesToWrapWith,
                }
            }
        else:
            obj = {
                "lockedMaxWidth": self.lockedMaxVisWidth,
                "isWrap": self.isWrap,
                "prefixesToWrapWith": self.prefixesToWrapWith,
            }

        return obj

    def asDict(self) -> dict[str, Any]:
        result = self.export_toJsonDict()
        if self._calcWidth:
            result["_calcWidth"] = self._calcWidth
        return result

    @staticmethod
    def create_fromJsonDict(spec: dict) -> "RenderOptions_GridPart":
        if isinstance(spec, dict):
            _lockedMaxVisWidth = spec.get("lockedMaxWidth", None)
            _isWrap = spec.get("isWrap", True)
            _prefixesToWrapWith = spec.get("prefixesToWrapWith", None)

            return RenderOptions_GridPart(
                _lockedMaxVisWidth, _prefixesToWrapWith, _isWrap
            )
        else:
            raise TypeError(
                f"RenderOptions_GridPart.create_fromJsonDict(): Cannot import type {type(spec)}"
            )

    @staticmethod
    def createOrNone_fromJsonDictOrNone(
        spec: dict | None,
    ) -> Union["RenderOptions_GridPart", None]:
        if spec is None:
            return None
        else:
            return RenderOptions_GridPart.create_fromJsonDict(spec)


class RenderDecisions_GridPart:
    def __init__(
        self, customisableOptions: RenderOptions_GridPart | None, currentWidth: int
    ):
        self.customisableOptions = customisableOptions
        self.currentWidth = currentWidth

    def asDict(self) -> dict[str, Any]:
        return {
            "options": (
                None
                if self.customisableOptions is None
                else self.customisableOptions.export_toJsonDict()
            ),
            "width": self.currentWidth,
        }
