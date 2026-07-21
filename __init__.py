################################################################################
#
# Shared Libraries
#
import os, sys

shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.logger import appLog
from ukko_pylibs.basic.simpleUtils import PrettyText
from ukko_pylibs.basic.simpleUtils import EscapeMgr
from ukko_pylibs.basic.simpleUtils import DictUtils
from ukko_pylibs.basic.simpleUtils import Utils
from ukko_pylibs.basic.simpleUtils import ImageInfo
from ukko_pylibs.app.appSupport import app, AppChoices
from ukko_pylibs.app.appSupport import Define as AppDefinition
from ukko_pylibs.basic.prettyTable import PrettyTable

from ukko_pylibs.basic.fileUtils import FileUtils
from ukko_pylibs.basic import styling
from ukko_pylibs.basic.class_HandledException import HandledException
from ukko_pylibs.basic.simpleUtils import timestampObj_from_ns


class DataTypes:
    from ukko_pylibs.basic.class_DataContents import DataContents
    from ukko_pylibs.basic.class_JsonData import JsonDict

    JsonDict = JsonDict
    DataContents = DataContents


__all__ = [
    "appLog",
    "AppDefinition",
    "PrettyText",
    "EscapeMgr",
    "DictUtils",
    "Utils",
    "FileUtils",
    "DataTypes",
    "app",
    "styling",
    "HandledException",
    "ImageInfo",
    "timestampObj_from_ns",
    "AppChoices",
    "PrettyTable",
]
