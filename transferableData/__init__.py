################################################################################
#
# Shared Libraries
#
import os, sys

shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)


from ukko_pylibs.transferableData.class_ITransferableData import ITransferableData
import ukko_pylibs.transferableData.customising as customising

from ukko_pylibs.transferableData.customising import CustomContentsFormatDefinition
from ukko_pylibs.transferableData.customising import CustomisedContents


__all__ = [
    "ITransferableData",
    "customising",
    "CustomContentsFormatDefinition",
    "CustomisedContents",
]
