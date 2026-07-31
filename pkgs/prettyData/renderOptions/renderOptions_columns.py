import sys, os
from typing import Union
from pathlib import Path

################################################################################
#
# Ensure shared Packages are available
#

packages_dir = str((Path(__file__).parent.parent.parent.parent / "pkgs").absolute())
if not packages_dir.endswith("/pkgs") or not os.path.exists(packages_dir):
    exit(f"❌  {__file__}\n    Misconfigured: [/path/to]/pkgs is not {packages_dir}")

if packages_dir not in sys.path:
    sys.path.append(packages_dir)
#
################################################################################


from ukkoDataFormats import SparseList

from prettyData.renderOptions.renderOptions_gridPart import RenderOptions_GridPart

# from prettyData. import renderOptions as renderOptions
################################################################################


class RenderOptions_Columns(SparseList[RenderOptions_GridPart]):

    def __init__(
        self,
        objSrc: Union[
            "RenderOptions_Columns", SparseList[RenderOptions_GridPart], None
        ] = None,
    ):
        super().__init__(RenderOptions_GridPart(), objSrc)

    @staticmethod
    def create_fromJsonDictOrNone(spec: dict | list | None) -> "RenderOptions_Columns":
        return RenderOptions_Columns(
            RenderOptions_Columns.create_fromJsonDictOrNone_andBlank(
                spec, RenderOptions_GridPart()
            )
        )

    @staticmethod
    def createOrNone_fromJsonDictOrNone(
        spec: dict | list | None,
    ) -> Union["RenderOptions_Columns", None]:
        if spec is None:
            return None
        return RenderOptions_Columns(
            RenderOptions_Columns.create_fromJsonDict_andBlank(
                spec, RenderOptions_GridPart()
            )
        )

    @staticmethod
    def create_fromList(spec: list) -> "RenderOptions_Columns":
        return RenderOptions_Columns(
            RenderOptions_Columns.create_fromList_andBlank(
                spec, RenderOptions_GridPart()
            )
        )

    @staticmethod
    def createOrNone_fromListOrNone(
        spec: list | None,
    ) -> Union["RenderOptions_Columns", None]:
        return None if spec is None else RenderOptions_Columns.create_fromList(spec)
