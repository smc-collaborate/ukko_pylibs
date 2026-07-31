################################################################################
#
# Import shared Libraries
#


###########################
#


import os
import sys
from pathlib import Path

################################################################################
#
# Ensure shared Packages are available
#

packages_dir = str((Path(__file__).parent.parent.parent / "pkgs").absolute())
if not packages_dir.endswith("/pkgs") or not os.path.exists(packages_dir):
    exit(f"❌  {__file__}\n    Misconfigured: [/path/to]/pkgs is not {packages_dir}")

if packages_dir not in sys.path:
    sys.path.append(packages_dir)
#
################################################################################
import ukkoUtils
from appAssist import AppChoices, app, appConfig
from prettyData import PrettyData
from ukkoDataFormats import JsonDict

from appLogging import appLog
from appLogging import timeFromStart_text as ns_asText
from ukkoUtils import asJsonStr
import prettyText
from ukkoStyling import styling
import dictUtils
import escapeFormatting

__all__ = [
    "JsonDict",
    "PrettyData",
    "AppChoices",
    "app",
    "ukkoUtils",
    "appLog",
    "asJsonStr",
    "prettyText",
    "ns_asText",
    "styling",
    "appConfig",
    "dictUtils",
    "escapeFormatting",
]
