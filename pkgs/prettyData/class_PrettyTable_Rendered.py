import sys, os

from pathlib import Path


from ukkoDataFormats import SparseList
import prettyText, ukkoUtils
from appLogging import appLog

################################################################################
#


from prettyData import renderOptions as renderOptions
from .base import MaxWidths, PrettyCellContents, IPrettyData_Render_Interface
from .data.class_PrettyTable_Contents import PrettyTable_Contents
from .data.prettyTable_Rows import PrettyTable_Row


class CellInfo:
    def __init__(
        self,
        srcText: str,
        styleWidth: int = 20,
        stylingOption: renderOptions.GridPart | None = None,
    ):

        from ukkoStyling import styling

        self.baseLines: list[str] = prettyText.textWrapWithPrefixes(
            srcText,
            styleWidth,
            (True if stylingOption is None else stylingOption.prefixesToWrapWith),
        )

        self._lines: list[str] = []
        colouring = "" if stylingOption is None else stylingOption.styleAndColour
        openingColourCodes = ""
        for line in self.baseLines:
            if line == "":
                self._lines.append(line)
            else:
                # if (openingColourCodes): #<-- @todo: Cope with truncated rendering

                self._lines.append(styling.apply(line, colouring))
        self.width: int = styleWidth

    def height(self) -> int:
        return len(self._lines)

    def getRowText(self, rowNum: int) -> str:
        txt = self._lines[rowNum] if rowNum in range(len(self._lines)) else ""

        return prettyText.padToWidth(txt, self.width)


class PrettyTable_Rendered(IPrettyData_Render_Interface):
    def __init__(
        self,
        tableSrc: PrettyTable_Contents,
        renderOptionsIn: (
            renderOptions.Table | str | dict | list[int | None] | None
        ) = None,
    ):
        self.in_table = tableSrc

        if isinstance(renderOptionsIn, str | dict | None):
            #####
            self.renderOptions = renderOptions.Table(renderOptionsIn)
        elif isinstance(renderOptionsIn, renderOptions.Table):
            self.renderOptions = renderOptionsIn
        elif isinstance(renderOptionsIn, list):
            self.renderOptions = renderOptions.Table.create_fromLockedVisWidths(
                renderOptionsIn
            )
        else:
            if renderOptionsIn is not None:
                appLog.print_warning(
                    f"PrettyTableRendered: renderOptionsIn={type(renderOptionsIn)} .v. {(renderOptions.Table)}"
                )
            self.renderOptions = renderOptions.Table()
        self.out_lines: list[str] = self.doBuild()

    def asTextLines(self) -> list[str]:
        if False:
            return [f"Table Style: {self.renderOptions.asJsonable()}"] + self.out_lines
        else:
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
            rowStyleSource_: str | None = None,
        ) -> list[str]:

            if row is None:
                return []

            rowStyleSource = (
                borderStyleSource if rowStyleSource_ is None else rowStyleSource_
            )
            # |x| print(f"rowStyleSource:{rowStyleSource}")
            cellsInRow: list[CellInfo] = []
            for colNum in range(len(self.proc_visWidths_used)):

                wid = self.proc_visWidths_used[colNum]
                if wid > 0:
                    cellsInRow.append(
                        CellInfo(
                            row.getOrEmpty(colNum),
                            wid,
                            self.renderOptions.getRenderOption(colNum, rowStyleSource),
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
