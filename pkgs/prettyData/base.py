import os
import sys

from typing import Any, Callable, Self, Tuple, Union

import numpy as np
from pathlib import Path

################################################################################
#
# Ensure shared Packages are available
#

packages_dir = str((Path(__file__).parent.parent.parent / "pkgs").absolute())
if not packages_dir.endswith("/pkgs") or not os.path.exists(packages_dir):
    exit(f"❌  {__file__}\n    Misconfigured: [/path/to]/pkgs is not {packages_dir}")

if packages_dir not in sys.path:
    sys.path.append(packages_dir)
#
################################################################################

from appLogging import appLog
import prettyText, ukkoUtils

from ukkoDataFormats import (
    JsonDict,
    SparseList,
    Sparse2D,
    NameValuePairList,
    NameValuePair,
)


################################################################################

PrettyCellContents = str

PrettyTable_RowList = list[PrettyCellContents | None]


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
                self.includeVal(colNum, prettyText.uniLen_approx(colText))


class IPrettyData_Render_Interface:
    def asTextLines(self) -> list[str]:
        raise NotImplementedError(
            self.__class__.__name__ + ".asTextLines() isn't implemented"
        )

    def doDump(self):
        for line in self.asTextLines():
            print(line)
