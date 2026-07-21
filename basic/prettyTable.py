import os
import sys

from typing import Any, Callable, Self, Tuple, Union

import numpy as np

################################################################################
#
# Add project root directory to system path


shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.class_JsonData import JsonDict
from ukko_pylibs.basic.logger import appLog
from ukko_pylibs.basic.simpleUtils import PrettyText, Utils
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
        # |x| print(f"includeWidths_list_str: {src}")

        self.includeWidths_SparseList(
            SparseList[str].create_fromList_andBlank(src, ""), skipIfColIsEmpty
        )

    def includeWidths_SparseList(
        self, src: SparseList[str], skipIfColIsEmpty: bool = False
    ):
        # |x| print(f"includeWidths_SparseList: {Utils.asJsonStr(src.asDict())}")
        for colNum, colText in src.items():
            if not skipIfColIsEmpty or self.data.getOrEmpty(colNum) > 0:
                self.includeVal(colNum, PrettyText.uniLen_approx(colText))
            # |x|     print(f"{colNum}: {colText}")
            # |x| else:
            # |x|     print(f"{colNum}: SKIP: {colText}")
        # |x| print(f"includeWidths_SparseList -> {self.asDict()}")


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


class RenderOptions_SingleCol:
    """Options to Render a PrettyTable column
    Note that all widths are 'visual widths' - which can include wider icons, remove ANSI codes etc
    """

    def __init__(
        self,
        lockedMaxVisWidth: int | None = None,
        prefixesToWrapWith: list[str] | None = None,
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


class RenderOptions_Table:
    """Options to Render a PrettyTable"""

    def __init__(
        self,
        colDivider: str | None = None,
        colOptions: RenderOptions_Columns | None = None,
    ):
        self.colDivider = " " if colDivider is None else colDivider  # ' ' # = "│",
        self.colOptions = RenderOptions_Columns() if colOptions is None else colOptions

    @staticmethod
    def createOrNone_fromJsonDictOrNone(
        spec: dict | None,
    ) -> Union["RenderOptions_Table", None]:
        if spec is None:
            return None

        _colDivider = spec.get("colDivider")
        _colOptions = RenderOptions_Columns.createOrNone_fromJsonDictOrNone(
            spec.get("colOptions")
        )

        return RenderOptions_Table(_colDivider, _colOptions)

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
        # |x| print("!!! PrettyTable_Rendered()")

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

        # |x|print("----------------")
        # |x|print("PrettyTable_Rendered.out_lines():")
        # |x|print(Utils.asJsonStr(self.out_lines,indent=2))
        # |x|print("----------------")

    def asLines(self) -> list[str]:
        return self.out_lines

    def doBuild(self) -> list[str]:

        self.proc_visWidths_calc: MaxWidths = (
            self.in_table.getMaxWidths()
        )  # < Before clipping, wrapping etc.
        self.proc_visWidths_used: list[int] = []

        # |x|print("----------------")
        # |x|print("PrettyTable_Rendered.proc_visWidths_calc:")
        # |x|print(Utils.asJsonStr(self.proc_visWidths_calc.asDict()))
        # |x|print("----------------")
        # |x|print("PrettyTable_Rendered.in_table:")
        # |x|print(Utils.asJsonStr(self.in_table.asDict(),indent=2))
        # |x|print("----------------")
        # |x|print("renderOptions:")
        # |x|print(Utils.asJsonStr(self.renderOptions,indent=2))
        # |x|print("----------------")
        for colNum in range(self.proc_visWidths_calc.getLen()):
            maxVisWidth = self.renderOptions.getMaxVisWidth(colNum)
            # |x| print("MaxVisWidth: ",maxVisWidth)
            calc = self.proc_visWidths_calc[colNum]
            used = calc
            if maxVisWidth is not None:
                if maxVisWidth < used:
                    used = maxVisWidth
            self.proc_visWidths_used.append(used)

        def row_asTextLines(
            row: SparseList[PrettyCellContents] | PrettyTable_Row | None,
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
            for n in range(rowHeight):
                linesOut.append(
                    self.renderOptions.colDivider.join(
                        [cell.getRowText(n) for cell in cellsInRow]
                    )
                )

            return linesOut

        lines: list[str] = []
        if self.in_table.colTitles.hasData():
            lines.extend(row_asTextLines(self.in_table.colTitles))
            # |x| lines.append((str(self.in_table.colTitles.asDict()),"_debugNote:colTitles"))
        for row in self.in_table.rows().values():
            # |x| print(f"row[type:{type(row)}]: {row}")
            lines.extend(row_asTextLines(row))
            # |x| lines.append((str(row.asDict()),"_debugNote:row"))

        if False:

            def widsAsText(wids: list[int], caption: str):
                txt: str = ""
                for wid in self.proc_visWidths_used:
                    if txt != "":
                        txt += "|"
                    if wid > 0:
                        txt += "-" * wid
                return txt + " : " + caption + "=" + str(wids)

            lines.insert(
                0,
                (
                    widsAsText(self.proc_visWidths_used, "proc_visWidths_used"),
                    "_debugNote",
                ),
            )
            lines.insert(
                0,
                (
                    widsAsText(
                        self.proc_visWidths_calc.asList(), "proc_visWidths_calc"
                    ),
                    "_debugNote",
                ),
            )
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
