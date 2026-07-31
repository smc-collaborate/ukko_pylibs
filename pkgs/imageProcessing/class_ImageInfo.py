import os, sys
from typing import Any, Type
import numpy as np
from pathlib import Path

################################################################################
#
# Ensure shared Packages are available
#

packages_dir = str((Path(__file__).parent.parent / "pkgs").absolute())
if not packages_dir.endswith("/pkgs") or not os.path.exists(packages_dir):
    exit(f"❌  {__file__}\n    Misconfigured: [/path/to]/pkgs is not {packages_dir}")

if packages_dir not in sys.path:
    sys.path.append(packages_dir)
#
################################################################################

from ukkoUtils import HandledException

################################################################################
#


class ImageInfo:
    @staticmethod
    def imageFormatTextToSpec(specStr: str) -> dict[str, Any]:
        """Image format spec str:   'png','jpg','bmp','mono8_16x16','mono12_32x32+15' etc"""
        _parts_format = specStr.split("_", maxsplit=1) + [""]
        _parts_size = (_parts_format + [""])[1].split("+", maxsplit=1)

        _parts_wid_height = (_parts_size[0] + "x").split("x")

        format = _parts_format[0].strip()

        width = strToInt(_parts_wid_height[0], 0, f"width from {specStr}")
        height = strToInt(_parts_wid_height[1], 0, f"height from {specStr}")
        offset = strToInt((_parts_size + [""])[1], 0)

        result: dict[str, Any] = {"format": format}

        if width != 0:
            result["width"] = width
        if height != 0:
            result["height"] = height
        if offset != 0:
            result["offset"] = offset

        # appLog.print_verbose(f"imageFormatTextToSpec({specStr}) -> {result}")
        return result

    @staticmethod
    def isStandardImageFormat(ext: str) -> bool:
        return ImageInfo.asStandardImageFormatOrNone(ext) is not None

    @staticmethod
    def makeImageFormatExt(ext: str) -> str:
        ext = ext.strip().removeprefix(".").lower()
        return "." + ("" if ImageInfo.isStandardImageFormat(ext) else "raw_") + ext

    @staticmethod
    def asStandardImageFormatOrNone(ext: str) -> str | None:
        ext = ext.strip().removeprefix(".").lower()

        if not ext in ["png", "jpg", "jpeg", "bmp", "gif", "tiff"]:
            return None
        if ext == "jpg":
            return "jpeg"
        return ext


def strToInt(value: str, defaultValue: int, context: str | None = None) -> int:
    try:
        if (value == "") and context is None:
            return defaultValue  # < If expected to fail, avoid an exception to aide debugging where we halt on all exceptions
        return int(value.strip())
    except ValueError:
        if (context is not None) and (len(context) > 0):
            sys.stderr.write(
                f"⚠️  strToInt(): Failed to convert '{value}' to int in {context}\n"
            )
        return defaultValue
