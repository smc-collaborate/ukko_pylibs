#!/usr/bin/python3

VERSION = "0.0.1-wip"  # < Warning: When updating version, ensure you update the tests that report version number too !


from ukkoCommonCollection import ukkoUtils, AppChoices, app, PrettyData, JsonDict

#########################################################################
#

CMD_COL_LEN = 60


def main():

    params: AppChoices = app.Define(
        {
            "version": "0.0.1",
            "description": "Validation Tests for PrettyTable",
            "author": "mac@spacemachines.com",
            "options": [
                {
                    "name": "contents",
                    "type": JsonDict,
                    "mustBeDirect": True,
                    "formatAsText": "PrettyTable.Contents",
                    "description": "PrettyTable.Contents as JSON",
                },
                {
                    "name": "render",
                    "type": JsonDict | None,
                    "default": None,
                    "formatAsText": "PrettyTable.Renderer",
                    "description": "PrettyTable.Renderer as JSON (or blank)",
                },
                {
                    "name": "output-format",
                    "shortName": "f",
                    "lookup": ["text", "json", "json-full"],
                    "default": "text",
                    "group": "Display Options",
                    "source": "~appAuto",
                    "position": 9999,
                },
            ],
            "examples": [
                [
                    "<exeName+action> file:<SAMPLES_DIR>/table-small.json",
                    "# Show a simple table",
                ],
                [
                    "<exeName+action> file:<SAMPLES_DIR>/table-wide.json",
                    "# Show a table that requires wrapping",
                ],
                [
                    "<exeName+action> file:<SAMPLES_DIR>/table-wide.json",
                    "--render=file:<SAMPLES_DIR>/render-barred.json",
                    "# Demonstrate render options including wrapping",
                ],
            ],
            "showHiddenOptions": True,
        }
    ).parseParams()

    print("Normalised    : " + app.appInfo_normalisedCommand_styled())
    # app.print_cyan(params)

    table_spec = params.param_asDict("contents")
    render_spec = params.param_asDictOrNone("render")

    contents = PrettyData.Contents.create_fromJsonDict(table_spec)

    renderingList = [
        render_spec,
        '{"borders":"outer+vert","rowStyling":{"title":"+bold"}}',
    ]

    for renderStyle in renderingList:
        print("")
        print(
            f"Rendering Style[{type(renderStyle)}]: {ukkoUtils.asJsonStr(renderStyle)}"
        )
        lines_out = PrettyData.Rendered(contents, renderStyle).asTextLines()

        for line in lines_out:
            print(line)


if __name__ == "__main__":
    app.doRun(main)
