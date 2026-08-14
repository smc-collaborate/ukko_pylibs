################
#
from copy import deepcopy
from typing import Any, Tuple, Union
from typing import Generic, TypeVar  # < Needed for compliance with Python 3.10

################
#
from ukkoUtils import typeAsStr, createFrom_basedOnTemplate, asJsonable, asJsonStr
from appLogging import appLog

################
#


def visLength(text: str) -> int:
    import prettyText

    return prettyText.uniLen_approx(text)


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


# Below is equivalent to:
# class SparseList[ContentKind](dict[int, ContentKind]):  .. for Python 3.10

ContentKind = TypeVar("ContentKind")


class SparseList(dict[int, ContentKind], Generic[ContentKind]):
    @staticmethod
    def create_fromJsonDict_andBlank(
        spec: dict | list, blankValue: ContentKind
    ) -> "SparseList[ContentKind]":
        if isinstance(spec, list):
            mySrc = list[ContentKind | None]()
            for x in spec:
                mySrc.append(SparseList[ContentKind](blankValue)._jsonImportContent(x))
            return SparseList[ContentKind].create_fromList_andBlank(mySrc, blankValue)
        elif isinstance(spec, dict):
            result = SparseList[ContentKind](blankValue)
            for key, value in spec.items():
                result[int(key)] = result._jsonImportContent(value)
            return result
        else:
            raise TypeError(
                f"SparseList.create_fromJsonDict(): Cannot import type {type(spec)}"
            )

    @staticmethod
    def create_fromJsonDictOrNone_andBlank(
        spec: dict | list | None, blankValue: ContentKind
    ) -> "SparseList[ContentKind]":
        return (
            SparseList[ContentKind](blankValue)
            if spec is None
            else SparseList[ContentKind].create_fromJsonDict_andBlank(spec, blankValue)
        )

    @staticmethod
    def createOrNone_fromJsonDictOrNone_andBlank(
        spec: dict | list | None, blankValue: ContentKind
    ) -> Union["SparseList[ContentKind]", None]:
        return (
            None
            if spec is None
            else SparseList[ContentKind].create_fromJsonDict_andBlank(spec, blankValue)
        )

    @staticmethod
    def create_fromList_andBlank(
        src: list[ContentKind | None], blankValue: ContentKind
    ) -> "SparseList[ContentKind]":
        result = SparseList[ContentKind](blankValue)

        if src is not None:
            for n in range(len(src)):
                value = src[n]
                if value is not None:
                    if type(blankValue) == type(value):
                        result[n] = value
                    elif hasattr(
                        blankValue, "create_fromJsonDict_andBlank"
                    ) and callable(getattr(blankValue, "create_fromJsonDict_andBlank")):
                        result[n] = (
                            blankValue.create_fromJsonDict_andBlank(  # pyright: ignore[reportAttributeAccessIssue]
                                value, blankValue
                            )
                        )
                    elif hasattr(blankValue, "create_fromJsonDict") and callable(
                        getattr(blankValue, "create_fromJsonDict")
                    ):
                        result[n] = (
                            blankValue.create_fromJsonDict(  # pyright: ignore[reportAttributeAccessIssue]
                                value
                            )
                        )
                    else:
                        appLog.print_warning(
                            f"Populating SparseList[type:{type(blankValue)}] with type {type(value)}={value}  - ignoring"
                        )

        return result

    @property
    def classCaption(self) -> str:
        txt = asJsonStr(self._blankValue)
        if txt == "null":
            txt = ""
        else:
            txt = "default:" + txt
        return f"SparseList[{typeAsStr(self._getContentType())}]({txt})"

    @staticmethod
    def createOrNone_fromListOrNone_andBlank(
        src: list[ContentKind | None] | None, blankValue: ContentKind
    ) -> Union["SparseList[ContentKind]", None]:
        return (
            None
            if src is None
            else SparseList[ContentKind].create_fromList_andBlank(src, blankValue)
        )

    @staticmethod
    def create_fromListOrNone_andBlank(
        src: list[ContentKind | None] | None, blankValue: ContentKind
    ) -> "SparseList[ContentKind]":
        return (
            SparseList[ContentKind](blankValue)
            if src is None
            else SparseList[ContentKind].create_fromList_andBlank(src, blankValue)
        )

    def asJsonable(self) -> dict[str, Any]:
        result: dict[str, Any] = {}

        if self.hasData():

            ranges = RangesInt(list(self.keys()))

            for _rangeVal in ranges:
                entry = [self[n] for n in _rangeVal.as_range()]
                result[_rangeVal.asText()] = entry[0] if len(entry) == 1 else entry

        return result

    def __init__(
        self,
        blankValue: ContentKind,
        src: Union["SparseList[ContentKind]", dict[int, ContentKind], None] = None,
    ):
        self._blankValue = blankValue
        if src is not None:
            self.update(src)

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

    def append(self, entry: ContentKind) -> int:
        return self._setEntry(entry, None)[1]

    def _setEntry(
        self, entry: ContentKind, position: int | None = None
    ) -> Tuple[ContentKind, int]:
        posUsed = self._newKey(position)
        self[posUsed] = entry
        return self[posUsed], posUsed

    def setEntry(self, entry: ContentKind, position: int | None = None) -> ContentKind:
        return self._setEntry(entry, position)[0]

    def _getContentType(self) -> type:
        return type(self._blankValue)

    def _defaultContent(self) -> ContentKind:
        # print(f"Calling self._defaultContent({ContentKind})")
        theType = self._getContentType()
        if callable(theType):
            return theType()  # type: ignore[call-arg]

        for value in ["", 0]:
            try:
                valueOut: ContentKind = value  # Throws an exception if not possible
                return valueOut
            except:
                pass
        raise TypeError(self.classCaption + ": Cannot create default ContentKind")

    def _jsonImportContent(self, valueIn) -> ContentKind:
        return createFrom_basedOnTemplate(valueIn, self._blankValue)

    def getOrCreate(self, position: int) -> ContentKind:
        if position in self:
            return self[position]
        else:
            return self.setEntry(self._defaultContent(), position)

    def getOrEmpty(self, position: int) -> ContentKind:
        if position in self:
            return self[position]

        return deepcopy(self._blankValue)


class MaxWidths(SparseList[int]):
    def __init__(self):
        super().__init__(0)

    def includeVal(self, colNum: int, width: int):
        self[colNum] = max(self.getOrEmpty(colNum), width)

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
            if not skipIfColIsEmpty or self.getOrEmpty(colNum) > 0:
                self.includeVal(colNum, visLength(colText))


# Below is equivalent to:
# class Sparse2D[CellContentKind]:  .. for Python 3.10
CellContentKind = TypeVar("CellContentKind")


class Sparse2D(Generic[CellContentKind]):

    def _getContentType(self) -> Any | None:
        orig_class = getattr(self, "__orig_class__", None)
        if orig_class is not None:
            content_type = getattr(orig_class, "__args__", [None])[0]
            return content_type

    def _getContentTypeAsText(self) -> str:
        return typeAsStr(self._getContentType())

    def __init__(self, blankCellContent: CellContentKind):
        self.blankEntry = blankCellContent
        self.rows = SparseList[SparseList[CellContentKind]](
            SparseList[CellContentKind](blankCellContent)
        )

        self._numCols = 0

    def hasData(self) -> bool:
        return self.rows.hasData()

    def asJsonable(self):
        return {
            "_kind": f"Sparse2D[{typeAsStr(self._getContentType())}]",
            "numCols": self._numCols,
            "rows": self.rows.asJsonable(),
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

    def appendCol(self, col: SparseList[CellContentKind] | None):
        if col is not None:
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
