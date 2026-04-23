from copy import deepcopy
from enum import Enum
from enum import auto as EnumAuto
import os
import sys
from typing import Any, Tuple, Union

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.appSupport import appLog
import ukko_pylibs.basic.appSupport as app
import ukko_pylibs.basic.simpleUtils as simpleUtils
from ukko_pylibs.basic.simpleUtils import Utils as Utils
from ukko_pylibs.basic.class_HandledException import HandledException
from ukko_pylibs.markdown.class_MarkdownTable import (
    IMarkdownElement,
    MarkdownTable,
    MarkdownElementsCache,
    objToMarkdownText,
)
from ukko_pylibs.schemaHandling.schemaProcessing import SchemaUsageInstructions

#
################################################################################

INCLUDE_ADDITIONAL_SCHEMA_DETAILS = False


class SchemaTableAndPosition:

    def asDict(self):
        return {
            "destTable": self.destTable.spec.asShortMarker(),
            "parentNames": self.parentNames,
            "anyParentIsOptional": self.anyParentIsOptional,
        }

    def depth(self):
        return len(self.parentNames)

    def __init__(
        self,
        destTable: MarkdownTable,
        parentNames: list[str] | None = None,
        anyParentIsOptional: bool = False,
    ):
        self.parentNames = parentNames if parentNames else []
        self.anyParentIsOptional = anyParentIsOptional
        self.destTable = destTable

    def createSubTable(
        self, name: str | None, isRequired: bool
    ) -> " SchemaTableAndPosition":
        if name is None:
            name = "{Unnamed}"
        return SchemaTableAndPosition(
            self.destTable,
            self.parentNames + [name],
            self.anyParentIsOptional or not isRequired,
        )

    @staticmethod
    def getTable(src: Union["SchemaTableAndPosition", None]) -> MarkdownTable | None:
        if src is None:
            return None
        return src.destTable

    def getParentsAsText(self) -> str:

        name_to_use = ""

        for parentName in self.parentNames:
            name_to_use += parentName + " » "

        return name_to_use


@staticmethod
def SchemaTableAndPosition_createNew(
    spec, docKind, withHyperlinks
) -> Tuple[SchemaTableAndPosition, bool]:
    """Returns [value, tableIsNewlyCreated]"""
    _destEntry, isNewlyCreated = MarkdownTable.createOrGetCached(
        spec,
        titleKind=docKind,
        headers=[
            "Req",
            "Name",
            {"text": "Type", "generateHyperlinks": True},
            "Description",
            "Notes",
        ],
        withHyperlinks=withHyperlinks,
    )
    if (_destEntry is None) or (not isinstance(_destEntry, MarkdownTable)):
        raise TypeError(f"Expected MarkdownTable - got {type(_destEntry).__name__}")

    return SchemaTableAndPosition(_destEntry), isNewlyCreated


class SchemaEntry:
    @staticmethod
    def refToFriendlyName(ref: str) -> str:
        return (
            ref.removeprefix("ref: ")
            .removeprefix("parts/")
            .removesuffix(".json")
            .replace("/", " » ")
        )

    def __init__(self, srcObj: dict[str, Any]):
        self.srcObj_orig = deepcopy(srcObj)
        self.srcObj = deepcopy(self.srcObj_orig)
        self.comment = self.srcObj.pop("$comment", None)
        self.refId = (
            self.refToFriendlyName(str(self.comment))
            if self.comment is not None
            else None
        )
        self.type = self.srcObj.pop("type", None)
        self.properties = self.srcObj.pop("properties", None)
        self.oneOf = self.srcObj.pop("oneOf", None)
        self.description = self.srcObj.pop("description", "")

    def typeAsStr(self) -> str:
        if self.isSubtable(True) and self.refId is not None:
            return str(self.refId)
        elif self.type is not None:
            txt = str(self.type)
        elif self.oneOf is not None:
            if len(self.oneOf) == 1:
                txt = SchemaEntry(self.oneOf[0]).typeAsStr()
            else:
                txt = f"One of {len(self.oneOf)} options"
        elif isinstance(self.properties, dict):
            if len(self.properties) == 0:
                txt = "(Empty Object)"
            else:
                txt = "(Object)"
        else:
            txt = "{Unknown Type}"

        if self.refId is not None and (INCLUDE_ADDITIONAL_SCHEMA_DETAILS):
            txt = f"{self.refId}: {txt}"
        return txt

    def typeIs(self, types: Union[str, list[str]]) -> bool:
        if self.type is None:
            return False
        if isinstance(types, str):
            return self.type == types
        else:
            return self.type in types

    def toLine_md(self, prefix_in: str | None = None) -> str:
        txt = ""
        if prefix_in is not None:
            prefix_used = prefix_in
        else:
            prefix_used = self.type if str(self.type) is not None else "{Unknown Type}"
        try:
            return objToMarkdownText(self.srcObj, prefix_used)

        except Exception as ee:
            txt += f"+Exception {ee}"
        return txt

    def createNewFromRemaining(self) -> "SchemaEntry":
        result = self.cloneFromOrig()
        result.srcObj_orig = self.srcObj
        result.srcObj = self.srcObj
        return result

    def cloneFromOrig(self) -> "SchemaEntry":
        return SchemaEntry(self.srcObj_orig)

    def doPop(self, key: str, default: Any = None) -> Any:
        return self.srcObj.pop(key, default)

    def isOneOf(self) -> bool:
        return self.oneOf is not None

    def isSubtable(self, includeOneOf: bool) -> bool:

        is_object = self.type == "object"

        if isinstance(self.properties, dict) and (len(self.properties) == 0):
            if (len(self.srcObj) == 2 and is_object) or (len(self.srcObj) == 1):
                return False  # < Totally empty object

        if is_object or (self.properties is not None):
            return True
        if includeOneOf and (self.oneOf is not None):
            return True
        return False

    def getLimits(
        self, minKey: str, maxKey: str, name: str, quoteValuesWith: str = "`"
    ) -> Tuple[str, Any | None]:

        def quoteIfNeeded(val: Any) -> str:
            return f"{quoteValuesWith}{val}{quoteValuesWith}"

        min = self.doPop(minKey)
        max = self.doPop(maxKey)

        exactValue = None
        if (min is None) and (max is None):
            lenLimitTxt = ""
        elif (min is not None) and (max is None):
            lenLimitTxt = f"{name} ≥ {quoteIfNeeded(min)}"
        elif (max is not None) and (min is None):
            lenLimitTxt = f"{name} ≤ {quoteIfNeeded(max)}"
        elif min == max:
            lenLimitTxt = f"{name}={quoteIfNeeded(min)} exactly"
            exactValue = min
        else:
            lenLimitTxt = f"{name}={quoteIfNeeded(min)} … {quoteIfNeeded(max)}"

        example = self.doPop("example")
        if example is not None:
            exampleStr = "eg: " + Utils.asJsonStr(example)

            if lenLimitTxt != "":
                lenLimitTxt = f"{lenLimitTxt} ({exampleStr})"
            else:
                lenLimitTxt = exampleStr

        const = self.doPop("const")
        if const is not None:
            constStr = f"Always {quoteIfNeeded(const)}"
            exactValue = const
            if lenLimitTxt != "":
                lenLimitTxt = f"{lenLimitTxt} | {constStr}"
            else:
                lenLimitTxt = constStr
        return lenLimitTxt, exactValue


class NewTableLocation(Enum):
    IN_SAME_MARKDOWN_FILE = EnumAuto()
    IN_NEW_MARKDOWN_FILE = EnumAuto()
    AS_SUBTABLE = EnumAuto()
    AS_FULLTABLE = EnumAuto()


def createTableForSchema(
    options: "MarkdownSchemaDoc",
    tableName: str | None,
    schemaEntry_in: SchemaEntry | dict[str, Any],
    owner: IMarkdownElement | None,
    docKind: str = "",
    required: bool = False,
) -> SchemaTableAndPosition:

    return jsonSchemaAddEntry(
        options, owner, schemaEntry_in, docKind, tableName, required
    )


def jsonSchemaAddEntry(
    options: "MarkdownSchemaDoc",
    destOrCreateWithOwnerOrNone: SchemaTableAndPosition | IMarkdownElement | None,
    schemaEntry_in: SchemaEntry | dict[str, Any],
    docKind: str = "",
    name_in: str | None = "[Value]",
    required: bool = False,
) -> SchemaTableAndPosition:
    dest: SchemaTableAndPosition
    if isinstance(schemaEntry_in, dict):
        dataToAdd = SchemaEntry(schemaEntry_in)
    else:
        dataToAdd = schemaEntry_in.cloneFromOrig()

    out_name = (
        str(docKind)
        + ("" if docKind == "" else ": ")
        + ("" if not name_in else str(name_in))
    )
    out_type = dataToAdd.typeAsStr()
    out_description: str = dataToAdd.description
    out_notes: str = ""

    def jsonSchemaAddDirect(addTo: SchemaTableAndPosition):
        out_type = dataToAdd.typeAsStr()
        notes = [out_notes]

        try:

            id = dataToAdd.doPop("$id")
            if (id is not None) and (
                id != f"parts/{addTo.destTable.spec.namePart}.json"
            ):
                addTo.destTable.addExtraNote(f"⚠️ id : {id}'", allowDuplicates=False)

            ####################################
            # Now do the subtable contents
            #
            if dataToAdd.isOneOf():
                addTo.destTable.addToParagraphBefore(
                    f"One of {simpleUtils.pluralize(len(dataToAdd.oneOf), 'option')}:"
                )
                for i, option in enumerate(dataToAdd.oneOf):
                    optionName = str(option.pop("description", f"Option {i+1}"))
                    if SchemaEntry(option).isSubtable(includeOneOf=True):
                        tableAndPosition = createTableForSchema(
                            options, optionName, option, owner=addTo.destTable
                        )
                        addTo.destTable.addToParagraphBefore(
                            f" * {addTo.destTable.makeMarkdownLinkTo(tableAndPosition.destTable,'Option')}"
                        )
                    else:
                        addTo.destTable.addToParagraphBefore(
                            f" * {SchemaEntry(option).toLine_md()}"
                        )

                addTo.destTable.addToParagraphBefore("")
                return
            elif dataToAdd.isSubtable(includeOneOf=False):
                _properties = dataToAdd.properties
                if _properties is None:
                    return  # < No properties - so nothing to add to the table
                if not isinstance(_properties, dict):
                    raise TypeError(
                        f"Expected 'properties' to be a dict - not a {type(_properties).__name__}"
                    )

                _required = dataToAdd.doPop("required", [])
                if len(_properties) > 0:

                    _additionalProperties = dataToAdd.doPop(
                        "additionalProperties", True
                    )

                    if isinstance(_additionalProperties, bool):
                        if _additionalProperties:
                            _properties["{other}"] = {
                                "note": f"Additional properties are permitted - no checks will be applied",
                                "type": "",  # < Don't want to say 'any' as that implies something about the type, which is not necessarily the case
                            }
                    elif isinstance(_additionalProperties, dict):
                        _properties["{other}"] = _additionalProperties
                    else:
                        _properties["{other}"] = {"type": str(_additionalProperties)}
                    for key in _properties:
                        if key in _required:
                            key_is_required = True
                            _required.remove(key)
                        else:
                            key_is_required = False

                        subEntry = _properties[key]
                        jsonSchemaAddEntry(
                            options,
                            addTo,
                            SchemaEntry(subEntry),
                            name_in=key,
                            required=key_is_required,
                        )

                    if len(_required) > 0:
                        msg = f"Required properties not listed in schema: {', '.join(_required)}"
                        addTo.destTable.addExtraNote("⚠️ " + msg, allowDuplicates=False)
                return
            #
            # A simple type now
            #
            enumList = dataToAdd.doPop("enum")
            if enumList is not None:
                if isinstance(enumList, list):
                    notes += ["One of: " + ", ".join([f"**{x}**" for x in enumList])]
            if dataToAdd.typeIs(["number", "integer"]):
                lenLimitTxt, _ = dataToAdd.getLimits("minimum", "maximum", "Value")

                notes += [lenLimitTxt]
            elif dataToAdd.typeIs("string"):
                lenLimitTxt, _ = dataToAdd.getLimits("minLength", "maxLength", "Length")

                notes += [lenLimitTxt]
            elif dataToAdd.typeIs("array"):
                arrayItemsType = dataToAdd.doPop("items")

                minItems = dataToAdd.doPop("minItems")
                maxItems = dataToAdd.doPop("maxItems")
                if arrayItemsType is not None:
                    out_type = arrayItemsType.pop("type", "<Unknown Type>")

                    if len(arrayItemsType) > 0:
                        extras = "Array items: ["
                        for key in arrayItemsType:
                            extras += f"{key}={arrayItemsType[key]} "
                        extras += "]"
                        notes += [extras]
                else:
                    out_type = "❓"
                if (
                    (minItems is not None)
                    and (maxItems is not None)
                    and (minItems == maxItems)
                ):
                    exactLength = minItems
                    out_type = f"[{out_type}] x {exactLength}"
                else:
                    out_type = f"[{out_type} ...]"
                    notes += [Utils.rangeAsText(minItems, maxItems, "Array length: ")]

        except Exception as e:
            appLog.print_warning_withException(e)
            addTo.destTable.addExtraNote(f"⚠️ Error processing schema entry: {str(e)}")

        _doAppendToTable(
            out_name,
            out_type,
            out_description,
            "; ".join([note for note in notes if note != ""]),
        )
        return

    def doCreateNewTable(
        owner: IMarkdownElement | None, name_to_use: str
    ) -> Tuple[SchemaTableAndPosition, bool]:
        if owner is None:
            pass
        """Returns [value, tableIsNewlyCreated]"""
        location = options._getSuggestedExportLocation(
            "parts" if name_to_use.startswith("$") else "_other"
        )
        spec = IMarkdownElement.Spec(
            name_to_use, out_description, location, owner=owner
        )

        dest_, destIsNewlyCreated_ = SchemaTableAndPosition_createNew(
            spec, docKind, withHyperlinks=options.isExporting()
        )

        return dest_, destIsNewlyCreated_

    def _doAppendToTable(
        out_name: str,
        out_type: str,
        out_description: str,
        out_notes: str,
        summariseExtras: bool = True,
        forceOutRequired: str | None = None,
    ) -> SchemaTableAndPosition:

        def markdown_boldIfNotEmpty(txt: str) -> str:
            if txt != "":
                return f"**{txt}**"
            else:
                return txt

        if forceOutRequired is not None:
            out_required = forceOutRequired
        elif not (required):
            out_required = " "
        elif dest.anyParentIsOptional:
            out_required = "🔓"
        else:
            out_required = "🔒"

        if summariseExtras:
            out_notes = dataToAdd.toLine_md(out_notes)
        if out_type is not None:
            out_type = out_type.removeprefix("Interface Specification: parts/")

        if out_name == "queueLength":
            pass

        dest.destTable.addRow(
            [
                out_required,
                markdown_boldIfNotEmpty(f"{dest.getParentsAsText()}{out_name}"),
                out_type,
                "" if (out_description == out_type) else out_description,
                out_notes,
            ]
        )
        return dest

    name_to_use = name_in
    if (
        (name_in is None)
        or (not name_in.startswith("$") and (" " in name_in))
        and (out_description != "")
        and not (" " in out_description)
    ):
        name_to_use = out_description
    else:
        name_to_use = name_in
    if False:
        import json

        print("---------v")
        if docKind:
            print(f"Input titleKind: {docKind}")
        print(f"name_in    : {name_in}")
        if out_description:
            print(f"description: {out_description}")
        if destOrCreateWithOwnerOrNone is not None:
            print(
                f"destination: {json.dumps(destOrCreateWithOwnerOrNone.asDict(), indent=2)}"
            )
        print(f"name_to_use: {name_to_use}")

        print(f"dataToAdd: {json.dumps(dataToAdd.srcObj, indent=2)}")
        print("---------^")

    destIsNewlyCreated = False
    if (destOrCreateWithOwnerOrNone is None) or isinstance(
        destOrCreateWithOwnerOrNone, IMarkdownElement
    ):
        dest, destIsNewlyCreated = doCreateNewTable(
            destOrCreateWithOwnerOrNone, name_to_use
        )

        if not destIsNewlyCreated:
            return dest
    else:
        dest = destOrCreateWithOwnerOrNone
    try:
        if not dataToAdd.isSubtable(includeOneOf=True):
            jsonSchemaAddDirect(dest)
        else:
            suggestInSameMarkdownFile = True
            if dataToAdd.doPop("_includeInTable"):
                suggestInSameMarkdownFile = True
            if dataToAdd.doPop("_includeInParent"):
                suggestInSameMarkdownFile = True

            if destIsNewlyCreated:
                newTableLocation = NewTableLocation.AS_FULLTABLE
            elif dataToAdd.refId is not None:
                newTableLocation = (
                    NewTableLocation.IN_NEW_MARKDOWN_FILE
                    if options.isExporting()
                    else NewTableLocation.IN_SAME_MARKDOWN_FILE
                )
            elif dest.depth() < options.MAX_SUBTABLES - 1:
                newTableLocation = NewTableLocation.AS_SUBTABLE
            elif suggestInSameMarkdownFile:
                newTableLocation = NewTableLocation.IN_SAME_MARKDOWN_FILE
            else:
                newTableLocation = NewTableLocation.IN_NEW_MARKDOWN_FILE

            ##########################
            # AS_SUBTABLE
            #
            if newTableLocation is NewTableLocation.AS_SUBTABLE:
                if not dataToAdd.isOneOf():
                    _doAppendToTable(
                        out_name,
                        "" if out_type == "object" else out_type,
                        out_description,
                        out_notes,
                        summariseExtras=False,
                    )

                    dest = dest.createSubTable(out_name, required)
                    jsonSchemaAddDirect(dest)
                else:
                    outEntry_md = out_type + ":"

                    if out_notes != "":
                        outEntry_md += " ; " + out_notes
                    _doAppendToTable(
                        out_name,
                        "",
                        "",
                        outEntry_md,
                        summariseExtras=False,
                    )
                    for i, option in enumerate(dataToAdd.oneOf):
                        optionName = str(option.pop("description", f"Option {i+1}"))

                        optionName_short = optionName
                        if optionName.endswith("]"):
                            optionName_short = (
                                optionName.rsplit("[", 1)[-1].strip().removesuffix("]")
                            )
                        else:
                            optionName_short = out_name + "[" + optionName + "]"
                        if SchemaEntry(option).isSubtable(includeOneOf=True):
                            tableAndPosition = createTableForSchema(
                                options, optionName, option, owner=dest.destTable
                            )
                            optionEntry_md = f"{dest.destTable.makeMarkdownLinkTo(tableAndPosition.destTable,'Option',optionName_short)}"
                        else:
                            optionEntry_md = optionName_short

                        outEntry_md = "" if out_notes == "" else out_notes + " ; "
                        outEntry_md += " • " + optionEntry_md

                        _doAppendToTable(
                            "",
                            "",
                            "",
                            outEntry_md,
                            summariseExtras=False,
                            forceOutRequired=" ",
                        )
            else:
                new_name = dest.getParentsAsText() + out_name
                if dataToAdd.refId is not None:
                    new_name += f" : {dataToAdd.refId}"
                if newTableLocation is NewTableLocation.IN_SAME_MARKDOWN_FILE:
                    subLocation, subLocationIsNewlyCreated = doCreateNewTable(
                        dest.destTable, new_name
                    )
                elif newTableLocation is NewTableLocation.IN_NEW_MARKDOWN_FILE:
                    subLocation, subLocationIsNewlyCreated = doCreateNewTable(
                        None,
                        dataToAdd.refId if dataToAdd.refId is not None else new_name,
                    )
                else:
                    subLocation = dest
                    subLocationIsNewlyCreated = destIsNewlyCreated
                if subLocationIsNewlyCreated:
                    jsonSchemaAddDirect(subLocation)
                if not destIsNewlyCreated:
                    _doAppendToTable(
                        out_name,
                        dest.destTable.makeMarkdownLinkTo(
                            subLocation.destTable, out_type
                        ),
                        out_description,
                        out_notes,
                        summariseExtras=False,
                    )
    except Exception as e:
        appLog.print_warning_withException(e)
        dest.destTable.addExtraNote(f"⚠️ Error processing schema entry: {str(e)}")
        _doAppendToTable(
            out_name,
            dataToAdd.typeAsStr(),
            out_description,
            out_notes,
            summariseExtras=True,
        )
    return dest


class MarkdownSchemaDoc:
    def __init__(
        self,
        schemaShow: dict[str, Any],
        kind: str = "",
        _exportFolder: str = "",
        namePartIsLiteralQuoted: bool = False,
    ):
        self.schemaCollection = schemaShow
        self.docKind = kind
        self.exportFolder = _exportFolder
        self.MAX_SUBTABLES = 4
        self.namePartIsLiteralQuoted = namePartIsLiteralQuoted

        MarkdownElementsCache.doClear()

    def isExporting(self) -> bool:
        return self.exportFolder != ""

    def _getSuggestedExportLocation(self, topDir: str = "") -> str:
        path = f"{self.exportFolder if self.isExporting() else '_generated_markdown'}/{topDir}/".replace(
            "//", "/"
        )
        return path

    def _createMarkdownFile(
        self, namePart: str, topDir: str = "", owner: IMarkdownElement | None = None
    ) -> Tuple[IMarkdownElement, bool]:
        value, isNewlyCreated = IMarkdownElement.createOrGetCached(
            IMarkdownElement.Spec(
                namePart=namePart,
                simpleFullCaption=namePart,
                owner=owner,
                suggestedExportLocation=self._getSuggestedExportLocation(topDir),
            )
        )

        if isNewlyCreated:
            quotes = "`" if self.namePartIsLiteralQuoted else ""
            value.addLine(f"# {self.docKind}: {quotes}{namePart}{quotes}")

        return value, isNewlyCreated

    def _makeSchemasPlus(
        self,
        part,
        partSchema: list[dict[str, Any]] | dict[str, Any],
        parent: IMarkdownElement | None = None,
        prettifyCaption: bool = False,
    ) -> IMarkdownElement | None:
        returnValue: IMarkdownElement | None = None
        if isinstance(partSchema, dict):
            returnValue = self.fullSchemaToTable(partSchema, owner=parent)
            if prettifyCaption:
                returnValue.spec.simpleFullCaption = (
                    returnValue.spec.simpleFullCaption.split(":")[-1].strip().title()
                )
                # outTable.titleKind=''
        elif isinstance(partSchema, list):
            returnValue, isNewlyCreated = self._createMarkdownFile(
                part, "fullQueries", owner=parent
            )
            if isNewlyCreated:
                n = 0
                for x in partSchema:
                    self._makeSchemasPlus(
                        f"{part}[{n}]", x, parent=returnValue, prettifyCaption=True
                    )
                    n += 1
            else:
                appLog.print_warning(f"Expected newlyCreatedValue: {part}")
        else:
            appLog.print_warning(
                f"Unknown schema type for part {part}: {type(partSchema).__name__}"
            )
        return returnValue

    def makeLinesPlus(self) -> list[Tuple[str, str]]:
        """return list[User Message, markdownContents]"""
        summary: IMarkdownElement | None

        if self.isExporting():
            appLog.print_verbose("Outputs exported to: " + self.exportFolder)
            summary, _isNewlyCreated = self._createMarkdownFile("Communication Queries")
        else:
            summary = None
        # |else:
        # |    summary,_isNewlyCreated=self._createMarkdownFile("All Tables")

        for part, partSchema in self.schemaCollection.items():
            entry = self._makeSchemasPlus(part, partSchema, None)
            if (entry is not None) and (summary is not None):
                summary.addLine(
                    f" * {summary.makeMarkdownLinkTo(entry,'Communications')}"
                )

        results = []
        if self.isExporting():
            results += MarkdownElementsCache.ensureAllExported()
        else:
            md = self.dumpAllTables()

            results.append(("", md))

        return results

    def dumpAllTables(self) -> str:
        return MarkdownElementsCache.getAllAsMarkdown()

    def fullSchemaToTable(
        self, __srcObj: dict[str, Any], owner: IMarkdownElement | None = None
    ) -> MarkdownTable:
        """Returns the table created from the schema, and the remaining properties that were not processed (if any)
        * srcObj.usageInstructions
        * srcObj.jSchema
        * srcObj.name
        * srcObj.$comment
        * srcObj.[anything else] -> added as extra notes to the table"""
        srcObj = deepcopy(__srcObj)

        name = srcObj.pop("name", None)
        usageInstructions = SchemaUsageInstructions(
            srcObj.pop("usageInstructions", None)
        )
        jSchema = srcObj.pop("jsonSchema", None)

        canAddProperties = (
            isinstance(jSchema, dict)
            and (jSchema.get("type") == "object")
            and isinstance(jSchema.get("properties"), dict)
        )
        dest = createTableForSchema(self, name, jSchema, owner=owner)

        # Optional: dest.destTable.footer_md = "# Full Schema Details:\n```json\n" + Utils.asJsonStr(jSchema, indent=2) + "\n```"

        for x in usageInstructions.getExtraNotesAsList(
            True
        ):  # includeBitstreamInfo=not addedBitstreamInfo):
            dest.destTable.addExtraNote(x, allowDuplicates=True)

        if "$comment" in srcObj:
            dest.destTable.addExtraNote(
                f"FullSchemaExtra[comment]: {srcObj.pop('$comment')}",
                allowDuplicates=False,
            )

        for key, value in srcObj.items():
            dest.destTable.addExtraNote(
                f"FullSchemaExtra: {key}=`{Utils.asJsonStr(value)}`",
                allowDuplicates=False,
            )

        return dest.destTable

    def dumpRemaining(self, srcObj_: dict[str, Any] | None, prefix: str = "") -> str:
        entry_md = ""
        if srcObj_ != None:
            for key, value in srcObj_.items():
                entry_md += f"{prefix}: {key}\n"
                entry_md += "```json\n"
                entry_md += Utils.asJsonStr(value, indent=2)
                entry_md += "\n```\n"

        return entry_md

    def usageRulesSchemaToMarkdown(self, srcObj_: dict[str, Any] | None) -> list[str]:
        if srcObj_ == None:
            return []

        srcObj = deepcopy(srcObj_)

        lines = []
        if "$comment" in srcObj_:
            lines.append(f"comment: {srcObj_.pop('$comment')}")

        binaryRules = srcObj.pop("binaryRules", None)
        srcObj.pop("permitRawErrorResult", None)

        if binaryRules == {"expected": True}:
            lines.append("🔒  Bitstream Payload Required")
        elif binaryRules != {"expected": False}:
            lines.append(f"usageRulesSchemaToMarkdown: binaryRules={binaryRules}")
        for key, value in srcObj.items():
            lines.append(f"Usage Rules Descriptor[{key}]: `{Utils.asJsonStr(value)}`")

        return lines
