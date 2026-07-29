from copy import deepcopy
import json
import os, sys
from pathlib import Path
from typing import Any, Tuple, Union

################################################################################
#
# Add project root directory to system path


shared_dir = os.path.abspath(f"{Path(__file__).parent}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import DictUtils, Utils
from ukko_pylibs.basic.simpleUtils import DictUtils as Options

from ukko_pylibs.basic.logger import appLog

################################################################################
#


def _sysModules_asList(doFilter: bool = True) -> list[dict[str, Any]]:

    moduleList: list[dict[str, Any]] = []

    def _appendModuleInfos(moduleSrc, treePosition, dest: list[dict[str, Any]]):

        parentObj: dict[str, Any] = {"leaf": treePosition}
        try:
            dataSrc = moduleSrc.__dict__

            def _addIfFound(_key: str, defaultValue: str | None = None):
                value = dataSrc.get(_key)
                if value and (value != defaultValue):
                    parentObj[_key.removeprefix("__").removesuffix("__")] = value

            _addIfFound("__name__", treePosition)
            _addIfFound("__package__")  # ,defaultPackage)
            _addIfFound("__file__")

            if len(parentObj) == 1:
                for name, value in dataSrc.items():
                    if value != moduleSrc and str(value).startswith("<module "):
                        _appendModuleInfos(
                            value,
                            (treePosition + "." + name) if treePosition else name,
                            dest,
                        )
        except Exception as ee:
            parentObj["error"] = f"⚠️  [Other]: {ee}"

        dest.append(parentObj)

    for key, value in sys.modules.items():
        if doFilter:
            txt = str(value)
            if txt.endswith("built-in)>"):
                continue
            if txt.endswith("(frozen)>"):
                continue
            if "from '/usr" in txt:
                continue
            if "<class 'typing." in txt:
                continue
            if ".venv/" in txt:
                continue
        _appendModuleInfos(value, key, moduleList)

    return moduleList


def _modulesListAsPackageTree(moduleList: list[dict[str, Any]]) -> dict[str, Any]:

    packages: dict[str, Any] = {}
    for entry in moduleList:
        leaf: str | None = entry.get("leaf", None)
        leafTrail: list[str] = leaf.split(".") if leaf else []

        if leaf == entry.get("package"):
            if not entry.get("file"):
                # Namespace noted : entry['namespace-noted']=True
                entry.pop("package", None)
            elif str(entry.get("file")).endswith("__init__.py"):
                # Init noted :  entry['init-noted']=True
                entry.pop("package", None)
            else:
                entry["WTH?"] = True
        elif ".".join(leafTrail[:-1]) == entry.get("package"):
            # Package noted: entry['package-noted']=True
            entry.pop("package", None)
        entry.pop("leaf", None)
        prevEntry = DictUtils.get(packages, leafTrail)
        if prevEntry:
            prevValues = {}
            for x in entry:
                if x in prevEntry:
                    prevValues[x] = prevEntry[x]
                prevEntry[x] = entry[x]
            if prevValues:
                if "_prev" in prevEntry:
                    prevEntry["_prev"] = []

                prevEntry["_prev"].append(prevValues)

        else:
            DictUtils.set(packages, leafTrail, entry)

    return packages


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
    def __init__(self, objToWalk, baseOptions: dict[str, Any] | None = None):
        self.baseOptions = baseOptions

    def isSkipping(self, walkingOptions: dict[str, Any]) -> bool:
        return bool(walkingOptions.get("skip"))

    def setSkipping(self, walkingOptions: dict[str, Any]):
        walkingOptions["skip"] = True

    def doEntryReview(self, walkedEntry: WalkedEntry, walkingOptions: dict[str, Any]):
        # < Returns: (Bool)=No child iteration
        # < The walkingOptions options will be passed to children & later siblings only
        # < Use 'skip'=True to skip the children/later siblings
        appLog.print_verbose(
            "WalkTree. Reviewing: "
            + walkedEntry.asText()
            + f"  Walking Options:{walkingOptions}   BaseOptions:{self.baseOptions}"
        )

    def onEntryIterationCompleted(
        self, walkedEntry: WalkedEntry, walkingOptions: dict[str, Any]
    ):
        appLog.print_verbose(
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


class WalkTreeAction_substituteFileEntry(IWalkTreeAction_Interface):
    def doEntryReview(self, walkedEntry: WalkedEntry, walkingOptions: dict[str, Any]):
        entry = walkedEntry.entry

        if walkedEntry.isSettable() and isinstance(entry, dict) and entry.get("file"):
            file = str(entry.pop("file", ""))

            if Options.getBoolOrFalse(self.baseOptions, "useRealPaths"):
                file = os.path.realpath(file)

            isDir = False
            if file.endswith(os.sep + "__init__.py"):
                file = file.removesuffix("__init__.py")
                isDir = True
            if len(entry) == 0:
                walkedEntry.setValue(file)
            elif isDir:
                walkedEntry.setValue({"location": file, "parts": entry})
            else:
                walkedEntry.setValue({"file": file, "parts": entry})


class WalkTreeAction_removePathPrefix(IWalkTreeAction_Interface):
    def doEntryReview(self, walkedEntry: WalkedEntry, walkingOptions: dict[str, Any]):
        # appLog.print_always("WalkTreeAction_removePathPrefix. Reviewing: "+walkedEntry.asText()+f"  Walking Options:{walkingOptions}   BaseOptions:{self.baseOptions}")

        pathPrefixWithTrailingSlash = Options.getStr(
            walkingOptions, "pathPrefixWithTrailingSlash", ""
        )
        logThis = Options.getBoolOrFalse(self.baseOptions, "logThis")

        entry = walkedEntry.entry
        if isinstance(entry, dict) and "location" in entry:
            location = entry["location"]
            if location and type(location) is str:
                walkingOptions["pathPrefixWithTrailingSlash"] = entry["location"]
                return

        if walkedEntry.parent().key == "parts" and pathPrefixWithTrailingSlash:
            walkingOptions["pathPrefixWithTrailingSlash"] = (
                walkingOptions["pathPrefixWithTrailingSlash"]
                + walkedEntry.key
                + os.path.sep
            )

        if isinstance(entry, str) and walkedEntry.key not in ["location"]:
            hasRemoved, newValue = Utils.hasRemovedPrefix(
                entry, pathPrefixWithTrailingSlash
            )
            if hasRemoved:
                walkedEntry.setValue(newValue)
            else:
                hasRemoved, newValue = Utils.hasRemovedSuffix(
                    entry, os.path.sep + "__init__.py"
                )
                if hasRemoved:
                    walkedEntry.setValue(newValue + os.path.sep)
                else:
                    walkedEntry.setValue(entry)  # + "|"+pathPrefixWithTrailingSlash)
            return
        elif isinstance(entry, dict) and "file" in entry and type(entry["file"]) is str:
            _fname = entry["file"]
            hasRemoved, newValue = Utils.hasRemovedSuffix(
                _fname, os.path.sep + "__init__.py"
            )
            if hasRemoved:
                entry.pop("file", None)
                walkingOptions["pathPrefixWithTrailingSlash"] = entry["location"]

    def onEntryIterationCompleted(
        self, walkedEntry: WalkedEntry, walkingOptions: dict[str, Any]
    ):

        if self.isSkipping(walkingOptions):
            return

        if type(walkedEntry.entry) is dict:
            simplify = True
            # appLog.print_always("WalkTreeAction_removePathPrefix. Completed: "+str(walkedEntry.entry.keys()) )#+f"  Walking Options:{walkingOptions}   BaseOptions:{self.baseOptions}")
            for key, value in walkedEntry.entry.items():
                if value != key + ".py":
                    simplify = False
                    # appLog.print_always(f" ** NO : {key}:{value}")
                    break

            if simplify:
                # appLog.print_always(f" ** YES ")
                walkedEntry.setValue(list(walkedEntry.entry.keys()))


def sysModules_review(
    doFilter: bool = True, useRealPaths: bool = True
) -> Tuple[dict[str, Any], str | None]:
    """Returns packages, projDir"""

    moduleList: list[dict[str, Any]] = _sysModules_asList(doFilter=doFilter)

    packages = _modulesListAsPackageTree(moduleList)

    WalkTreeAction_substituteFileEntry({"useRealPaths": useRealPaths}).walkTree(
        packages
    )

    mainDirWithTrailingSlash: str | None = None
    if "__main__" in packages and isinstance(packages["__main__"], str):
        mainDirWithTrailingSlash = (
            str(Path(packages["__main__"]).parent).removesuffix(os.path.sep)
            + os.path.sep
        )
        packages["__main__"] = packages["__main__"].removeprefix(
            mainDirWithTrailingSlash
        )

    walkOptions: dict[str, Any] = {"logThis": True}
    if mainDirWithTrailingSlash:
        walkOptions["pathPrefixWithTrailingSlash"] = mainDirWithTrailingSlash

    WalkTreeAction_removePathPrefix({"useRealPaths": useRealPaths}).walkTree(packages)

    return packages, mainDirWithTrailingSlash


def pyInfo_asDict():

    packages: dict[str, Any] | str = {}

    packages, mainDir = sysModules_review(doFilter=True, useRealPaths=True)

    results: dict[str, Any] = {
        "python": sys.version,
        "platform": sys.platform,
        "executable": sys.executable,
    }

    if mainDir:
        results["mainDir"] = mainDir

    results["packages"] = packages

    return results


if __name__ == "__main__":

    obj = Utils.makeJsonable(pyInfo_asDict())
    print(Utils.asJsonStr(obj, indent=2))
