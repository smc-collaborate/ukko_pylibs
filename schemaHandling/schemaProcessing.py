from enum import Enum
from pathlib import Path
import os, sys

import jsonschema
from typing import Any
from copy import deepcopy

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

import ukko_pylibs.app.appSupport as app
from ukko_pylibs.app.appSupport import appLog
from ukko_pylibs.basic.simpleUtils import Utils as Utils
import ukko_pylibs.basic.fileUtils as fileUtils
from ukko_pylibs.transferableData.class_ITransferableData import ITransferableData
from ukko_pylibs.basic.simpleUtils import PrettyText

#
################################################################################


#
################################################################################

WARN_ON_MISSING_SCHEMAS = True  # Set to True to warn if schemas are missing

g_app_schemasDir: str = ""


def schema_getDir(kind: str = "commands") -> str:
    """
    Get the directory path for the specified schema kind.
    """
    global g_app_schemasDir
    if g_app_schemasDir == "":
        _dir = str(Path(app.getDir("schemas")).resolve(strict=False))
        _dir2 = _dir.removesuffix("/") + "/dataDefinitions"
        g_app_schemasDir = _dir2 if os.path.exists(_dir2) else _dir
        appLog.print_verbose(
            f"{'✓' if os.path.exists(g_app_schemasDir) else '✗'} Schema directory: {g_app_schemasDir}"
        )

    return g_app_schemasDir + "/" + kind


def schema_list(kind: str = "commands") -> list[str]:
    """
    List all available schemas in the schemas directory.
    """
    schema_dir = schema_getDir(kind)
    if not os.path.exists(schema_dir):
        appLog.print_warning(f"Schema directory {schema_dir} does not exist.")
        return []

    appLog.print_verbose(f"Schema directory {schema_dir} : Reviewing ...")
    cmds = []
    for cmd in os.listdir(schema_dir):
        cmd_path = os.path.join(schema_dir, cmd)
        appLog.print_verbose(f"Reviewing: {cmd}")
        if os.path.isdir(cmd_path):
            cmds.append(cmd)
        elif cmd.endswith(".json"):
            cmds.append(cmd.removesuffix(".json"))
    return sorted(cmds)


def schema_loadRef(ref: str) -> dict[str, Any]:
    schemaElement = fileUtils.loadJson_dict(
        "@" + schema_getDir(ref), "Schema reference", exceptionOnError=False
    )
    schemaElement["$comment"] = f"ref: {ref}"

    return schemaElement


def schema_cleanElement(
    schemaElementIn: dict[str, Any] | None, isStrict: bool = True
) -> dict[str, Any] | None:
    """
    Clean up the schema by removing unnecessary fields and ensuring it is well-formed.
    """
    # |Logging| appLog.print_verbose(f"Schema cleanElement: {Utils.asJsonStr(schemaElement)}")
    if schemaElementIn is None or (not isinstance(schemaElementIn, dict)):
        return schemaElementIn
    schemaElement = schemaElementIn.copy()

    if schemaElement == {}:
        return schemaElement
    if schemaElement.get("error", None) is not None:
        return schemaElement

    #
    # Each element is:
    # "type": "object",
    # "properties": dict[str, schemaElement]
    # --"additionalProperties": false
    #
    if schemaElement.get("ref", None) is not None:
        schemaElement = schema_loadRef(schemaElement["ref"])

        if "error" in schemaElement:
            return schemaElement

    if "oneOf" in schemaElement:
        # Clean up each element in oneOf
        schemaElement["oneOf"] = [
            schema_cleanElement(item, isStrict) for item in schemaElement["oneOf"]
        ]

    if "items" in schemaElement:
        schemaElement["items"] = schema_cleanElement(schemaElement["items"], isStrict)

    if schemaElement.get("type", None) != "object":
        return schemaElement

    if "properties" in schemaElement:
        for key, value in schemaElement["properties"].items():
            schemaElement["properties"][key] = schema_cleanElement(value, isStrict)

    if (
        not (isStrict)
        and ("additionalProperties" in schemaElement)
        and (schemaElement.get("additionalProperties_PRESERVE", False) == False)
    ):
        del schemaElement["additionalProperties"]

    return schemaElement


class enum_ItemExpectation(Enum):
    REQUIRED = "Required"
    OPTIONAL = "Optional"
    NOT_PERMITTED = "Not Permitted"
    REQUIRED_IF_RESPONSE = "Required if Response is present"
    OPTIONAL_IF_RESPONSE = "Optional if Response is present"

    @staticmethod
    def fromExpectationValueOrNone(
        value: Any | None, defaultValue: "enum_ItemExpectation"
    ) -> "enum_ItemExpectation":
        if value is None:
            return defaultValue
        elif isinstance(value, bool):
            return (
                enum_ItemExpectation.REQUIRED
                if value
                else enum_ItemExpectation.OPTIONAL
            )
        elif isinstance(value, str):
            for entry in enum_ItemExpectation:
                if value.lower() in [
                    entry.value.lower(),
                    entry.name.lower(),
                    entry.name.lower().replace("_", ""),
                ]:
                    return entry
                if value.lower().replace("_", "") == entry.name.lower().replace(
                    " ", ""
                ):
                    return entry
        appLog.print_warning(
            f"enum_ItemExpectation: `{Utils.asJsonStr(value)}` - Defaulting to {defaultValue}"
        )
        return enum_ItemExpectation.NOT_PERMITTED


class SchemaUsageInstructions:
    # | Example SchemaUsageInstructions:{
    # |     "bitstream":{"expected":false},
    # |     "permitRawErrorResult":false
    # | }
    DEFAULT_ITEM_EXPECTATION = enum_ItemExpectation.NOT_PERMITTED

    def isDefault(self) -> bool:
        return (
            (
                self.bitstreamExpectation
                == SchemaUsageInstructions.DEFAULT_ITEM_EXPECTATION
            )
            and (self.bitstreamDescription_md == "")
            and (not self.permitRawErrorResult)
            and (len(self.usageRulesList) == 0)
        )

    def asDict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}

        if self.isDefault():
            return result

        if (
            self.bitstreamExpectation
            != SchemaUsageInstructions.DEFAULT_ITEM_EXPECTATION
        ) or (self.bitstreamDescription_md != ""):
            result["bitstream"] = {"expectation": self.bitstreamExpectation.value}
            if self.bitstreamDescription_md != "":
                result["bitstream"]["description_md"] = self.bitstreamDescription_md

        if len(self.usageRulesList) > 0:
            result["usageInstructions"] = [str(x) for x in self.usageRulesList]
        if self.permitRawErrorResult:
            result["permitRawErrorResult"] = True
        return result

    def __init__(self, srcObj: dict[str, Any] | None):
        self.bitstreamExpectation = self.DEFAULT_ITEM_EXPECTATION
        self.bitstreamDescription_md: str = ""
        self.permitRawErrorResult = False
        self.usageRulesList: list[str] = []
        if srcObj is not None:
            try:
                self.permitRawErrorResult = srcObj.pop("permitRawErrorResult", False)

                bitstream = srcObj.pop("bitstream", None)

                if bitstream is not None:
                    if "expectation" in bitstream:
                        value = bitstream.get("expectation")
                    elif "expected" in bitstream:
                        value = bitstream.get("expected")
                    else:
                        value = None

                    self.bitstreamExpectation = (
                        enum_ItemExpectation.fromExpectationValueOrNone(
                            value, self.DEFAULT_ITEM_EXPECTATION
                        )
                    )
                    self.bitstreamDescription_md = str(
                        bitstream.get("description_md", "")
                    )

                for key, value in srcObj.items():
                    self.usageRulesList.append(
                        f"Usage Rules[{key}]: `{Utils.asJsonStr(value)}`"
                    )

            except Exception as e:
                appLog.print_warning_withException(
                    e,
                    f"Error processing SchemaUsageInstructions: {Utils.asJsonStr(srcObj)}",
                )

    def getBitstreamInfoAsText(self) -> str:

        if self.bitstreamDescription_md != "":
            note = " (" + self.bitstreamDescription_md + ")"
        else:
            note = ""
        if (
            self.bitstreamExpectation
            == SchemaUsageInstructions.DEFAULT_ITEM_EXPECTATION
        ):
            return ""
        elif self.bitstreamExpectation == enum_ItemExpectation.REQUIRED:
            return f"🔒  Bitstream Payload{note} Required"
        elif self.bitstreamExpectation == enum_ItemExpectation.OPTIONAL:
            return f"ℹ️  Bitstream Payload{note} optional"
        elif self.bitstreamExpectation == enum_ItemExpectation.NOT_PERMITTED:
            return f"⭐  Bitstream Payload{note} not permitted"
        else:
            return f"⭐  Bitstream Payload{note} {self.bitstreamExpectation.value}"

    def getBitstreamExpectation(self, jsonData: dict[str, Any] | None) -> bool | None:
        responsePresent = (
            bool("response" in jsonData) if jsonData is not None else False
        )

        if self.bitstreamExpectation == enum_ItemExpectation.REQUIRED:
            return True
        elif self.bitstreamExpectation == enum_ItemExpectation.OPTIONAL:
            return None
        elif self.bitstreamExpectation == enum_ItemExpectation.NOT_PERMITTED:
            return False
        elif self.bitstreamExpectation == enum_ItemExpectation.REQUIRED_IF_RESPONSE:
            return True if responsePresent else False
        elif self.bitstreamExpectation == enum_ItemExpectation.OPTIONAL_IF_RESPONSE:
            return None if responsePresent else False
        else:
            appLog.print_warning(
                f"SchemaUsageRules.getBitstreamExpectation: Invalid value {Utils.asJsonStr(self.bitstreamExpectation)}"
            )
            return False  # < Not permitted if anything goes tragically wrong here

    def getExtraNotesAsList(self, includeBitstreamInfo: bool = True) -> list[str]:
        lines = []
        if includeBitstreamInfo:
            bitstreamInfoText = self.getBitstreamInfoAsText()
            if bitstreamInfoText != "":
                lines.append(bitstreamInfoText)
        lines += self.usageRulesList
        return lines

    @staticmethod
    def create_fromFile(
        fname: str, defaultObj: dict[str, Any] | None = None
    ) -> "SchemaUsageInstructions":
        if not os.path.exists(fname):
            return SchemaUsageInstructions(defaultObj)

        if os.path.exists(fname):
            srcObj = fileUtils.loadJson_dict(
                "@" + fname, "Usage schema Rules", exceptionOnError=False
            )
            if "error" not in srcObj:
                return SchemaUsageInstructions(srcObj)
            appLog.print_warning(
                f"Failed to load usage schema from {fname}: {srcObj['error']}"
            )
        return SchemaUsageInstructions(defaultObj)


class Schema:
    """
    A class to represent a schema.
    """

    def asDict(self) -> dict[str, Any]:
        """
        Convert the schema to a dict[str,...] representation.
        """
        result: dict[str, Any] = {"name": self.name}
        if self.jsonSchema is not None:
            result["jsonSchema"] = self.jsonSchema
        if not self.usageInstructions.isDefault():
            result["usageInstructions"] = self.usageInstructions.asDict()
        if self.errMsg is not None:
            result["errMsg"] = self.errMsg
        return result

    @staticmethod
    def fromRef(
        ref: str,
        isStrict: bool = True,
    ):
        ref = ref.removeprefix("ref:").removesuffix(".json")

        return Schema(
            f"parts/${ref}", f"{schema_getDir('parts')}/${ref}.json", isStrict=isStrict
        )

    @staticmethod
    def fromCmdAndPart(
        cmd: str, piece: str, schema_description: str = "schema", isStrict: bool = True
    ):
        def defaultsOrNone(
            usageInstructions: SchemaUsageInstructions,
        ) -> tuple[dict[str, Any] | None, str, str | None] | None:
            """Generate a default request schema for a given command, including the params schema if available.
            Returns a tuple of (jsonSchema, jsonSchemaFilename, errMsg)
            """

            if piece == "request":
                return Schema.defaultSchemaForCmd_Request(cmd, isStrict)
            elif piece == "reply":
                return Schema.defaultSchemaForCmd_Reply(
                    cmd, usageInstructions.permitRawErrorResult
                )
            elif (piece == "requestParams") or (piece == "responseData"):
                return None, "(None)", None
            else:
                return None

        return Schema(
            f"{cmd}:{piece}",
            f"{schema_getDir()}/{cmd}/{piece}.json",
            schema_description,
            isStrict,
            defaultsOrNone,
        )

    def __init__(
        self,
        name: str,
        fname: str,
        schema_description: str = "schema",
        isStrict: bool = True,
        defaultsIfNotFound: Any | None = None,
    ):
        # Piece: "request","reply","request+reply","requestParams","responseData"

        self.name: str = name
        self.jsonSchemaFilename = fname

        self.jsonSchema: dict[str, Any] | None = None
        self.errMsg: str | None = None
        self.description: str = schema_description
        self.usageInstructions = SchemaUsageInstructions.create_fromFile(
            f"{self.jsonSchemaFilename.removesuffix('.json')}_usageRules.json"
        )

        #
        # ######################################################################

        # |Logging|
        appLog.print_verbose(
            f"Schema({self.name}): Loading schema from {self.jsonSchemaFilename}"
        )
        try:

            jSchemaFile_exists = os.path.exists(self.jsonSchemaFilename)

            if WARN_ON_MISSING_SCHEMAS:
                _dir = os.path.dirname(self.jsonSchemaFilename)
                if not os.path.exists(_dir):
                    appLog.print_warning(
                        f"Schema directory {_dir} not found"
                    )  # < Do this even if we auto-create the 'request' or 'reply' schema, since it indicates a chance to define the schema properly

            if jSchemaFile_exists:
                self.jsonSchema = fileUtils.loadJsonDictFromFile(
                    self.jsonSchemaFilename, self.description, exceptionOnError=False
                )
            else:
                result = None
                if defaultsIfNotFound is not None:
                    result = defaultsIfNotFound(self.usageInstructions)
                if result is not None:
                    self.jsonSchema, self.jsonSchemaFilename, self.errMsg = result
                else:
                    self.jsonSchema = {
                        "error": "No schema at " + self.jsonSchemaFilename
                    }
                    appLog.print_warning(f"Schema({self.name}): {self.errMsg}")

        except Exception as e:
            self.errMsg = f"Failed to load schema from {Utils.pathDisplay(self.jsonSchemaFilename)}: {str(e)}"
            appLog.print_warning(
                f"Schema({self.name}): Error loading schema: {self.errMsg}"
            )
        if self.jsonSchema is not None:
            #
            # Clean up
            #
            self.jsonSchema = schema_cleanElement(self.jsonSchema, isStrict)

    def __repr__(self) -> str:
        return f"Schema({self.name})"

    @staticmethod
    def defaultSchemaForCmd_Reply(cmd: str, permitRawErrorResult: bool = True):
        """Generate a default REPLY schema for a given command, including the params schema if available.
        Returns a tuple of (jsonSchema, jsonSchemaFilename, errMsg)
        """
        _fname = ""
        _jsonSchema = {
            "type": "object",
            "properties": {"chosenCmd": {"type": "string", "const": cmd}},
            "required": ["chosenCmd"],
            "additionalProperties": False,
        }

        schema_responseData = Schema.fromCmdAndPart(
            cmd, "responseData", "responseData schema"
        )
        if schema_responseData.jsonSchema is None:
            _fname = "(Internal)"
        else:
            schema_responseData.jsonSchema["_includeInTable"] = True

            if "description" not in schema_responseData.jsonSchema:
                schema_responseData.jsonSchema["description"] = f"{cmd} Response"

            _jsonSchema["properties"]["response"] = schema_responseData.jsonSchema
            _fname = f"+ {schema_responseData.jsonSchemaFilename}"
            _jsonSchema["required"].append("response")
        _errMsg = (
            None
            if (schema_responseData.errMsg is None)
            else f"response:{schema_responseData.errMsg}"
        )

        if permitRawErrorResult:
            if "description" not in _jsonSchema:
                _jsonSchema["description"] = f"❌  Error Reply"

            _jsonSchema = {
                "description": f"{cmd}: Reply",
                "type": "object",
                "oneOf": [
                    {
                        "type": "object",
                        "description": f"✅  Success Reply",
                        "properties": {
                            "chosenCmd": {"type": "string", "const": cmd},
                            "error": {
                                "type": "string",
                                "description": "Human readable description of error",
                                "minLength": 1,
                                "maxLength": 1023,
                            },
                            "errCode": {
                                "type": "string",
                                "description": "A form intended for machine parsing",
                                "minLength": 1,
                                "maxLength": 64,
                            },
                        },
                        "required": ["chosenCmd", "error"],
                    },
                    _jsonSchema,
                ],
            }

        if "description" not in _jsonSchema:
            _jsonSchema["description"] = f"{cmd} Reply"

        return _jsonSchema, _fname, _errMsg

    @staticmethod
    def defaultSchemaForCmd_Request(cmd: str, isStrict: bool = True):
        """Generate a default request schema for a given command, including the params schema if available.
        Returns a tuple of (jsonSchema, jsonSchemaFilename, errMsg)
        """
        _fname = ""
        _jsonSchema = {
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "const": cmd},
                # "timestamp": {"ref": "parts/$timestamp.json"},
                # "params": {"type": "object", "properties":{},"additionalProperties": False},
            },
            "required": ["cmd"],
            "additionalProperties": False,
        }

        if str(cmd).startswith("actions.add"):
            _jsonSchema["properties"]["action_id"] = {
                "type": "string",
                "minLength": 1,
                "maxLength": 64,
            }
            _jsonSchema["required"].append("action_id")

        schema_requestParams = Schema.fromCmdAndPart(
            cmd, "requestParams", "requestParams schema", isStrict
        )

        if schema_requestParams.jsonSchema is not None:
            if not "_includeInTable" in schema_requestParams.jsonSchema:
                schema_requestParams.jsonSchema["_includeInTable"] = True

            _jsonSchema["properties"]["params"] = schema_requestParams.jsonSchema
            _jsonSchema["required"].append("params")
            _fname = f"+ {schema_requestParams.jsonSchemaFilename}"
        else:
            _fname = "(Internal)"

        _errMsg = (
            None
            if (schema_requestParams.errMsg is None)
            else f"params:{schema_requestParams.errMsg}"
        )

        return _jsonSchema, _fname, _errMsg

    def doValidateJson(self, inputJson: dict[str, Any] | None) -> str | None:
        warn_msg: str | None = None
        try:
            if self.errMsg is not None:
                warn_msg = f"Schema for {self.name} invalid: {self.errMsg}"
            elif self.jsonSchema is None:
                msg = f"Not found: {self.jsonSchemaFilename}"
                if WARN_ON_MISSING_SCHEMAS:
                    appLog.print_warning(f"Schema({self.name}): {msg}")
                else:
                    appLog.print_verbose(f"Schema({self.name}): {msg}")
                return msg
            else:
                jsonschema.validate(instance=inputJson, schema=self.jsonSchema)
                warn_msg = None
        except jsonschema.ValidationError as e:
            warn_msg = f"JSON schema validation error: {'/'.join([str(item) for item in e.relative_path])}={Utils.asJsonStr(e.instance)} | {e.message}"
        except jsonschema.SchemaError as e:
            warn_msg = f"Invalid JSON Schema in {self.jsonSchemaFilename}: {e.message}"
        except Exception as e:
            warn_msg = f"Unexpected error during validation: {str(e)}"

        if warn_msg is not None and (warn_msg != ""):
            failure_obj = {
                "failure": warn_msg,
                "jsonData": inputJson,
                "jsonSchema": self.jsonSchema,
            }
            appLog.print_warning(
                f"---------------------------\ndoValidateJson({self.name}): {Utils.asJsonStr(failure_obj, indent=2)}\n---------------------------"
            )

        return warn_msg

    def bitstreamIsExpectedOrNone(
        self,
        jsonData: dict[str, Any] | None,
    ) -> bool | None:
        return self.usageInstructions.getBitstreamExpectation(jsonData)

    def doValidate(self, contents: ITransferableData) -> bool:
        resultJsonAlreadyPrinted = self.doValidateJson(contents.dict_annotations)
        resultBinary = None
        bitstreamIsExpected = self.bitstreamIsExpectedOrNone(contents.dict_annotations)
        if bitstreamIsExpected is False:
            if contents.hasBitstreamData():
                resultBinary = f"Schema for {self.name} does not support binary data, but binary data was provided."
        elif bitstreamIsExpected is True:

            if not contents.hasBitstreamData():
                resultBinary = f"Schema for {self.name} expects binary data, but no binary data was provided."
        else:
            # No binary rules, so no validation needed
            pass

        if resultBinary is not None:
            appLog.print_warning(
                f"Schema[{self.name}].doValidateBinary: {resultBinary}"
            )
        elif resultJsonAlreadyPrinted is None:
            appLog.print_verbose(f"✓ Schema[{self.name}].Validated")

        return (resultJsonAlreadyPrinted is None) and (resultBinary is None)


def objToMarkdownText(srcObj: dict, txtPrefix: str = "") -> str:
    out_notes = txtPrefix
    try:
        for key in srcObj:
            if key != "note":
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


class MarkdownTable:
    def __init__(
        self, name: str, headers: list[str], tableNamePrefix: str | None = None
    ):
        self.name = name
        self.headers = headers
        self.rows: list[list[str]] = []
        self.hideEmptyColumns = True
        self.extraNotes: list[str] = []
        self.namePrefix = name if tableNamePrefix is None else tableNamePrefix
        self.paragraphBefore: list[str] = []

    def addRow(self, row: list[str]):
        self.rows.append(row)

    def addExtraNote(self, note: str, allowDuplicates: bool = False):
        if allowDuplicates or note not in self.extraNotes:
            self.extraNotes.append(note)

    def addToParagraphBefore(self, line: str):
        self.paragraphBefore.append(line)

    @staticmethod
    def _asStr(cell: Any) -> str:
        if cell is None:
            return ""
        elif isinstance(cell, str):
            return cell
        else:
            cellStr = Utils.asJsonStr(cell)
            return cellStr

    def getMaxVisWidths(self) -> list[int]:
        maxWidths = [0] * len(self.headers)

        for row in self.rows:
            for i, cell in enumerate(row):
                maxWidths[i] = max(
                    maxWidths[i], PrettyText.UniLen_approx(self._asStr(cell))
                )

        for i, header in enumerate(self.headers):
            if (maxWidths[i] > 0) or not self.hideEmptyColumns:
                maxWidths[i] = max(maxWidths[i], PrettyText.UniLen_approx(header))

        return maxWidths

    def getMarkdown(self) -> str:

        md = ""

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
                visLen = PrettyText.UniLen_approx(cellStr)
                if visLen > visWidth:
                    cellStr = cellStr[: visWidth - 3] + "..."
                # if len(cellStr)!= visLen:cellStr=f"{cellStr} ({visLen} chars)"
                return cellStr + " " * (visWidth - visLen)

            title = ""
            divider = ""
            for i in colsToUse:
                title += _formatColEntry(self.headers[i], visWidths[i]) + " | "
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
            md += "\nℹ️ Additional Notes:\n"
            for x in self.extraNotes:
                md += " * " + str(x) + "\n"
        return md


INCLUDE_ADDITIONAL_SCHEMA_DETAILS = False


class SchemaDocMarkdown:
    def __init__(self, schemaShow: dict[str, Any], kind: str = ""):
        self.schemaCollection = schemaShow
        self.lines = ""
        self.tables: dict[str, MarkdownTable] = {}
        self.kind = kind

    def getLines(self) -> str:

        self.lines = ""
        for part, partSchema in self.schemaCollection.items():

            if isinstance(partSchema, dict):
                fullSchemaDict = partSchema
            elif isinstance(partSchema, Schema):
                fullSchemaDict = partSchema.asDict()
            else:
                self.lines += f"Unknown schema type for part {part}: {type(partSchema).__name__}\n\n"
                continue

            self.fullSchemaToTable(fullSchemaDict, self.kind)
        return self.lines + self.dumpAllTables()

    def dumpAllTables(self) -> str:

        md = ""

        for tableName, table in self.tables.items():
            prefix = ""
            if not ":" in tableName:
                prefix = "Table: "
            md += f"{self.md_heading_prefix()}{prefix}{tableName}\n\n"
            md += table.getMarkdown() + "\n\n"
        return md

    def md_heading_prefix(self, level: int | None = None) -> str:
        level_ = level if level is not None else 1
        return "#" * level_ + " "

    def fullSchemaToTable(
        self, __srcObj: dict[str, Any] | None, kind: str = ""
    ) -> MarkdownTable | None:

        if __srcObj == None:
            return None

        srcObj = deepcopy(__srcObj)

        _defaultTableName = f"Unnamed_{len(self.tables)+1}"
        name = srcObj.pop("name", _defaultTableName)

        if kind != "":
            kindPrefix = f"{kind}: "
        else:
            kindPrefix = ""
        table = self.createTableForSchema(
            f"{kindPrefix}{name}", srcObj.pop("jsonSchema", None)
        )
        for x in self.usageRulesSchemaToMarkdown(srcObj.pop("usageRules", None)):
            table.addExtraNote(x, allowDuplicates=True)

        if "$comment" in srcObj:
            table.addExtraNote(
                f"FullSchemaExtra[comment]: {srcObj.pop('$comment')}",
                allowDuplicates=False,
            )

        for key, value in srcObj.items():
            table.addExtraNote(
                f"FullSchemaExtra: {key}=`{Utils.asJsonStr(value)}`",
                allowDuplicates=False,
            )

        return table

    @staticmethod
    def refToFriendlyName(ref: str) -> str:
        return ref.removeprefix("ref: ").removeprefix("parts/").removesuffix(".json")

    @staticmethod
    def isSubtable(srcObj: dict[str, Any], includeOneOf: bool) -> bool:
        if srcObj is None:
            return False
        if not isinstance(srcObj, dict):
            return False

        properties = srcObj.get("properties", None)
        out_type = srcObj.get("type", None)

        if isinstance(properties, dict) and (len(properties) == 0):
            if len(srcObj) == 2 and srcObj.get("type", None) == "object":
                return False
            if len(srcObj) == 1:
                return False

        if (out_type == "object") or (properties is not None):
            return True
        if includeOneOf and ("oneOf" in srcObj):
            return True
        return False

    def jsonSchemaAddEntry(
        self,
        __destTableOrNone: MarkdownTable | None,
        srcObj_: dict[str, Any],
        name_in: str = "[Value]",
        required: bool = False,
        depth: int = 0,
    ) -> MarkdownTable:
        # A helper function to extract key information from a JSON schema entry for tabular display
        # Returns a list of strings: [required, name, type, description, notes]

        if srcObj_ is None:
            return

        def _getLimits(minKey: str, maxKey: str, name: str) -> str:
            min = srcObj.pop(minKey, None)
            max = srcObj.pop(maxKey, None)

            if (min is None) and (max is None):
                lenLimitTxt = ""
            elif (min is not None) and (max is None):
                lenLimitTxt = f"{name} ≥ {min}"
            elif (max is not None) and (min is None):
                lenLimitTxt = f"{name} ≤ {max}"
            elif min == max:
                lenLimitTxt = f"{name}={min} exactly"
            else:
                lenLimitTxt = f"{name}={min}..{max}"

            example = srcObj.pop("example", None)
            if example is not None:
                exampleStr = "eg: " + Utils.asJsonStr(example)

                if lenLimitTxt != "":
                    lenLimitTxt = f"{lenLimitTxt} ({exampleStr})"
                else:
                    lenLimitTxt = exampleStr

            const = srcObj.pop("const", None)
            if const is not None:
                constStr = "Always " + Utils.asJsonStr(const)

                if lenLimitTxt != "":
                    lenLimitTxt = f"{lenLimitTxt} | {constStr}"
                else:
                    lenLimitTxt = constStr
            return lenLimitTxt

        @staticmethod
        def _schemaToTextLine_md(obj: dict) -> str:
            txt = ""
            try:
                txt = obj.pop("type", "<Unknown Type>")
                return objToMarkdownText(obj, txt)

            except Exception as ee:
                txt += f"+Exception {ee}"
            return txt

        def _finalAppendToTable(
            out_required: str,
            out_name: str,
            out_type: str,
            out_description: str,
            out_notes: str,
        ) -> MarkdownTable:
            if out_name.startswith("Command Specification: "):
                return destTable
            if out_name.startswith("Interface Specification: "):
                return destTable

            out_notes = objToMarkdownText(srcObj, out_notes)
            if depth == 0:
                out_notes += f"  [Depth: {depth}]"
            if out_type is not None:
                out_type = out_type.removeprefix("Interface Specification: parts/")
            destTable.addRow(
                [out_required, out_name, out_type, out_description, out_notes]
            )
            return destTable

        srcObj = deepcopy(srcObj_)
        out_name = name_in
        out_type = srcObj.pop("type", None)
        out_description = srcObj.pop("description", "")
        out_notes = ""
        out_required = "🔒" if required else " "

        if __destTableOrNone is None:
            _tableName = out_name
            srcObj = deepcopy(srcObj_)

            if out_description is not None:
                _tableName += f" : {out_description}"
            title = srcObj.pop("title", None)
            if title is not None:
                _tableName += f" : {title}"

            if _tableName in self.tables:
                return self.tables[_tableName]

            destTable = MarkdownTable(
                _tableName,
                ["Req", "Name", "Type", "Description", "Notes"],
                tableNamePrefix=out_name,
            )
            self.tables[_tableName] = destTable
        else:
            destTable = __destTableOrNone

        isSubtable = self.isSubtable(srcObj, includeOneOf=True)

        try:
            refId = SchemaDocMarkdown.popRefId(srcObj)

            if isSubtable and __destTableOrNone is not None:
                # This is a subtable, so we create a new table for it and add a reference to it in the current table
                if refId is not None:
                    subTableName = refId
                else:
                    subTableName = f"{destTable.namePrefix}.{name_in}"
                self.jsonSchemaAddEntry(None, srcObj, subTableName, False, depth + 1)
                srcObj = {}
                # .pop("required",None)
                # srcObj.pop("required",None)
                if depth == 0:
                    return __destTableOrNone
                else:
                    return _finalAppendToTable(
                        out_required, out_name, subTableName, out_description, out_notes
                    )

            id = srcObj.pop("$id", None)
            if (id is not None) and (id != f"parts/{destTable.namePrefix}.json"):
                destTable.addExtraNote(f"⚠️ id : {id}'", allowDuplicates=False)

            if (out_type == "object") or ("properties" in srcObj):
                _properties = srcObj.pop("properties", {})
                if not isinstance(_properties, dict):
                    raise TypeError(
                        f"Expected 'properties' to be a dict - not a {type(_properties).__name__}"
                    )
                if len(_properties) > 0:
                    _required = srcObj.pop("required", [])
                    _additionalProperties = srcObj.pop("additionalProperties", True)

                    if isinstance(_additionalProperties, bool):
                        if _additionalProperties:
                            _properties["«other»"] = {
                                "note": f"Additional properties are permitted - no checks will be applied"
                            }
                    elif isinstance(_additionalProperties, dict):
                        _properties["«other»"] = _additionalProperties
                    else:
                        _properties["«other»"] = {"type": str(_additionalProperties)}

                    for key in _properties:
                        if key in _required:
                            key_is_required = True
                            _required.remove(key)
                        else:
                            key_is_required = False

                        subEntry = _properties[key]
                        self.jsonSchemaAddEntry(
                            destTable, subEntry, key, key_is_required, depth + 1
                        )
                    if len(_required) > 0:
                        msg = f"Required properties not listed in schema: {', '.join(_required)}"
                        destTable.addExtraNote("⚠️ " + msg, allowDuplicates=False)
                    return destTable

            _tableName = destTable.name

            oneOf = srcObj.pop("oneOf", None)

            if oneOf is not None:
                destTable.addToParagraphBefore(
                    f"One of {PrettyText.pluralize(len(oneOf), 'option')}:"
                )
                for i, option in enumerate(oneOf):
                    optionName = str(
                        option.pop("description", f"{_tableName}.option[{i+1}]")
                    )
                    if self.isSubtable(option, includeOneOf=True):
                        self.createTableForSchema(optionName, option)
                        destTable.addToParagraphBefore(f" * {optionName}")
                    else:
                        destTable.addToParagraphBefore(
                            f" * {_schemaToTextLine_md(srcObj)}"
                        )

                return destTable  # return _finalAppendToTable(out_required, "aa:"+out_name, out_type, out_description, out_notes)

            if (out_type == "number") or (out_type == "integer"):
                lenLimitTxt = _getLimits("minimum", "maximum", "Value")

                out_notes += lenLimitTxt

                if refId is not None and (INCLUDE_ADDITIONAL_SCHEMA_DETAILS):
                    out_type = f"{refId}: {out_type}"

                return _finalAppendToTable(
                    out_required, out_name, out_type, out_description, out_notes
                )

            if out_type == "string":
                lenLimitTxt = _getLimits("minLength", "maxLength", "Length")

                out_notes += lenLimitTxt

                if refId is not None and (INCLUDE_ADDITIONAL_SCHEMA_DETAILS):
                    out_type = f"{refId}: {out_type}"

                for key in srcObj:
                    out_notes += f" {key}={Utils.asJsonStr(srcObj[key])}"

                return _finalAppendToTable(
                    out_required, out_name, out_type, out_description, out_notes
                )

            if out_type == "array":
                arrayItemType = srcObj.pop("items", None)

                if arrayItemType is not None:
                    arrayItemType = self.itemInfoToFriendlyStr(arrayItemType)
                    minItems = srcObj.get("minItems", None)
                    maxItems = srcObj.get("maxItems", None)

                    if (
                        (minItems is not None)
                        and (maxItems is not None)
                        and (minItems == maxItems)
                    ):
                        srcObj.pop("minItems")
                        srcObj.pop("maxItems")

                        if minItems <= 5:
                            out_type = "[" + ", ".join([arrayItemType] * minItems) + "]"
                        else:
                            out_type = f"[{arrayItemType} x {minItems}]"

                if refId is not None and (INCLUDE_ADDITIONAL_SCHEMA_DETAILS):
                    out_type = f"{refId}: {out_type}"

                return _finalAppendToTable(
                    out_required, out_name, out_type, out_description, out_notes
                )

            if refId is not None:
                if out_type is None:
                    out_type = refId
                    self.createTableForSchema(refId, srcObj)
                elif INCLUDE_ADDITIONAL_SCHEMA_DETAILS:
                    out_type += f"[{refId}]"
            return _finalAppendToTable(
                out_required, out_name, out_type, out_description, out_notes
            )

        except Exception as e:
            destTable.addExtraNote(f"⚠️ Error processing schema entry: {str(e)}")
            return _finalAppendToTable(
                out_required, out_name, out_type, out_description, out_notes
            )

    @staticmethod
    def popRefId(srcObj_: dict[str, Any]) -> str | None:
        if srcObj_ is None:
            return None
        comment = srcObj_.pop("$comment", None)
        return (
            None
            if comment is None
            else SchemaDocMarkdown.refToFriendlyName(str(comment))
        )

    def createTableForSchema(
        self, tableNamePrefix: str, srcObj_: dict[str, Any]
    ) -> MarkdownTable:
        return self.jsonSchemaAddEntry(None, srcObj_, tableNamePrefix, depth=0)

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
            lines.append("Bitstream Payload Expected")
        elif binaryRules != {"expected": False}:
            lines.append(f"usageRulesSchemaToMarkdown: binaryRules={binaryRules}")
        for key, value in srcObj.items():
            lines.append(f"Usage Rules Descriptor[{key}]: `{Utils.asJsonStr(value)}`")

        return lines

    @staticmethod
    def itemInfoToFriendlyStr(obj_in: dict[str, Any] | None):
        if obj_in is None:
            return "<❓Unspecified>"

        obj = deepcopy(obj_in)
        result = obj.pop("type", "❓")

        extras = []
        for name, value in obj.items():
            extras.append(f"{name}={Utils.asJsonStr(value)}")
        if len(extras) > 0:
            result += " [" + ", ".join(extras) + "]"
        return result
