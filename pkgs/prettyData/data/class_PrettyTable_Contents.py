import os
import sys

from typing import Any, Callable, Self, Tuple, Union

import numpy as np
from pathlib import Path

################################################################################
#
# Ensure shared Packages are available
#

packages_dir = str(
    (Path(__file__).absolute().parent.parent.parent.parent / "pkgs").absolute()
)
if not packages_dir.endswith("/pkgs") or not os.path.exists(packages_dir):
    exit(f"❌  {__file__}\n    Misconfigured: [/path/to]/pkgs is not {packages_dir}")

if packages_dir not in sys.path:
    sys.path.append(packages_dir)
#
################################################################################


from ukkoDataFormats import NameValuePairList, Sparse2D, SparseList


################################################################################
#
from prettyData.base import PrettyTable_RowList, PrettyCellContents, MaxWidths
from prettyData.data.prettyTable_Rows import PrettyTable_Row


class PrettyTable_Contents:
    def __init__(self, titles: PrettyTable_RowList | None = None):
        self.colTitles = PrettyTable_Row(titles)
        self.contentsGrid = Sparse2D[PrettyCellContents](PrettyCellContents())
        self.src = None

    def asDict(self) -> dict[str, Any]:
        result = {"colTitle": self.colTitles, "contentsGrid": self.contentsGrid}

        if self.src is not None:
            result["source"] = self.src

        return result

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
        table.src = spec
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
        import ukkoUtils

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
                            lines.append(
                                f"{key2:<{keyLen}} : {ukkoUtils.asStr(value2)}"
                            )
                    nameValues.append(("Value", "\n".join(lines)))
                else:
                    nameValues.append(("Value", ukkoUtils.asStr(value)))
            elif isinstance(value, dict):
                nameValues.append((keyTitle, key))
                for key2, value2 in value.items():
                    if value2 is not None:
                        nameValues.append((key2, ukkoUtils.asStr(value2)))
            else:
                nameValues.append((keyTitle, ukkoUtils.asStr(value)))

            result.appendRow_namePairList(nameValues)

        return result


# |x| from . import renderOptions
# |x|
# |x|    def renderAs(
# |x|        self, options: Union["renderOptions.Table", str | None] = None
# |x|    ) -> "PrettyTable_Rendered":
# |x|
# |x|        optionsToUse = renderOptions.able | None
# |x|        if not isinstance(options, str):
# |x|            optionsToUse = options
# |x|        else:
# |x|            optionsToUse = renderOptions.Table(
# |x|                Borders.createOrNoneFrom_name(options), None
# |x|            )
# |x|
# |x|        return PrettyTable_Rendered(self, optionsToUse)
