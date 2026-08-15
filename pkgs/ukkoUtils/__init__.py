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
from .src.module_utils import asJsonStr, asJsonRStr, asStr, asJsonable

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

from .src.module_utils import (
    typeAsStr,
    typeOfAsStr,
    asStrWithType,
    createFrom_basedOnTemplate,
    createFrom_basedOnType,
)

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
    "hasRemovedPrefix",
    "hasRemovedSuffix",
    "hasReplacedPrefix",
    "DeviceStateEnum",
    "isStdoutText",
    "HandledException",
    "getPrettyExceptionInfo",
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
    #############################
    # Type handling & Conversions
    "typeAsStr",
    "typeOfAsStr",
    "createFrom_basedOnTemplate",
    "createFrom_basedOnType",
    "toBool",
    "toHex",
    "asJsonStr",
    "asJsonRStr",
    "asStr",
    "asJsonable",
    "asStrWithType",
    "json_loads",
    "dictFromJsonLikeStr",
    "asUtf8orBytes",
    ###################
    # ProgressMsg
    #
    "ProgressMsg",
    "IWithProgressMarker_Interface",
]
