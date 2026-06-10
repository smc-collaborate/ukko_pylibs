import os, sys
from typing import Any, Type
import numpy as np

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

import ukko_pylibs.app.appSupport as app

################################################################################
#


class PixelFormatData:
    def __init__(
        self,
        name: str | None,
        bytesPerPixel: int,
        formatPackKind: str,
        bitDepth: int,
        isGrayscale: bool,
        isLeftAligned: bool = False,
    ):
        self.bytesPerPixel = bytesPerPixel
        self.formatPackKind = formatPackKind
        self.bitDepth = bitDepth
        self.isGrayscale = isGrayscale
        self._name = name
        self.isLeftAligned = isLeftAligned

    def asNpDtypeOrNone(self) -> Type[np.unsignedinteger] | None:
        if self.bytesPerPixel == 1:
            return np.uint8
        elif self.bytesPerPixel == 2:
            return np.uint16
        elif self.bytesPerPixel == 4:
            return np.uint32
        else:
            return None

    def getLeftShiftCount(self) -> int:
        if self.isLeftAligned:
            return 0
        count = self.bytesPerPixel * 8 - self.bitDepth
        if count <= 0:
            return 0

        return count

    def name(self) -> str:
        if (self._name is not None) and (self._name != ""):
            return self._name

        colourKind = "mono" if self.isGrayscale else "rgb"

        if not self.isGrayscale and self.bitDepth == 8:
            depth = ""
        else:
            depth = f"{self.bitDepth}"
        suffix = "L" if self.isLeftAligned else ""

        return colourKind + depth + suffix

    def convertPixelData_orHandledException(
        self, inFormat: dict[str, Any], data: list[Any]
    ) -> int:  # tuple[int]: # Returns Pixel tuple
        """
        Append pixel data to the PixelFormatData instance.
        :param data: List of pixel values to append
        """
        inNumPlanes = inFormat.get("planes")
        inBitDepth = inFormat.get("bitdepth", 8)
        inGreyscale = inFormat.get("greyscale")

        inBytesPerPixel = inNumPlanes * (inBitDepth // 8)
        inBitMax = (1 << inBitDepth) - 1
        outBitMax = (1 << self.bitDepth) - 1

        if not self.isGrayscale:
            raise app.HandledException(f"Unsupported conversion format: {self}")

        if (inGreyscale) and (inNumPlanes == 1):
            gray_ratio = data[0] / inBitMax
        elif (
            (not inGreyscale)
            and ((inNumPlanes == 3) or (inNumPlanes == 4))
            and (inBitDepth == 8)
            and (inBytesPerPixel == inNumPlanes)
        ):
            gray_ratio = rgb_gamma_to_grayscale_ratio(
                data[0], data[1], data[2], inFormat.get("gamma", 1.0)
            )
        else:
            raise app.HandledException(f"Unsupported PNG format[a]: {inFormat}")

        outMagnitude = gray_ratio * outBitMax
        return round(outMagnitude)

    @staticmethod
    def u8(bitDepth: int, isGrayscale: bool) -> "PixelFormatData":
        return PixelFormatData(None, 1, "B", bitDepth, isGrayscale)

    @staticmethod
    def u16(bitDepth: int, isGrayscale: bool) -> "PixelFormatData":
        return PixelFormatData(None, 2, "H", bitDepth, isGrayscale)


def rgb_to_grayscale_ratio(r, g, b):
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def rgb_gamma_to_grayscale_ratio(r, g, b, gamma=1.0):
    grayscale_ratio = rgb_to_grayscale_ratio(r, g, b)

    # Apply gamma correction
    if gamma != 1.0:
        grayscale_ratio = (grayscale_ratio) ** (1.0 / gamma)

    return grayscale_ratio


PIXEL_FORMATS = {
    "mono8": PixelFormatData.u8(bitDepth=8, isGrayscale=True),
    "mono9": PixelFormatData.u16(bitDepth=9, isGrayscale=True),
    "mono10": PixelFormatData.u16(bitDepth=10, isGrayscale=True),
    "mono11": PixelFormatData.u16(bitDepth=11, isGrayscale=True),
    "mono12": PixelFormatData.u16(bitDepth=12, isGrayscale=True),
    "mono13": PixelFormatData.u16(bitDepth=13, isGrayscale=True),
    "mono14": PixelFormatData.u16(bitDepth=14, isGrayscale=True),
    "mono15": PixelFormatData.u16(bitDepth=15, isGrayscale=True),
    "mono16": PixelFormatData.u16(bitDepth=16, isGrayscale=True),
}
