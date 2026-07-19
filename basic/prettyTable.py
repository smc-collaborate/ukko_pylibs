import os
import sys

from typing import Any, Callable, Tuple

import numpy as np

################################################################################
#
# Add project root directory to system path


shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.logger import appLog
from ukko_pylibs.basic.simpleUtils import PrettyText, Utils
from ukko_pylibs.basic.sparseLists import SparseList, Sparse2D


################################################################################
#
class MaxWidths(SparseList[int]):
    def __init__(self):
        super().__init__()

    def includeVal(self, colNum: int, width: int):
        self[colNum] = max(self.getOrEmpty(colNum), width)

    def includeWidths_list_str(
        self, src: list[str | None], skipIfColIsEmpty: bool = False
    ):
        # |x| print(f"includeWidths_list_str: {src}")

        self.includeWidths_SparseList(
            SparseList[str].createFromList(src, None), skipIfColIsEmpty
        )

    def includeWidths_SparseList(
        self, src: SparseList[str], skipIfColIsEmpty: bool = False
    ):
        # |x| print(f"includeWidths_SparseList: {Utils.asJsonStr(src.asDict())}")
        for colNum, colText in src.items():
            if not skipIfColIsEmpty or self.getOrEmpty(colNum) > 0:
                self.includeVal(colNum, PrettyText.uniLen_approx(colText))
            # |x|     print(f"{colNum}: {colText}")
            # |x| else:
            # |x|     print(f"{colNum}: SKIP: {colText}")
        # |x| print(f"includeWidths_SparseList -> {self.asDict()}")


PrettyCellContents = str
PrettyTable_Row = SparseList[PrettyCellContents]


class PrettyTable:
    def __init__(self, titles: list[PrettyCellContents | None] | None = None):
        self.colTitles = PrettyTable_Row.createFromList(titles, note="[title]")
        self.contentsGrid = Sparse2D[PrettyCellContents]()

    def asDict(self) -> dict[str, Any]:
        return {"colTitle": self.colTitles, "contentsGrid": self.contentsGrid}

    def rows(self) -> SparseList[PrettyTable_Row]:
        return self.contentsGrid.rows

    def appendRow(self, row: PrettyTable_Row):
        self.contentsGrid.appendRow(row)

    def appendTable(self, addThis: "PrettyTable", withSeparatingBlankLine: bool = True):
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
        self.contentsGrid.appendRow(PrettyTable_Row())

    def appendRowList(self, row: list[PrettyCellContents | None], note: Any | None):
        self.contentsGrid.appendRow(PrettyTable_Row.createFromList(row, note))

    def appendColList(self, col: list[PrettyCellContents | None]):
        self.contentsGrid.appendCol(PrettyTable_Row.createFromList(col))

    def hasData(self) -> bool:
        return self.contentsGrid.hasData()

    def getGridMaxWidths(self):
        maxWidths_calc = MaxWidths()

        for row in self.contentsGrid.rows.values():
            maxWidths_calc.includeWidths_SparseList(row)

        return maxWidths_calc

    def getMaxWidths(self) -> MaxWidths:

        maxWidths_calc = self.getGridMaxWidths()
        maxWidths_calc.includeWidths_SparseList(self.colTitles, skipIfColIsEmpty=True)
        return maxWidths_calc


class RenderOptions_SingleCol:
    """Options to Render a PrettyTable column
    Note that all widths are 'visual widths' - which can include wider icons, remove ANSI codes etc
    """

    def __init__(
        self,
        lockedMaxVisWidth: int | None = None,
        prefixesToWrapWith: list[str] | None = None,
    ):
        self.lockedMaxVisWidth: int | None = (
            lockedMaxVisWidth  # < None = Auto-calculate
        )
        self.is_wrap = True  # < Wrap on visual Width
        self._calcWidth: list[int] | None = None
        self.prefixesToWrapWith = prefixesToWrapWith


RenderOptions_Columns = SparseList[RenderOptions_SingleCol]


class RenderOptions_Table:
    """Options to Render a PrettyTable"""

    def __init__(
        self, colDivider: str = " ", colOptions: RenderOptions_Columns | None = None
    ):
        self.colDivider = colDivider  # ' ' # = "│",
        self.colOptions = RenderOptions_Columns() if colOptions is None else colOptions

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
        tableSrc: PrettyTable,
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

        def row_asText(row: PrettyTable_Row | None) -> str:
            txtOut = ""
            # note:Any|None=None
            if row:
                # note=row.note
                for colNum in range(len(self.proc_visWidths_used)):

                    wid = self.proc_visWidths_used[colNum]
                    if wid > 0:
                        if txtOut != "":
                            txtOut += self.renderOptions.colDivider
                        txtOut += PrettyText.padToWidth(row.getOrEmpty(colNum), wid)
            return txtOut

        lines: list[str] = []
        if self.in_table.colTitles:
            lines.append(row_asText(self.in_table.colTitles))
            # |x| lines.append((str(self.in_table.colTitles.asDict()),"_debugNote:colTitles"))
        for row in self.in_table.rows().values():
            # |x| print(f"row[type:{type(row)}]: {row}")
            lines.append(row_asText(row))
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
