from copy import deepcopy
from typing import Any, Union


import ukkoUtils


from .renderOptions_gridPart import RenderOptions_GridPart
from .renderOptions_columns import RenderOptions_Columns
from .borders import Borders

################################################################################


class RenderOptions_Table:
    """Options to Render a PrettyTable
    Only access these values with:
       .getRenderOption(colNum=13,rowDescription='title') -> RenderOptions_GridPart|None
       .getMaxVisWidth(colNum=13) -> int | None
    """

    Columns = RenderOptions_Columns

    def __init__(
        self,
        # border: Borders | dict | str | None = None,
        # colOptions: RenderOptions_Columns | str | dict | list | None = None,
        specIn: dict[str, Any | None] | str | None = None,
    ):
        """Options include:
        * borders
        * colOptions
        * rowStyling
        """
        self.rowStyling: dict[str, str]
        self.border: Borders
        self.colOptions_: RenderOptions_Columns
        self.specFull: dict[str, Any | None]

        if specIn is None:
            self.specFull = {}
        elif isinstance(specIn, str):
            self.specFull = (
                ukkoUtils.dictFromJsonLikeStr(
                    specIn,
                    "Unable to interprete PrettyData.RenderOption_Table spec",
                    None,
                )
                or {}
            )
        else:
            self.specFull = specIn

        border_src = self.specFull.get("borders")
        colOptions_src = self.specFull.get("colOptions")

        self.rowStyling = (
            self.specFull.get("rowStyling") or {}
        )  # < eg: ['title']='red+bold'

        if isinstance(border_src, Borders):
            self.border = border_src
        else:
            self.border = Borders.createFrom_dict(border_src)

        if isinstance(colOptions_src, RenderOptions_Columns):
            self.colOptions_ = colOptions_src
        else:
            self.colOptions_ = (
                RenderOptions_Columns.createOrNone_fromJsonDictOrNone(colOptions_src)
                or RenderOptions_Columns()
            )

    def _getRowStyling(self, rowDescription: str | None) -> str:
        """eg: getRowStyling('title')-> 'red+bold'"""
        if not rowDescription:
            return ""
        return str(self.rowStyling.get(rowDescription, ""))

    def getRenderOption(
        self, colNum: int, rowDescription: str | None
    ) -> RenderOptions_GridPart | None:
        """eg: getRenderOption(13,'title')"""
        rowStyle = self._getRowStyling(rowDescription)
        result: RenderOptions_GridPart | None = self.colOptions_.get(colNum)
        if rowStyle != "":
            result = deepcopy(result) or RenderOptions_GridPart()
            result.styleAndColour = rowStyle
            # |x| print(f"rowDescription[{rowDescription}]->{rowStyle}")
        return result

    def getMaxVisWidth(self, colNum: int) -> int | None:
        if colNum not in self.colOptions_:
            return None
        elif not self.colOptions_[colNum]:
            return None
        else:
            return self.colOptions_[colNum].lockedMaxVisWidth

    def get(self, name: str) -> Any | None:
        return self.specFull.get(name)

    @staticmethod
    def createOrNone_fromJsonDictOrNone(
        spec: dict | None,
    ) -> Union["RenderOptions_Table", None]:
        if spec is None:
            return None

        result = RenderOptions_Table(spec)

        return result

    @staticmethod
    def create_fromLockedVisWidths(
        lockedMaxVisWidths: list[int | None],
    ) -> "RenderOptions_Table":
        result = RenderOptions_Table()
        for colNum, wid in enumerate(lockedMaxVisWidths):
            if wid is not None:
                result.colOptions_[colNum] = RenderOptions_GridPart(
                    lockedMaxVisWidth=wid
                )
        return result
