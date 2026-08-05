from typing import Union


from ukkoDataFormats import SparseList

from prettyData.base import PrettyTable_RowList, PrettyCellContents

################################################################################


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
