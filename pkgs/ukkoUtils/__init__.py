################################################################################
#
# This relies on NO OTHER ukko libraries to initialise
#

####################
#
# Prettifiying
#

from .src.module_utils import pathAsDisplay

###
#
# Text <-> Data
#
###########################################
#
# DataToText
#
from .src.module_utils import asJsonStr, asJsonRStr, asStr, makeJsonable as asJsonable

from .src.module_utils import json_loads, dictFromJsonLikeStr
from .src.module_utils import toBool, toHex, rangeAsText
from .src.module_utils import DeviceStateEnum
from .src.module_utils import getStartupPath
from .src.module_utils import (
    hasRemovedPrefix,
    hasRemovedSuffix,
    asUtf8orBytes,
    hasReplacedPrefix,
)

###################
# Environment info
#
from .src.module_utils import isStdoutText

from .src.module_utils import typeAsStr, typeOfAsStr

###################
# Debug info
#
from .src.module_utils import __line__


###################
# Format data in common ways
#
from .src.module_utils import timestampObj_from_ns
from .src.module_utils import asUtf8orBytesOrNone
from .src.class_HandledException import getExceptionAsDict

###################
# ProgressMsg
#
from .src.class_ProgressMsg import ProgressMsg, IWithProgressMarker_Interface

###################
#
from .src.class_HandledException import HandledException, getPrettyExceptionInfo

__all__ = [
    "pathAsDisplay",
    "asJsonStr",
    "asJsonRStr",
    "asStr",
    "asJsonable",
    "json_loads",
    "dictFromJsonLikeStr",
    "toBool",
    "toHex",
    "hasRemovedPrefix",
    "hasRemovedSuffix",
    "hasReplacedPrefix",
    "asUtf8orBytes",
    "DeviceStateEnum",
    "isStdoutText",
    "HandledException",
    "getPrettyExceptionInfo",
    "typeAsStr",
    "typeOfAsStr",
    "getStartupPath",
    "rangeAsText",
    "__line__"
    ###################
    # Format data in common ways
    #
    ,
    "timestampObj_from_ns",
    "asUtf8orBytesOrNone",
    "getExceptionAsDict",
    ###################
    # ProgressMsg
    #
    "ProgressMsg",
    "IWithProgressMarker_Interface",
]
