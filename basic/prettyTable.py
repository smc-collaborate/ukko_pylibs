import os
import sys

from typing import Any, Callable, Self, Tuple, Union

import numpy as np
from pathlib import Path

################################################################################
#
# Add project root directory to system path


shared_dir = os.path.abspath(f"{Path(__file__).parent}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.class_JsonData import JsonDict
from ukko_pylibs.basic.logger import appLog
from ukko_pylibs.basic.simpleUtils import (
    PrettyText,
    Utils,
    NameValuePair,
    NameValuePairList,
)
from ukko_pylibs.basic.sparseLists import SparseList, Sparse2D


################################################################################
#
class MaxWidths:
    def __init__(self):
        self.data = SparseList[int](0)

    def __getitem__(self, pos: int) -> int:
        return self.data.get(pos, 0)

    def getLen(self):
        return self.data.getLen(includingBlanks=True)

    def items(self):
        return self.data.items()

    def includeVal(self, colNum: int, width: int):
        self.data[colNum] = max(self.data.getOrEmpty(colNum), width)

    def includeWidths_list_str(
        self, src: list[str | None], skipIfColIsEmpty: bool = False
    ):

        self.includeWidths_SparseList(
            SparseList[str].create_fromList_andBlank(src, ""), skipIfColIsEmpty
        )

    def includeWidths_SparseList(
        self, src: SparseList[str], skipIfColIsEmpty: bool = False
    ):
        for colNum, colText in src.items():
            if not skipIfColIsEmpty or self.data.getOrEmpty(colNum) > 0:
                self.includeVal(colNum, PrettyText.uniLen_approx(colText))


PrettyCellContents = str

PrettyTable_RowList = list[PrettyCellContents | None]


class PrettyTable_Row:
    def __init__(
        self, src: SparseList[PrettyCellContents] | PrettyTable_RowList | None = None
    ):
        if isinstance(src, SparseList):
            self.data = SparseList[PrettyCellContents](PrettyCellContents(), src)
        elif isinstance(src, list):
            self.data = SparseList[PrettyCellContents].create_fromListOrNone_andBlank(
                src, PrettyCellContents()
            )
        else:
            self.data = SparseList[PrettyCellContents](PrettyCellContents())

    def hasData(self) -> bool:
        return self.data.hasData()

    def getOrEmpty(self, pos: int) -> PrettyCellContents:
        return self.data.getOrEmpty(pos)

    def setEntry(self, entry: PrettyCellContents, position: int | None = None):
        self.data.setEntry(entry, position)

    @staticmethod
    def create_fromJsonDict(spec: dict | list) -> "PrettyTable_Row":
        return PrettyTable_Row(
            SparseList[PrettyCellContents].create_fromJsonDict_andBlank(
                spec, PrettyCellContents()
            )
        )

    @staticmethod
    def createOrNone_fromJsonDictOrNone(
        spec: dict | list | None,
    ) -> Union["PrettyTable_Row", None]:
        return (
            None
            if spec is None
            else PrettyTable_Row(
                SparseList[PrettyCellContents].create_fromJsonDict_andBlank(
                    spec, PrettyCellContents()
                )
            )
        )

    @staticmethod
    def create_fromList(spec: list) -> "PrettyTable_Row":
        return PrettyTable_Row(
            SparseList[PrettyCellContents].create_fromList_andBlank(
                spec, PrettyCellContents()
            )
        )


class PrettyTable_Contents:
    def __init__(self, titles: PrettyTable_RowList | None = None):
        self.colTitles = PrettyTable_Row(titles)
        self.contentsGrid = Sparse2D[PrettyCellContents](PrettyCellContents())

    def asDict(self) -> dict[str, Any]:
        return {"colTitle": self.colTitles, "contentsGrid": self.contentsGrid}

    def rows(self) -> SparseList[SparseList[PrettyCellContents]]:
        return self.contentsGrid.rows

    def appendRowList(self, row: PrettyTable_RowList | None):
        if row is not None:
            self.contentsGrid.appendRow(PrettyTable_Row(row).data)

    def appendRow_namePairList(self, pairsIn: NameValuePairList | None):
        if pairsIn is None:
            return

        rowOut = SparseList[str]("")

        def getColNum(title: str):
            for (
                colNum,
                titleFound,
            ) in (
                self.colTitles.data.items()
            ):  # @todo: Can be made more efficient by having a second index by value..
                if titleFound == title:
                    return colNum

            return self.colTitles.data.append(title)

        for name, value in pairsIn:
            if value is not None:
                rowOut[getColNum(name)] = str(value)
        self.contentsGrid.appendRow(rowOut)

    def appendRow(
        self,
        row: (
            PrettyTable_Row
            | SparseList[PrettyCellContents]
            | list[PrettyCellContents | None]
            | None
        ),
    ):
        if row is not None:
            if isinstance(row, PrettyTable_Row):
                self.contentsGrid.appendRow(row.data)
            elif isinstance(row, list):
                self.contentsGrid.appendRow(PrettyTable_Row(row).data)
            else:
                self.contentsGrid.appendRow(row)

    def appendTable(
        self, addThis: "PrettyTable_Contents", withSeparatingBlankLine: bool = True
    ):
        if not addThis.hasData():
            return

        if self.hasData() and withSeparatingBlankLine:
            self.appendRowBlank()
        if addThis.colTitles.hasData():
            wids: MaxWidths = addThis.getGridMaxWidths()
            newTitles = PrettyTable_Row()
            for col, wid in wids.items():
                if wid > 0:
                    title = addThis.colTitles.getOrEmpty(col)
                    if title:
                        newTitles.setEntry(title, col)

            if newTitles.hasData():
                self.appendRow(newTitles)

        for row in addThis.rows().values():
            self.appendRow(row)

    def appendRowBlank(self):
        self.contentsGrid.appendRow(PrettyTable_Row().data)

    def appendColList(self, col: list[PrettyCellContents | None] | None):
        if col is not None:
            self.contentsGrid.appendCol(
                SparseList[PrettyCellContents].create_fromList_andBlank(
                    col, PrettyCellContents()
                )
            )

    def hasData(self) -> bool:
        return self.contentsGrid.hasData()

    def getGridMaxWidths(self):
        maxWidths_calc = MaxWidths()

        for row in self.contentsGrid.rows.values():
            maxWidths_calc.includeWidths_SparseList(row)

        return maxWidths_calc

    def getMaxWidths(self) -> MaxWidths:

        maxWidths_calc = self.getGridMaxWidths()
        maxWidths_calc.includeWidths_SparseList(
            self.colTitles.data, skipIfColIsEmpty=True
        )
        return maxWidths_calc

    @staticmethod
    def create_fromJsonDict(spec: dict) -> "PrettyTable_Contents":
        _titles = spec.get("titles")
        _rows = spec.get("rows")

        table = PrettyTable_Contents(
            PrettyTable_RowList(_titles) if _titles is not None else None
        )
        if isinstance(_rows, dict):
            raise NotImplementedError(
                f"PrettyTable.import[_rows]: import of {type(_rows)} not implemented yet"
            )

        if isinstance(_rows, list):
            for rowSpec in _rows:
                if not isinstance(rowSpec, list):
                    raise NotImplementedError(
                        f"PrettyTable.import[_row]: import of {type(rowSpec)} not implemented yet"
                    )
                table.appendRowList(
                    PrettyTable_RowList(rowSpec) if rowSpec is not None else None
                )

        return table

    @staticmethod
    def create_fromValuePairs(
        nameValuePairRows: list[NameValuePairList],
    ) -> "PrettyTable_Contents":

        result = PrettyTable_Contents()

        for row in nameValuePairRows:
            result.appendRow_namePairList(row)

        return result

    @staticmethod
    def createFrom_dict(
        src: dict, keyTitle: str | None, option_multiLineValues: bool = True
    ) -> "PrettyTable_Contents":

        result = PrettyTable_Contents()

        for key, value in src.items():

            nameValues = NameValuePairList()

            if keyTitle is None:
                nameValues.append(("Name", key))

                if option_multiLineValues and isinstance(value, dict):

                    lines: list[str] = []
                    keyLen = max(
                        [len(key2) for key2 in value if value is not None], default=0
                    )

                    for key2, value2 in value.items():
                        if value2 is not None:
                            lines.append(f"{key2:<{keyLen}} : {Utils.asStr(value2)}")
                    nameValues.append(("Value", "\n".join(lines)))
                else:
                    nameValues.append(("Value", Utils.asStr(value)))
            elif isinstance(value, dict):
                nameValues.append((keyTitle, key))
                for key2, value2 in value.items():
                    if value2 is not None:
                        nameValues.append((key2, Utils.asStr(value2)))
            else:
                nameValues.append((keyTitle, Utils.asStr(value)))

            result.appendRow_namePairList(nameValues)

        return result

    def renderAs(
        self, options: Union["RenderOptions_Table", str | None] = None
    ) -> "PrettyTable_Rendered":

        optionsToUse = RenderOptions_Table | None
        if not isinstance(options, str):
            optionsToUse = options
        else:
            optionsToUse = RenderOptions_Table(
                Borders.createOrNoneFrom_name(options), None
            )

        return PrettyTable_Rendered(self, optionsToUse)


class RenderOptions_SingleCol:
    """Options to Render a PrettyTable column
    Note that all widths are 'visual widths' - which can include wider icons, remove ANSI codes etc
    """

    def __init__(
        self,
        lockedMaxVisWidth: int | None = None,
        prefixesToWrapWith: (
            list[str] | bool | None
        ) = True,  # < True = Auto  Anything before *=
        isWrap: bool = True,
    ):
        self.lockedMaxVisWidth: int | None = (
            lockedMaxVisWidth  # < None = Auto-calculate
        )
        self.isWrap = isWrap  # < Wrap on visual Width
        self._calcWidth: list[int] | None = None
        self.prefixesToWrapWith = prefixesToWrapWith

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
    def create_fromJsonDict(spec: dict) -> "RenderOptions_SingleCol":
        if isinstance(spec, dict):
            _lockedMaxVisWidth = spec.get("lockedMaxWidth", None)
            _isWrap = spec.get("isWrap", True)
            _prefixesToWrapWith = spec.get("prefixesToWrapWith", None)

            return RenderOptions_SingleCol(
                _lockedMaxVisWidth, _prefixesToWrapWith, _isWrap
            )
        else:
            raise TypeError(
                f"RenderOptions_SingleCol.create_fromJsonDict(): Cannot import type {type(spec)}"
            )

    @staticmethod
    def createOrNone_fromJsonDictOrNone(
        spec: dict | None,
    ) -> Union["RenderOptions_SingleCol", None]:
        if spec is None:
            return None
        else:
            return RenderOptions_SingleCol.create_fromJsonDict(spec)


class RenderOptions_Columns(SparseList[RenderOptions_SingleCol]):

    def __init__(
        self,
        objSrc: Union[
            "RenderOptions_Columns", SparseList[RenderOptions_SingleCol], None
        ] = None,
    ):
        super().__init__(RenderOptions_SingleCol(), objSrc)

    @staticmethod
    def create_fromJsonDictOrNone(spec: dict | list | None) -> "RenderOptions_Columns":
        return RenderOptions_Columns(
            RenderOptions_Columns.create_fromJsonDictOrNone_andBlank(
                spec, RenderOptions_SingleCol()
            )
        )

    @staticmethod
    def createOrNone_fromJsonDictOrNone(
        spec: dict | list | None,
    ) -> Union["RenderOptions_Columns", None]:
        if spec is None:
            return None
        return RenderOptions_Columns(
            RenderOptions_Columns.create_fromJsonDict_andBlank(
                spec, RenderOptions_SingleCol()
            )
        )

    @staticmethod
    def create_fromList(spec: list) -> "RenderOptions_Columns":
        return RenderOptions_Columns(
            RenderOptions_Columns.create_fromList_andBlank(
                spec, RenderOptions_SingleCol()
            )
        )

    @staticmethod
    def createOrNone_fromListOrNone(
        spec: list | None,
    ) -> Union["RenderOptions_Columns", None]:
        return None if spec is None else RenderOptions_Columns.create_fromList(spec)


class Borders:
    #                                   0...4...8...12..16..20..24
    # | eg:            top___________= "┏━━━┳━━━┳━━━┯━━━┳━━━┳━━━┓",
    # | eg:            title_________= "┃ A ┃ B ┃ C │ D ┃ E ┃ F ┃",
    # | eg:            undTopTitle___= "┣━━━╋━━━╋━━━┿━━━╋━━━╋━━━┫",
    # | eg:            entry_1_______= "┃ A ┃ B ┃ n │ n ┃ E ┃ F ┃",
    # | eg:            betweenEntries= "┠───╂───╂───┼───╂───╂───┨",
    # | eg:            entry_2_______= "┃ A ┃ B ┃ n │ n ┃ E ┃ F ┃",
    # | eg:            overBotTitle__= "┣━━━╋━━━╋━━━┿━━━╋━━━╋━━━┫",
    # | eg:            title_________= "┃ A ┃ B ┃ C │ D ┃ E ┃ F ┃",
    # | eg:            bottom________= "┗━━━┻━━━┻━━━┷━━━┻━━━┻━━━┛")

    class RowBorders:

        def __init__(
            self,
            blankEquiv: str,
            middleDiv: str,
            leftLimit: str = "",
            leftTitleMiddle: str = "",
            leftTitleEdge: str = "",
            rightTitleEdge: str = "",
            rightTitleMiddle: str = "",
            rightLimit: str = "",
        ):
            self.blankEquiv = blankEquiv
            self.midDiv = middleDiv

            self.leftLimit = leftLimit
            self.leftTitleMiddle = leftTitleMiddle
            self.leftTitleEdge = leftTitleEdge
            self.rightTitleEdge = rightTitleEdge
            self.rightTitleMiddle = rightTitleMiddle
            self.rightLimit = rightLimit

    @staticmethod
    def createRowBordersFrom_div(divider: str | None = None) -> RowBorders:
        return Borders.RowBorders(" ", " " if divider is None else divider)

    @staticmethod
    def createRowBordersFrom_template(
        paddingCount: int, template: str = ""
    ) -> RowBorders | None:

        if template == "":
            return None

        # isEmpty=(template=='')

        if len(template) != 25:  # not isEmpty and len(template)!=25:
            appLog.print_warning(
                f"RowBorders.createFrom_template(): Expecting template of length 25: '{template}'"
            )
            return None

        # if isEmpty:
        #    paddingText=' '*paddingCount
        #    return Borders.RowBorders(' ',paddingText+'│'+paddingText)
        # else:

        blankEquiv = template[1]

        leftLimit = template[0]
        leftTitleMiddle = template[4]
        leftTitleEdge = template[8]
        midDiv = template[12]
        rightTitleEdge = template[16]
        rightTitleMiddle = template[20]
        rightLimit = template[24]

        paddingText = blankEquiv * paddingCount

        return Borders.RowBorders(
            blankEquiv,
            paddingText + midDiv + paddingText,
            leftLimit + paddingText,
            paddingText + leftTitleMiddle + paddingText,
            paddingText + leftTitleEdge + paddingText,
            paddingText + rightTitleEdge + paddingText,
            paddingText + rightTitleMiddle + paddingText,
            paddingText + rightLimit,
        )

    def __init__(self):
        self.rowBorders: dict[str, Borders.RowBorders] = {}

    def get(self, name: str) -> Union["Borders.RowBorders", None]:
        result = self.rowBorders.get(name.strip("_ \t"))
        # |x| print(f"!!! Borders.get({Utils.asJsonStr(name)}) in {Utils.asJsonStr(list(self.rowBorders.keys()))}={result}")

        return result

    def set(self, name: str | list[str], entry: RowBorders | None):
        if entry:
            for singleName in [name] if isinstance(name, str) else name:
                self.rowBorders[singleName.strip("_")] = entry

    @staticmethod
    def createOrNoneFrom_name(name: str) -> Union["Borders", None]:

        standard_borders: dict[str, Borders] = {
            "outer+vert": Borders.createFrom_template(
                1,
                top___________="┏━━━┳━━━┳━━━┯━━━┳━━━┳━━━┓",
                title_________="┃ A ┃ B ┃ C │ D ┃ E ┃ F ┃",
                undTopTitle___="┣━━━╋━━━╋━━━┿━━━╋━━━╋━━━┫",
                entry_1_______="┃ A ┃ B ┃ n │ n ┃ E ┃ F ┃",
                betweenEntries="",  # "┠───╂───╂───┼───╂───╂───┨",
                entry_2_______="┃ A ┃ B ┃ n │ n ┃ E ┃ F ┃",
                overBotTitle__="┣━━━╋━━━╋━━━┿━━━╋━━━╋━━━┫",
                bottom________="┗━━━┻━━━┻━━━┷━━━┻━━━┻━━━┛",
            ),
            "blank": Borders.createFrom_divider(" "),
            "|": Borders.createFrom_divider(" │ "),
        }
        if name in standard_borders:
            return standard_borders[name]
        else:
            appLog.print_warning(
                f"Borders.createOrNoneFrom_name({name}) ignored.  Only valid entries are {Utils.asJsonStr(list(standard_borders.keys()))}"
            )
            return None

    @staticmethod
    def createFrom_template(
        paddingCount: int,
        top___________: str,
        title_________: str,
        undTopTitle___: str,
        entry_1_______: str,
        betweenEntries: str,
        entry_2_______: str,
        overBotTitle__: str,
        bottom________: str,
    ) -> "Borders":
        result = Borders()

        result.set(
            "top",
            Borders.createRowBordersFrom_template(paddingCount, top___________),
        )
        result.set(
            "title",
            Borders.createRowBordersFrom_template(paddingCount, title_________),
        )
        result.set(
            "undTopTitle",
            Borders.createRowBordersFrom_template(paddingCount, undTopTitle___),
        )
        result.set(
            "entry",
            Borders.createRowBordersFrom_template(paddingCount, entry_1_______),
        )
        result.set(
            "betweenEntries",
            Borders.createRowBordersFrom_template(paddingCount, betweenEntries),
        )
        result.set(
            "overBotTitle",
            Borders.createRowBordersFrom_template(paddingCount, overBotTitle__),
        )
        result.set(
            "bottom",
            Borders.createRowBordersFrom_template(paddingCount, bottom________),
        )
        return result

    @staticmethod
    def createFrom_divider(divider: str | None) -> "Borders":
        result = Borders()
        result.set(["entry", "title"], Borders.createRowBordersFrom_div(divider))
        return result

    @staticmethod
    def createFrom_dict(src: dict[str, Any] | str | Any | None) -> "Borders":

        if type(src) is str:
            result = Borders.createOrNoneFrom_name(src)
            if result is not None:
                return result
        if type(src) is dict:

            if "divider" in src:
                return Borders.createFrom_divider(src["divider"])

            if "template" in src:
                template: dict[str, Any] = src["template"]
                return Borders.createFrom_template(
                    template.get("paddingCount", 0),
                    template.get("top___________", ""),
                    template.get("title_________", ""),
                    template.get("undTopTitle___", ""),
                    template.get("entry_________", ""),
                    template.get("betweenEntries", ""),
                    "",
                    template.get("overBotTitle__", ""),
                    template.get("bottom________", ""),
                )
        return Borders.createFrom_divider(" ")


class RenderOptions_Table:
    """Options to Render a PrettyTable"""

    def __init__(
        self,
        border: Borders | str | None = None,
        colOptions: RenderOptions_Columns | None = None,
    ):
        if isinstance(border, Borders):
            self.border = border
        else:
            self.border = Borders.createFrom_divider(border)
        self.colOptions = RenderOptions_Columns() if colOptions is None else colOptions

    @staticmethod
    def createOrNone_fromJsonDictOrNone(
        spec: dict | None,
    ) -> Union["RenderOptions_Table", None]:
        if spec is None:
            return None

        _colOptions = RenderOptions_Columns.createOrNone_fromJsonDictOrNone(
            spec.get("colOptions")
        )

        result = RenderOptions_Table(
            Borders.createFrom_dict(spec.get("borders")), _colOptions
        )

        return result

    @staticmethod
    def create_fromLockedVisWidths(
        lockedMaxVisWidths: list[int | None],
    ) -> "RenderOptions_Table":
        result = RenderOptions_Table()
        for colNum, wid in enumerate(lockedMaxVisWidths):
            if wid is not None:
                result.colOptions[colNum] = RenderOptions_SingleCol(
                    lockedMaxVisWidth=wid
                )
        return result

    def getMaxVisWidth(self, colNum: int) -> int | None:
        if colNum not in self.colOptions:
            return None
        elif not self.colOptions[colNum]:
            return None
        else:
            return self.colOptions[colNum].lockedMaxVisWidth


class PrettyTable_Rendered:
    def __init__(
        self,
        tableSrc: PrettyTable_Contents,
        renderOptions: RenderOptions_Table | list[int | None] | None = None,
    ):
        self.in_table = tableSrc

        if renderOptions is None:
            self.renderOptions = RenderOptions_Table()
        elif isinstance(renderOptions, RenderOptions_Table):
            self.renderOptions = renderOptions
        else:
            self.renderOptions = RenderOptions_Table.create_fromLockedVisWidths(
                renderOptions
            )

        self.out_lines: list[str] = self.doBuild()

    def asTextLines(self) -> list[str]:
        return self.out_lines

    def doBuild(self) -> list[str]:

        self.proc_visWidths_calc: MaxWidths = (
            self.in_table.getMaxWidths()
        )  # < Before clipping, wrapping etc.
        self.proc_visWidths_used: list[int] = []
        for colNum in range(self.proc_visWidths_calc.getLen()):
            maxVisWidth = self.renderOptions.getMaxVisWidth(colNum)
            calc = self.proc_visWidths_calc[colNum]
            used = calc
            if maxVisWidth is not None:
                if maxVisWidth < used:
                    used = maxVisWidth
            self.proc_visWidths_used.append(used)

        def row_asTextLines(
            row: SparseList[PrettyCellContents] | PrettyTable_Row | None,
            borderStyleSource: str,
        ) -> list[str]:

            if row is None:
                return []

            class CellInfo:
                def __init__(
                    self,
                    srcText: str,
                    styleWidth: int = 20,
                    stylingOption: RenderOptions_SingleCol | None = None,
                ):
                    self.lines: list[str] = PrettyText.textWrapWithPrefixes(
                        srcText,
                        styleWidth,
                        (
                            False
                            if stylingOption is None
                            else stylingOption.prefixesToWrapWith
                        ),
                    )
                    self.width: int = styleWidth

                def height(self) -> int:
                    return len(self.lines)

                def getRowText(self, rowNum: int) -> str:
                    # @todo: Fix wrapping styling ?
                    txt = self.lines[rowNum] if rowNum in range(len(self.lines)) else ""

                    return PrettyText.padToWidth(txt, self.width)

            cellsInRow: list[CellInfo] = []
            for colNum in range(len(self.proc_visWidths_used)):

                wid = self.proc_visWidths_used[colNum]
                if wid > 0:
                    cellsInRow.append(
                        CellInfo(
                            row.getOrEmpty(colNum),
                            wid,
                            self.renderOptions.colOptions.get(colNum),
                        )
                    )

            if not cellsInRow:
                return []

            rowHeight = max([cell.height() for cell in cellsInRow])
            linesOut: list[str] = []

            if rowHeight:

                rowBorders = self.renderOptions.border.get(borderStyleSource)

                leftBorder = "" if rowBorders is None else rowBorders.leftLimit
                midDiv = " " if rowBorders is None else rowBorders.midDiv
                rightBorder = "" if rowBorders is None else rowBorders.rightLimit

                for n in range(rowHeight):
                    linesOut.append(
                        leftBorder
                        + midDiv.join([cell.getRowText(n) for cell in cellsInRow])
                        + rightBorder
                    )

            return linesOut

        def dividerAsTextLines(kind: str) -> list[str]:

            src = self.renderOptions.border.get(kind)
            if not src:
                return []

            return [
                line.replace(" ", src.blankEquiv)
                for line in row_asTextLines(SparseList[str](""), kind)
            ]

        lines: list[str] = []

        # | Box characters| ─	━	┄	┅   ┈	┉	╌	╍	═	╼	╾   ╸	╺	╴	╶
        # | Box characters|
        # | Box characters| │	┃	┆	┇	┊	┋	╎	╏   ║	╽	╿   ╻   ╹	╵	╷
        # | Box characters|
        # | Box characters| ┌	┍	┎	┏   ╒	╓   ╔   ╭
        # | Box characters| ┐	┑	┒	┓	╕	╖	╗	╮
        # | Box characters|
        # | Box characters| └	┕	┖	┗	╘	╙	╚	╰
        # | Box characters| ┘	┙	┚	┛	╛	╜	╝   ╯
        # | Box characters| ├	┝	┞	┟   ┠	┡	┢	┣	╟   ╠   ╞
        # | Box characters| ┤	┥	┦	┧	┨	┩	┪	┫	╢	╣   ╡
        # | Box characters| ┬	┭	┮   ┯   ┰	┱	┲	┳	╤	╥	╦
        # | Box characters|
        # | Box characters| ┴	┵	┶	┷	┸	┹	┺	┻	╧	╨	╩
        # | Box characters|
        # | Box characters| ┼	┽	┾	┿   ╀	╁	╂	╃	╪	╫	╬
        # | Box characters|
        # | Box characters| ╄	╅	╆	╇	╈	╉	╊	╋
        # | Box characters|
        # | Box characters| ╱   ╲   ╳
        # | Box characters|

        #
        # Top:           ╭───────────┬────────────┬─────────────┬────────────╮
        # TopTitleBlock: │           │            │             │            │
        # TopTitleBlock: │           │            │             │            │
        # UnderTitle:    ├───────────┼────────────┼─────────────┼────────────┤
        # Entry          │           │            │             │            │
        # Entry          │           │            │             │            │
        # UnderEntry     ├───────────┼────────────┼─────────────┼────────────┤
        # Entry          │           │            │             │            │
        # Entry          │           │            │             │            │
        # UnderEntry     ├───────────┼────────────┼─────────────┼────────────┤
        # Entry          │           │            │             │            │
        # Entry          │           │            │             │            │
        # Bottom:        ╰───────────┴────────────┴─────────────┴────────────╯
        #

        # |Other|            borders=Borders(len(self.renderOptions.colDivPre)-1,
        # |Other|                            top___________= "┌───┬───┬───┬───┬───┬───┐",
        # |Other|                            title_________= "│ A │ B │ C │ D │ E │ F │",
        # |Other|                            undTopTitle___= "├───┼───┼───┼───┼───┼───┤",
        # |Other|                            entry_1_______= "│ A │ B │ n │ n │ E │ F │",
        # |Other|                            betweenEntries= "├───┼───┼───┼───┼───┼───┤",
        # |Other|                            entry_2_______= "│ A │ B │ n │ n │ E │ F │",
        # |Other|                            overBotTitle__= "├───┼───┼───┼───┼───┼───┤",
        # |Other|                            bottom________= "└───┴───┴───┴───┴───┴───┘")
        # |Other|        elif self.renderOptions.colDivPre.startswith('║'):
        # |Other|            borders=Borders(len(self.renderOptions.colDivPre)-1,
        # |Other|                            top___________= "╔═══╦═══╦═══╤═══╦═══╦═══╗",
        # |Other|                            title_________= "║ A ║ B ║ C │ D ║ E ║ F ║",
        # |Other|                            undTopTitle___= "╠═══╬═══╬═══╪═══╬═══╬═══╣",
        # |Other|                            entry_1_______= "║ A ║ B ║ n │ n ║ E ║ F ║",
        # |Other|                            betweenEntries= "╟───╫───╫───┼───╫───╫───╢",
        # |Other|                            entry_2_______= "║ A ║ B ║ n │ n ║ E ║ F ║",
        # |Other|                            overBotTitle__= "╠═══╬═══╬═══╪═══╬═══╬═══╣",
        # |Other|                            bottom________= "╚═══╩═══╩═══╧═══╩═══╩═══╝")
        # |Other|
        lines.extend(dividerAsTextLines("top"))

        if self.in_table.colTitles.hasData():
            lines.extend(row_asTextLines(self.in_table.colTitles, "title"))

        kind = "undTopTitle"
        for row in self.in_table.rows().values():

            lines.extend(dividerAsTextLines(kind))
            kind = "betweenEntries"

            lines.extend(row_asTextLines(row, "entry"))

        lines.extend(dividerAsTextLines("bottom"))

        return lines

    def doDump(self):
        for line in self.out_lines:
            print(line)


class PrettyTable:
    Table = PrettyTable_Contents
    RenderOptions = RenderOptions_Table
    Rendered = PrettyTable_Rendered
    Row = PrettyTable_Row
    RowList = PrettyTable_RowList
