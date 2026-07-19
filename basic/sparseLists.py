import os
import sys

from typing import Any, Tuple

import numpy as np


class RangeInt:
    def __init__(self, first: int, last: int):
        self.first = first
        self.last = last

    def asText(self) -> str:
        txt = str(self.first)
        if self.last != self.first:
            txt += f"…{self.last}"
        return txt

    def appendNext(self, nextValue: int) -> bool:
        if nextValue != self.last + 1:
            return False
        self.last += 1
        return True

    def as_range(self) -> range:
        return range(self.first, self.last + 1)


class RangesInt(list[RangeInt]):
    def __init__(self, src: list[int] | None):
        super().__init__()

        if src:

            _values = sorted(src)

            currentRange: RangeInt | None = None

            for n in _values:
                if currentRange is None:
                    currentRange = RangeInt(n, n)
                elif not currentRange.appendNext(n):
                    self.append(currentRange)
                    currentRange = RangeInt(n, n)

            if currentRange:
                self.append(currentRange)

    def asTextList(self) -> list[str]:
        return [entry.asText() for entry in self]


class SparseList[ContentKind](dict[int, ContentKind]):

    def asDict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        # |x|result["_kind"]=f"SparseList[{typeAsText(self._getContentType())}]"
        # |Logging|result['len-includingBlanks']=self.getLen(includingBlanks=True)
        # |Logging|result['len-withoutBlanks']=self.getLen(includingBlanks=False)
        # |x|result['len-includingBlanks-calc']=max(self.keys())+1 if self else 0

        if self.note:
            result["note"] = self.note
        if self.hasData():

            ranges = RangesInt(list(self.keys()))

            for _rangeVal in ranges:
                entry = [self[n] for n in _rangeVal.as_range()]
                result[_rangeVal.asText()] = entry[0] if len(entry) == 1 else entry

        return result

    def __init__(self, iterableSource: Any | None = None, note: Any | None = None):

        if iterableSource:
            for n, value in iterableSource:
                self[n] = value
        self.note = note

    # |x|        self._refresh()

    @staticmethod
    def createFromList(
        src: list[ContentKind | None] | None, note: Any | None = None
    ) -> "SparseList[ContentKind]":
        result = SparseList[ContentKind](note=note)
        if src is not None:
            for n in range(len(src)):
                value = src[n]
                if value is not None:
                    result[n] = value

        # |x|        result._refresh()
        return result

    # |x|    def _refresh(self):
    # |x|        if self.hasData():
    # |x|            self._maxKeyPlusOne=max(self.keys())+1
    # |x|        else:
    # |x|            self._maxKeyPlusOne=0

    def hasData(self) -> bool:
        return len(self) > 0

    def getLen(self, includingBlanks: bool = True) -> int:
        if not self.hasData():
            return 0
        elif not includingBlanks:
            return len(self.keys())
        else:
            return max(self.keys()) + 1

    def asList(self) -> list[ContentKind]:
        return [self.getOrEmpty(n) for n in range(self.getLen())]

    def _newKey(self, position: int | None = None) -> int:
        if position is None:
            pos: int = self.getLen()
        else:
            pos: int = position
        return pos

    def append(self, entry: ContentKind):
        self.setEntry(entry, None)

    def setEntry(self, entry: ContentKind, position: int | None = None) -> ContentKind:
        posUsed = self._newKey(position)
        self[posUsed] = entry
        return self[posUsed]

    def _getContentType(self) -> Any | None:
        orig_class = getattr(self, "__orig_class__", None)
        if orig_class is not None:
            content_type = getattr(orig_class, "__args__", [None])[0]
            return content_type
        return None

    def _defaultContent(self) -> ContentKind:
        # print(f"Calling self._defaultContent({ContentKind})")
        theType = self._getContentType()
        if callable(theType):
            return theType()  # type: ignore[call-arg]

        try:
            return 0  # pyright: ignore[reportReturnType]
        except:
            raise TypeError(
                f"SparceList[{typeAsText(self._getContentType)}]: Cannot create default ContentKind"
            )

    def getOrCreate(self, position: int) -> ContentKind:
        if position in self:
            return self[position]
        else:
            return self.setEntry(self._defaultContent(), position)

    def getOrEmpty(self, position: int) -> ContentKind:
        if position in self:
            return self[position]

        return self._defaultContent()


def typeAsText(theType):

    try:
        # |x|if hasattr(theType,'__mro__'):
        # |x|    txt=str(theType.__mro__)
        # |x|else:
        txt = str(theType)

        txt = txt.removeprefix("<class '").removesuffix("'>")
    except Exception:
        txt = str(theType)
    return txt


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
                from ukko_pylibs.basic.simpleUtils import PrettyText as PrettyText

                self.includeVal(colNum, PrettyText.uniLen_approx(colText))
            # |x|     print(f"{colNum}: {colText}")
            # |x| else:
            # |x|     print(f"{colNum}: SKIP: {colText}")
        # |x| print(f"includeWidths_SparseList -> {self.asDict()}")


class Sparse2D[CellContentKind]:

    def _getContentType(self) -> Any | None:
        orig_class = getattr(self, "__orig_class__", None)
        if orig_class is not None:
            content_type = getattr(orig_class, "__args__", [None])[0]
            return content_type

    def _getContentTypeAsText(self) -> str:
        return typeAsText(self._getContentType())

    def __init__(self):
        self.rows = SparseList[SparseList[CellContentKind]]()

        self._numCols = 0

    def hasData(self) -> bool:
        return self.rows.hasData()

    def asDict(self):
        return {
            "_kind": f"Sparse2D[{typeAsText(self._getContentType())}]",
            "numCols": self._numCols,
            "rows": self.rows.asDict(),
        }

    def numRows(self) -> int:
        return self.rows.getLen()

    def numCols(self) -> int:
        return self._numCols

    def _noteColNum(self, colNum: int):
        if colNum >= self._numCols:
            self._numCols = colNum + 1

    def includeCell(
        self,
        entry: CellContentKind,
        colPosition: int | None = None,
        rowPosition: int | None = None,
    ) -> Tuple[int, int]:
        colPos = self.numCols() if colPosition is None else colPosition
        rowPos = self.numRows() if rowPosition is None else rowPosition

        row = self.rows.getOrCreate(rowPos)
        row.setEntry(entry, colPos)

        self._noteColNum(colPos)

        return (colPos, rowPos)

    def includeRow(
        self, row: SparseList[CellContentKind], rowPos: int | None
    ) -> SparseList[CellContentKind]:
        if row:
            self._noteColNum(max(row.keys()))

        return self.rows.setEntry(row, rowPos)

    def appendRow(self, row: SparseList[CellContentKind]):
        return self.includeRow(row, None)

    def appendCol(self, col: SparseList[CellContentKind]):
        return self.includeCol(col, None)

    def includeCol(
        self, col: SparseList[CellContentKind], colPosition: int | None = None
    ) -> int:
        colPos = self.numCols() if colPosition is None else colPosition
        for rowNum, entry in col.items():
            _row = self.rows.getOrCreate(rowNum)
            _row.setEntry(entry, colPos)

        self._noteColNum(colPos)

        return colPos
