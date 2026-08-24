from copy import deepcopy

from typing import Any, Union


from appLogging import appLog


################################################################################
#
class WalkedEntry:
    def __init__(
        self,
        entry: Any | None = None,
        parentage: Union["WalkedEntry", None] = None,
        key: str | int | None = None,
    ):
        self.entry: Any | None = entry
        self.parentRef: WalkedEntry | None = parentage
        self.key: str | int | None = key

    def hasType(self, kind: type) -> bool:
        return type(self.entry) is kind

    def createChild(self, key: str | int) -> "WalkedEntry":
        if type(self.entry) is list and type(key) is int:
            return WalkedEntry(self.entry[key], self, key)
        elif type(self.entry) is dict:
            return WalkedEntry(self.entry[key], self, key)
        else:
            raise ValueError("Parent entry is not keyable")

    def isEmpty(self) -> bool:
        return self.entry is None and self.parentRef is None

    def isSettable(self) -> bool:
        if self.parentRef is None or self.key is None:
            return False
        elif isinstance(self.parentRef.entry, dict):
            return True
        elif isinstance(self.parentRef.entry, list) and type(self.key) is int:
            return True
        else:
            return False

    def setValue(self, value: Any):
        self.entry = value
        if (
            self.parentRef is not None
            and isinstance(self.parentRef.entry, dict)
            and self.key is not None
        ):
            self.parentRef.entry[self.key] = value
        elif (
            self.parentRef is not None
            and isinstance(self.parentRef.entry, list)
            and type(self.key) is int
        ):
            self.parentRef.entry[self.key] = value
        else:
            appLog.print_warning(f"{self}.setValue({value}) is Invalid.  Ignored")

    def parentAsTextWithTrailingDot(self) -> str:
        if not self.parentRef:
            return ""
        else:
            return f"{self.parentRef.parentAsTextWithTrailingDot()}[{self.key}]."

    def asText(self) -> str:
        txt = self.parentAsTextWithTrailingDot().removesuffix(".")

        if txt != "":
            txt += "="

        if self.entry is None:
            return txt + "None"
        else:
            return txt + f"{type(self.entry)}"

    def __str__(self) -> str:
        return self.asText()

    @staticmethod
    def getEntry(src: Union["WalkedEntry", None]) -> dict | list | None:
        return None if src is None else src.entry

    @staticmethod
    def getKey(src: Union["WalkedEntry", None]) -> int | str | None:
        return None if src is None else src.key

    def parent(self, depth: int = 1) -> "WalkedEntry":
        return WalkedEntry._getAncestor(self, depth) or WalkedEntry()

    @staticmethod
    def _getAncestor(
        src: Union["WalkedEntry", None], depth: int = 1
    ) -> Union["WalkedEntry", None]:
        while depth > 0:
            if src is None:
                return None

            src = src.parentRef
            depth -= 1
        return src


class IWalkTreeAction_Interface:
    def __init__(self, baseOptions: dict[str, Any] | None = None):
        self.baseOptions = baseOptions or {}

    def isSkipping(self, walkingOptions: dict[str, Any]) -> bool:
        return bool(walkingOptions.get("skip"))

    def setSkipping(self, walkingOptions: dict[str, Any]):
        walkingOptions["skip"] = True

    def doEntryReview(self, walkedEntry: WalkedEntry, walkingOptions: dict[str, Any]):
        # < Returns: (Bool)=No child iteration
        # < The walkingOptions options will be passed to children & later siblings only
        # < Use 'skip'=True to skip the children/later siblings
        appLog.print_tediousDetail(
            "WalkTree. Reviewing: "
            + walkedEntry.asText()
            + f"  Walking Options:{walkingOptions}   BaseOptions:{self.baseOptions}"
        )

    def onEntryIterationCompleted(
        self, walkedEntry: WalkedEntry, walkingOptions: dict[str, Any]
    ):
        appLog.print_tediousDetail(
            "WalkTree. Completed: "
            + walkedEntry.asText()
            + f"  Walking Options:{walkingOptions}   BaseOptions:{self.baseOptions}"
        )

    def walkTree(
        self, objToWalk: WalkedEntry | Any, walkingOptions: dict[str, Any] | None = None
    ):
        """Walks a dictionary tree (or list), running 'doEntryReview' on each position &  onEntryIterationCompleted() after each position with children (or possibility of children - eg: list,dict)"""

        if type(objToWalk) is WalkedEntry:
            walkedEntry = objToWalk
        else:
            walkedEntry = WalkedEntry(objToWalk)

        options = deepcopy(walkingOptions) or {}
        self.doEntryReview(walkedEntry, options)

        if options.get("skip"):
            return  # <- Don't review children

        obj = walkedEntry.entry
        if isinstance(obj, dict):
            for key in list(obj.keys()):
                if self.isSkipping(options):
                    break
                self.walkTree(WalkedEntry(obj[key], walkedEntry, key), options)
            self.onEntryIterationCompleted(walkedEntry, options)
        elif isinstance(obj, list):
            for key in range(
                len(obj) - 1, -1, -1
            ):  # Go backwards so we can delete in our 'action' function
                if self.isSkipping(options):
                    break
                self.walkTree(WalkedEntry(obj[key], walkedEntry, key), options)
            self.onEntryIterationCompleted(walkedEntry, options)
