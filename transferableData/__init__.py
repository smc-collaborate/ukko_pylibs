################################################################################
#
# Shared Libraries
#
import os, sys
from pathlib import Path

shared_dir = os.path.abspath(f"{Path(__file__).parent}/../../")
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
