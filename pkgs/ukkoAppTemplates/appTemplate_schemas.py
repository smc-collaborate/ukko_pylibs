#
#
from appAssist import app
from appLogging import appLog
import fileUtils, ukkoUtils
from schemaHandling import Schema, schema_list, MarkdownSchemaDoc

#
################################################################################


def runApp(appDescription: str, args: list[str]):

    VERSION = "1.0.2"
    appDefinition = {
        "version": VERSION,
        "description": appDescription if appDescription != "" else "Process schemas",
        "author": "mac@spacemachines.com",
        "options": [
            {
                "name": "action",
                "mustBeDirect": True,
                "customising": {
                    "show": {"description": "View the schema for a command"},
                    "doc-markdown": {
                        "description": "View the schema as Markdown Documentation",
                        "options": [
                            {
                                "name": "exportPath",
                                "shortName": "p",
                                "description": "Export the markdown to files under this directory (eg: 'docs/schemas')",
                                "type": str,
                                "default": "",
                            }
                        ],
                    },
                    "validate": {
                        "description": "Validate a JSON file against the schema for a command",
                        "options": [
                            {
                                "name": "inputJson",
                                "shortName": "j",
                                #                                                    "type": str,
                                "default": "@/dev/stdin",
                                "mayBeDirect": True,
                            },
                            {"name": "strict"},
                        ],
                    },
                },
            },
            {
                "name": "kind",
                "mustBeDirect": True,
                "customising": {
                    "ref": {
                        "description": "Use the reference 'parts/$file.json' syntax to identify the schema part",
                        "options": [
                            {
                                "name": "name",
                                "type": str,
                                "mayBeDirect": True,
                                "hint": "parts/$file.json",
                            }
                        ],
                    },
                    "cmd": {
                        "description": "Use a command to identify the schema",
                        "options": [
                            {
                                "name": "name",
                                "lookup": schema_list(),
                                "mayBeDirect": True,
                            },
                            {
                                "name": "piece",
                                "lookup": [
                                    "request",
                                    "reply",
                                    "request+reply",
                                    "requestParams",
                                    "responseData",
                                ],
                                "default": "request+reply",
                                "mayBeDirect": True,
                            },
                        ],
                    },
                    "all": {"description": "Process all communication specifications"},
                    "json": {
                        "description": "The schema is JSON from a file",
                        "options": [
                            {
                                "name": "json",
                                "type": str,
                                "default": "-",
                                "mayBeDirect": True,
                                "hint": "The file to load the JSON schema from",
                            }
                        ],
                    },
                },
            },
        ],
    }

    params = app.Define(appDefinition).parseParams(args)

    isStrict = bool(
        params.get("strict", True)
    )  # Only given option in validation - otherwise default to true
    ###########
    # Load Schema into JSON
    #
    schemasShow = {}
    schema: Schema | None = None
    fileKind = ""
    if params["kind"] == "ref":
        schema = Schema.fromRef(
            params.asStr("name").removeprefix("$"), isStrict=isStrict
        )
        fileKind = "Interface Specification"
        schemasShow[params.asStr("name")] = schema.asJsonable()
    elif params["kind"] == "json":
        fname = params.asStr("json")
        if (fname == "-") or (fname == ""):
            fname = "/dev/stdin"
        name = ukkoUtils.pathAsDisplay(fname)
        fileKind = "Specification"
        schema = Schema(name, fname, isStrict=isStrict)
        schemasShow[name] = schema.asJsonable()
    elif params["kind"] == "all":
        fileKind = "Command Specification"

        for name in schema_list():
            schemasShow[name] = [
                Schema.fromCmdAndPart(name, "request", isStrict=isStrict).asJsonable(),
                Schema.fromCmdAndPart(name, "reply", isStrict=isStrict).asJsonable(),
            ]
    elif (params.asStr("piece") == "request+reply") and (
        params["action"] != "validate"
    ):
        fileKind = f"Command Specification[{params['name']}]"
        name = params.asStr("name")
        schemasShow[name] = [
            Schema.fromCmdAndPart(name, "request", isStrict=isStrict).asJsonable(),
            Schema.fromCmdAndPart(name, "reply", isStrict=isStrict).asJsonable(),
        ]
    else:
        fileKind = f"Interface Specification: {params['name']}[{params['piece']}]"
        schemasShow[params.asStr("name") + "." + params.asStr("piece")] = (
            Schema.fromCmdAndPart(
                params.asStr("name"), params.asStr("piece"), isStrict=isStrict
            ).asJsonable()
        )

    appLog.print_verbose(f"Loaded schemas: {ukkoUtils.asJsonStr(schemasShow,indent=2)}")
    if params["action"] == "show":
        print(ukkoUtils.asJsonStr(schemasShow, indent=2))
    elif params["action"] == "doc-markdown":

        for caption, md in MarkdownSchemaDoc(
            schemasShow,
            fileKind,
            params.asStr("exportPath"),
            namePartIsLiteralQuoted=True,
        ).makeLinesPlus():
            if caption != "":
                appLog.print_info(caption)
            if md != "":
                print(md.strip())
            print("\n")
    elif params["action"] == "validate":
        if schema is None:
            errmsg = "No schema to validate"
        else:
            errmsg = schema.doValidateJson(
                fileUtils.loadJson_dict(params.asStr("inputJson"))
            )

        if errmsg is None:
            print(
                f"✓ Schema validate[{"Untitled" if schema is None else schema.name}] : OK"
            )
        else:
            app.error_exit(errmsg)
