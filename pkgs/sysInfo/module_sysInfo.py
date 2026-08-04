import os, sys
from pathlib import Path
from typing import Any, Tuple


import ukkoUtils


from appLogging import appLog
import dictUtils
import dictUtils as Options

from dictionaryWalker import WalkedEntry, IWalkTreeAction_Interface

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
        prevEntry = dictUtils.get(packages, leafTrail)
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
            dictUtils.set(packages, leafTrail, entry)

    return packages


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
            hasRemoved, newValue = ukkoUtils.hasRemovedPrefix(
                entry, pathPrefixWithTrailingSlash
            )
            if hasRemoved:
                walkedEntry.setValue(newValue)
            else:
                hasRemoved, newValue = ukkoUtils.hasRemovedSuffix(
                    entry, os.path.sep + "__init__.py"
                )
                if hasRemoved:
                    walkedEntry.setValue(newValue + os.path.sep)
                else:
                    walkedEntry.setValue(entry)  # + "|"+pathPrefixWithTrailingSlash)
            return
        elif isinstance(entry, dict) and "file" in entry and type(entry["file"]) is str:
            _fname = entry["file"]
            hasRemoved, newValue = ukkoUtils.hasRemovedSuffix(
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

    packages: dict[str, Any] | str

    packages, mainDir = sysModules_review(
        doFilter=not appLog.isVerbose(), useRealPaths=True
    )

    results: dict[str, Any] = {
        "version": sys.version,
        "platform": sys.platform,
        "executable": sys.executable,
        "packages": packages,
    }

    if mainDir:
        results["mainDir"] = mainDir

    return results


if __name__ == "__main__":

    obj = ukkoUtils.asJsonable(pyInfo_asDict())
    print(ukkoUtils.asJsonStr(obj, indent=2))
