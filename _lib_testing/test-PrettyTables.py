#!/usr/bin/python3

VERSION = "0.0.1-wip"  # < Warning: When updating version, ensure you update the tests that report version number too !
#########################################################################
#
# Add 'common' libraries
#
#
import os
import sys
from typing import Any
from pathlib import Path

libs_dir = os.path.abspath(f"{Path(__file__).parent}")
if libs_dir not in sys.path:
    sys.path.append(libs_dir)

from ukko_pylibs import PrettyTable, Utils, app, appLog, AppChoices, DataTypes

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
                    "type": DataTypes.JsonDict,
                    "mustBeDirect": True,
                    "formatAsText": "PrettyTable.Contents",
                    "description": "PrettyTable.Contents as JSON",
                },
                {
                    "name": "render",
                    "type": DataTypes.JsonDict | None,
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

    table = PrettyTable.Table.create_fromJsonDict(table_spec)

    renderOptions = PrettyTable.RenderOptions.createOrNone_fromJsonDictOrNone(
        render_spec
    )

    app.print_cyan(["renderOptions", Utils.asJsonStr(renderOptions, indent=2)])
    lines_out = PrettyTable.Rendered(table, renderOptions).asTextLines()

    for line in lines_out:
        print(line)


if __name__ == "__main__":
    app.doRun(main)
