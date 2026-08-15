from ukkoDataFormats import SparseList
import prettyText

################################################################################

PrettyCellContents = str

PrettyTable_RowList = list[PrettyCellContents | None]


################################################################################
#
class MaxWidths:
    def __init__(self):
        self.data = SparseList[int](0)

    def __getitem__(self, pos: int) -> int:
        return self.data[pos]

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
