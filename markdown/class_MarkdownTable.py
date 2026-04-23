from copy import deepcopy
import os
import sys
from pathlib import Path
from typing import Any, Sequence, Union, Tuple


################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.appSupport import appLog
from ukko_pylibs.basic.simpleUtils import Utils
import ukko_pylibs.basic.fileUtils as fileUtils
from ukko_pylibs.basic.class_HandledException import HandledException

#
################################################################################


def md_heading_prefix(level: int | None = None) -> str:
    level_ = level if level is not None else 1
    return "#" * level_ + " "


def md_make(text: str) -> str:
    return text.replace("\n", " ").strip().replace("#", "\\#")


def md_literalQuote(text: str, quoteRequested: bool = True) -> str:
    quoteMark = "`" if quoteRequested else ""
    return f"{quoteMark}{text}{quoteMark}"


def UniLen_approx(s: str) -> int:
    # A simple approximation of the display width of a string, treating wide characters as 2 and narrow as 1
    # This is not perfect but should work reasonably well for most cases
    width = 0
    for ch in s:
        if ch in ["🔒", "🔓", "❌", "✅", "⚠️", "ℹ️", "❓", "⭐"]:
            width += 2
        else:
            width += 1
    return width


def objToMarkdownText(srcObj: dict, txtPrefix: str = "") -> str:
    out_notes = txtPrefix
    try:
        for key in srcObj:
            if key != "note" and key != "":
                prefix = "**" + key + "** = "
            else:
                prefix = ""

            value = srcObj[key]
            if value == "[Value]":
                valueTxt = value
            elif isinstance(value, dict):
                valueTxt = f"`{Utils.asJsonStr(srcObj[key])}`"
            else:
                valueTxt = str(value)

            if out_notes != "":
                out_notes += " ; "
            out_notes += f"{prefix}{valueTxt}"
    except Exception as ee:
        out_notes += f"+Exception {ee}"
    return out_notes


allMarkdownElements = {}


class MarkdownElementsCache:
    @staticmethod
    def doClear():
        allMarkdownElements.clear()

    @staticmethod
    def getValues():
        return allMarkdownElements.values()

    @staticmethod
    def ensureAllExported() -> list[Tuple[str, str]]:
        results: list[Tuple[str, str]] = []
        for entry in MarkdownElementsCache.getValues():
            if not entry.hasOwner() and not entry.getIsExported():
                txtOrNone = entry.doExport()

                if txtOrNone is not None:
                    results.append(
                        (
                            f"Exported Toplevel Markdown: {entry.getSaveLocationAndDepth()[0]}",
                            txtOrNone,
                        )
                    )

        #  Review afterwards, to give all a chance to get exported
        for entry in MarkdownElementsCache.getValues():
            if not entry.getIsExported():
                appLog.print_warning(
                    f"Not saved:[uid:{entry.spec.uid:<100}]:  Exporting to {entry.spec.getSaveLocationAndDepth()[0]}"
                )

        return results

    @staticmethod
    def getAllAsMarkdown() -> str:
        md_all = ""

        for entry in MarkdownElementsCache.getValues():
            if not entry.hasOwner():
                md_this = entry.getMarkdown().strip()
                if md_this != "":
                    if md_all != "":
                        md_all += "\n"

                    md_all += md_this + "\n"
        return md_all


class IMarkdownElement:
    class Spec:

        def __init__(
            self,
            namePart: str | None = None,
            simpleFullCaption: str = "",
            suggestedExportLocation: str = "",
            owner: Union["IMarkdownElement", None] = None,
            uid: str | None = None,
        ):
            namePart_txt = (
                namePart
                if namePart is not None
                else f"Unnamed_{len(allMarkdownElements)+1}"
            )
            if owner is None:
                pass
            self.owner = owner
            self.suggestedExportLocation: str = suggestedExportLocation

            self.namePart: str = namePart_txt
            self.simpleFullCaption: str = simpleFullCaption

            if namePart_txt.startswith("$"):
                self.refName = namePart_txt
            elif " : $" in namePart_txt:
                self.refName = "$" + namePart_txt.split(" : $")[1]
            else:
                self.refName = None

            if (uid is None) or uid == "":

                if self.refName is not None:
                    uid = f"{self.getSaveLocationAndDepth(includeRootPath=False)[0]}={self.refName}"
                elif owner is not None:
                    uid = owner.spec.uid + " | " + str(namePart_txt)
                else:
                    uid = f"{self.getSaveLocationAndDepth(includeRootPath=False)[0]}={namePart}"

            self.uid: str = uid

        def getSaveLocationAndDepth(
            self, includeRootPath: bool = True
        ) -> Tuple[str, int]:
            pos = self
            depth = 0
            path = ""
            while pos is not None:
                depth += 1
                path = pos.___getSuggestedFilepath(includeRootPath)
                pos = pos._getParentSpec()
            return (path, depth)

        def ___getSuggestedFilepath(
            self, includeRootPath: bool = True, onlyActualFile: bool = False
        ) -> str:
            pos: Union["IMarkdownElement.Spec", None] = self

            fname = ""
            while pos is not None:
                if (fname == "") and not " " in pos.namePart:
                    fpart = fileUtils.filenameSanitise(pos.namePart.split(":"))
                else:
                    fpart = fileUtils.filenameSanitise(pos.namePart)

                if fname == "":
                    fname = fpart + ".md"
                else:
                    fpart = fileUtils.filenameSanitise(pos.namePart)
                    fname = fpart + "/" + fname

                if onlyActualFile:
                    return ""
                pos = pos._getParentSpec()

            if (fname != "") and includeRootPath:
                fname = (self.suggestedExportLocation.removesuffix("/") + "/") + fname
            return fname

        def getHeritage(self) -> list[str]:
            result: list[str] = []

            pos = self

            while pos is not None:
                result.append(pos.namePart)
                if pos.namePart.startswith("$"):
                    break
                pos = pos._getParentSpec()
            return result

        def _getParentSpec(self) -> Union["IMarkdownElement.Spec", None]:
            if self.owner is None:
                return None
            else:
                return self.owner.spec

        def asDict(self) -> dict[str, Any]:
            result = {}
            includeRedundant = False

            if includeRedundant and self.namePart != "":
                result["namePart"] = self.namePart
            if self.simpleFullCaption != "":
                result["simpleFullCaption"] = self.simpleFullCaption
            if self.owner is not None:
                result["owner"] = self.owner.spec.asShortMarker()
            #    self.suggestedExportLocation != "":
            #    result["suggestedExportLocation"] = self.suggestedExportLocation
            _pathAndDepth = self.getSaveLocationAndDepth()

            result["path"] = _pathAndDepth[0]
            if _pathAndDepth[1] != 1:
                result["depth"] = _pathAndDepth[1]

            result["uid"] = self.uid
            return result

        def asShortMarker(self):
            return {
                "simpleFullCaption": self.simpleFullCaption,
                "namePart": self.namePart,
            }

    @staticmethod
    def reviewCreateOrGetCachedForLogging(
        elementOut: "IMarkdownElement", isNewlyCreated: bool
    ) -> Tuple["IMarkdownElement", bool]:
        """Returns [entry,'isNewlyCreated']"""

        # |ExtraLogging| _txt=Utils.asJsonStr(elementOut, indent=2)
        # |ExtraLogging| if ("actions.addImage" in _txt) or ('_other' in _txt):
        # |ExtraLogging|     print(f">>----------------------- [{elementOut.__class__.__name__}]")
        # |ExtraLogging|     print("Created" if isNewlyCreated else "Found")
        # |ExtraLogging|     print(_txt)
        # |ExtraLogging|     print("<<-----------------------")

        return elementOut, isNewlyCreated

    @staticmethod
    def createOrGetCached(spec: Spec) -> Tuple["IMarkdownElement", bool]:
        """Returns [entry,'isNewlyCreated']"""
        found = spec.uid in allMarkdownElements

        if not found:
            allMarkdownElements[spec.uid] = IMarkdownElement(spec)

        return IMarkdownElement.reviewCreateOrGetCachedForLogging(
            allMarkdownElements[spec.uid], not found
        )

    def __init__(self, spec: Spec):

        self.spec = spec
        self.owned: list[IMarkdownElement | str] = []
        if spec.owner is not None:
            spec.owner.owned.append(self)
        self._isExported = False  # Do not use directly - use getIsExported() instead which checks the whole ownership chain
        self.referencedByCategory: dict[str, set["IMarkdownElement"]] = {}

        _txt = Utils.asJsonStr(self, indent=2)

        appLog.print_verbose(
            f"[uid:{self.spec.uid:<100}]: Creating {self.spec.getSaveLocationAndDepth(includeRootPath=False)[0]}"
        )

    def asDict(self) -> dict[str, Any]:
        result = self.spec.asDict()
        result["type"] = self.__class__.__name__
        _isExported = self.getIsExported()
        if _isExported:
            result["isExported"] = _isExported

        if self.referencedByCategory:
            obj = {}

            for category, refList in self.referencedByCategory.items():
                obj[category] = [x.spec.asShortMarker() for x in refList]

            result["referencedBy"] = obj

        if len(self.owned) > 0:
            theList = []
            for x in self.owned:
                if isinstance(x, str):
                    theList.append(x)
                elif hasattr(x, "asDict"):
                    theList.append(x.asDict())
                else:
                    theList.append(f"type:{type(x)}")
            result["owned"] = theList

        return result

    def addChild(self, newChild: "IMarkdownElement"):
        self.owned.append(newChild)
        newChild.spec.owner = self

    def addLine(self, line: str):
        self.owned.append(line)

    def getMarkdown(self) -> str:

        md = ""

        for entry in self.owned:
            if isinstance(entry, str):
                add_this = str(entry)
            else:
                add_this = entry.getMarkdown()

            if add_this != "":
                md += add_this.removesuffix("\n") + "\n"

        if self.referencedByCategory:
            md += "\n"
            md += "# Referenced By #\n"
            for category, theSet in self.referencedByCategory.items():
                md += f"\n**{category}**:\n"
                for entry in theSet:
                    md += f" * {self.makeMarkdownLinkTo(entry,None)}\n"

        return md

    def doExport(self, onlyIfUnsaved: bool = True) -> str | None:
        isExported = self.getIsExported()
        if onlyIfUnsaved and isExported:
            return None

        fname, depth = self.spec.getSaveLocationAndDepth()

        if depth != 1:
            if isExported:
                appLog.print_info(f"Skip: Exported as part of {fname}")
            else:
                appLog.print_warning(
                    f"Skip: Not exporting to {fname} because depth={depth} (only exporting top-level elements)"
                )

            return None
        #################
        #
        md = self.getMarkdown()

        appLog.print_verbose(f"[uid:{self.spec.uid:<100}]:  Exporting to {fname}")
        try:
            Path(fname).parent.mkdir(parents=True, exist_ok=True)

            with open(fname, "w") as file:
                file.write(md)
            self._isExported = True
        except Exception as e:
            appLog.print_error(f"Failed to save markdown to {fname}: {e}")
            raise e

        return md

    def hasOwner(self) -> bool:
        return self.spec.owner is not None

    def getSaveLocationAndDepth(self) -> Tuple[str, int]:
        return self.spec.getSaveLocationAndDepth()

    def getIsExported(self) -> bool:

        pos = self
        while pos is not None:

            if pos._isExported:
                return True
            pos = pos.spec.owner
        return False

    def getSimpleCaption(self, returnIfEmpty: str | None = None) -> str:

        pos = self
        while pos is not None:

            if pos.spec.simpleFullCaption != "":
                return pos.spec.simpleFullCaption
            pos = pos.spec.owner

        return (
            "(Untitled {self.__class__.__name__})"
            if (returnIfEmpty is None)
            else returnIfEmpty
        )

    def addReferencedBy(self, category: str | None, other: "IMarkdownElement"):
        if (category is None) or (category == ""):
            return

        if not (category in self.referencedByCategory):
            self.referencedByCategory[category] = set()

        self.referencedByCategory[category].add(other)

    def makeMarkdownLinkTo(
        self,
        linkDest: "IMarkdownElement",
        refCategory: str | None,
        optionalCaption: str = "",
    ) -> str:
        return str(
            self._makeRelativeLinkTo(
                linkDest, refCategory, optionalCaption, asObj=False
            )
        )

    def _makeRelativeLinkTo(
        self,
        linkDest: "IMarkdownElement",
        refCategory: str | None,
        optionalCaption: str = "",
        asObj: bool = False,
    ) -> str | dict:
        subTableLink, _ = linkDest.spec.getSaveLocationAndDepth()

        if optionalCaption != "":
            caption = optionalCaption
        elif linkDest.spec.refName is not None:
            caption = linkDest.spec.refName
        else:
            caption = linkDest.getSimpleCaption()

        if subTableLink == "":
            return caption

        myLocation, _ = self.getSaveLocationAndDepth()

        if myLocation == subTableLink:
            return caption
        if myLocation != "":
            subTableLink = os.path.relpath(
                subTableLink, start=Path(myLocation).parent.as_posix()
            )

        linkDest.addReferencedBy(refCategory, self)

        if asObj:
            return {"text": caption, "link": subTableLink}
        else:
            return f"[{caption}]({subTableLink})"


class MarkdownTable(IMarkdownElement):
    def __init__(
        self,
        spec: IMarkdownElement.Spec,
        nameParents: str = "",
        titleKind: str = "",
        headers: Sequence[str | dict] = ["name", "value"],
        withHyperlinks: bool = True,
    ):
        IMarkdownElement.__init__(self, spec)

        self.nameParents = nameParents
        self.headersPlus = headers
        self.withHyperlinks = withHyperlinks
        self.titleKind = titleKind

        self.rows: list[list[str]] = []
        self.hideEmptyColumns = True
        self.paragraphBefore: list[str] = []
        self.extraNotes: list[str] = []
        self.footer_md = ""
        if self.spec.simpleFullCaption == "":
            self.spec.simpleFullCaption = self.getNameFull()

    def getNameFull(self, asMarkdown: bool = True) -> str:

        namePartIsLiteralQuoted = True

        txt_md = md_literalQuote(
            self.spec.namePart, namePartIsLiteralQuoted and asMarkdown
        )

        if (self.nameParents != "") and self.spec.refName is not None:
            txt_md = self.nameParents + " : " + txt_md

        return txt_md

    @staticmethod
    def createOrGetCached(
        spec: IMarkdownElement.Spec,
        nameParents: str = "",
        titleKind: str = "",
        headers: Sequence[str | dict] = ["name", "value"],
        withHyperlinks: bool = True,
    ) -> Tuple["IMarkdownElement", bool]:
        """Returns [entry,'isNewlyCreated']"""
        found = spec.uid in allMarkdownElements

        if not found:
            allMarkdownElements[spec.uid] = MarkdownTable(
                spec, nameParents, titleKind, headers, withHyperlinks
            )

        return IMarkdownElement.reviewCreateOrGetCachedForLogging(
            allMarkdownElements[spec.uid], not found
        )

    def addRow(self, row: list[str]):
        self.rows.append(row)

    def addExtraNote(self, note: str, allowDuplicates: bool = False):
        if allowDuplicates or note not in self.extraNotes:
            appLog.print_info("Adding extra note: " + note)
            self.extraNotes.append(note)

    def addToParagraphBefore(self, line: str):
        self.paragraphBefore.append(line)

    def _asStr(self, cell: Any) -> str:
        if cell is None:
            return ""
        elif isinstance(cell, str):
            return cell
        elif self.withHyperlinks and isinstance(cell, dict) and ("link" in cell):
            link = str(cell.get("link"))
            text = str(cell.get("text", link))
            return f"[{text}]({link})"
        elif isinstance(cell, dict) and ("text" in cell):
            return str(cell.get("text"))
        else:
            return Utils.asJsonStr(cell)

    def getMaxVisWidths(self) -> list[int]:
        maxWidths = [0] * len(self.headersPlus)

        for row in self.rows:
            for i, cell in enumerate(row):
                maxWidths[i] = max(maxWidths[i], UniLen_approx(self._asStr(cell)))

        for i, header in enumerate(self.headersPlus):
            if (maxWidths[i] > 0) or not self.hideEmptyColumns:
                maxWidths[i] = max(maxWidths[i], UniLen_approx(self._asStr(header)))

        return maxWidths

    def getFullCaption_md(self) -> str:
        txt_1 = self.getNameFull()
        txt_2 = self.spec.simpleFullCaption

        def generaliseText(txtIn: str) -> str:
            txt = txtIn.replace("`", "").strip().lower().strip()
            txt = txt.replace(":", " ")
            txt = txt.replace("-", " ")
            return txt

        if txt_1 == txt_2:
            return txt_1
        if txt_1 == "":
            return txt_2
        if txt_2 == "":
            return txt_1
        if generaliseText(txt_1).endswith(generaliseText(txt_2)):
            return txt_1
        return f"{txt_1} -- {txt_2}"  # < [{generaliseText(txt_1)}] [{generaliseText(txt_2)}]"

    def getMarkdown(self) -> str:
        withTitle = True

        md = ""

        if withTitle:
            txt = self.getFullCaption_md()

            if self.titleKind != "" and not self.hasOwner():
                txt = self.titleKind + ": " + txt

            saveDepth = self.getSaveLocationAndDepth()[1]
            md += f"{md_heading_prefix(saveDepth)}{txt}\n\n"

        for x in self.paragraphBefore:
            md += str(x) + "\n"

        if len(self.rows) > 0:
            visWidths = self.getMaxVisWidths()
            colsToUse = [
                i
                for i, w in enumerate(visWidths)
                if (w > 0) or not self.hideEmptyColumns
            ]

            def _formatColEntry(cell: str, visWidth: int) -> str:
                cellStr = self._asStr(cell)
                visLen = UniLen_approx(cellStr)
                if visLen > visWidth:
                    cellStr = cellStr[: visWidth - 3] + "..."
                # if len(cellStr)!= visLen:cellStr=f"{cellStr} ({visLen} chars)"
                return cellStr + " " * (visWidth - visLen)

            title = ""
            divider = ""
            for i in colsToUse:
                title += (
                    _formatColEntry(self._asStr(self.headersPlus[i]), visWidths[i])
                    + " | "
                )
                divider += "-" * visWidths[i] + "-|-"

            md += "| " + title.removesuffix(" ") + "\n"
            md += "|-" + divider.removesuffix("-") + "\n"

            for row in self.rows:
                md += "| "
                for i in colsToUse:
                    if i < len(row):
                        cell = row[i]
                    else:
                        cell = ""
                    md += _formatColEntry(cell, visWidths[i]) + " | "
                md += "\n"

        if self.extraNotes:
            md += "\nAdditional Notes:\n"
            for x in self.extraNotes:
                md += " * " + str(x) + "\n"
        md += "\n"
        return md + super().getMarkdown() + self.footer_md
