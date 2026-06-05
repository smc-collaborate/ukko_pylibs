import io
import math
from typing import Any

import png
import struct, sys

import numpy as np
import cv2
import os

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.simpleUtils import DictUtils
from ukko_pylibs.basic.class_HandledException import HandledException


from ukko_pylibs.imageProcessing.class_PixelFormatData import (
    PIXEL_FORMATS,
    PixelFormatData,
)
from ukko_pylibs.basic.appSupport import appLog

################################################################################
#


class ShuffleLookup:

    # Lookup table is guaranteed to be a shuffled list of indexes
    # (or None)
    #  .lookup
    #  .count
    def __init__(
        self, nominalCount: int, formattingOptions: None | dict[str, Any] | Any = None
    ):
        self.lookup: None | list[int] = None

        if isinstance(formattingOptions, int):
            formattingOptions = {"count": formattingOptions}
        bitsource_in = DictUtils.get(formattingOptions, "bit_source", None)
        if isinstance(bitsource_in, list) and len(bitsource_in) > 0:
            appLog.print_verbose(f"Shuffling : {formattingOptions} ...")
            self.count = DictUtils.getInt(
                formattingOptions, "count", 1 << len(bitsource_in)
            )
            appLog.print_info(f"-> Count: {self.count}")
            ################################################
            # Fill out 'bitsource' if too short  (by incrementing last entry)
            bitsource = list(bitsource_in)
            x = bitsource[-1]
            n = 1 << len(bitsource)

            while n < self.count:
                x += 1
                value = 1 << (x)
                if value >= self.count:
                    x = 0
                bitsource.append(x)
                n <<= 1

            ################################################
            # Create Lookup table
            appLog.print_info(f"-> Count: {self.count} bitsource = {bitsource}")

            self.lookup = [
                ShuffleLookup.bit_exchange(x, bitsource) for x in range(self.count)
            ]
        else:
            appLog.print_verbose(f"Skip: Shuffling : {formattingOptions} ...")
            self.lookup = None
            self.count = DictUtils.getInt(formattingOptions, "count", nominalCount)

    @staticmethod
    def bit_exchange(value: int, bitlookup: list[int]) -> int:
        result = 0

        for bit_position in bitlookup:
            if value & 1:
                result |= 1 << bit_position
            value >>= 1

        return result

    def shuffle(self, input_data: list[Any] | tuple[Any]) -> list[Any] | tuple[Any]:
        if self.lookup is None:
            return input_data

        if len(input_data) != len(self.lookup):
            appLog.print_warning(
                f"Invalid lookup length: Expected {len(self.lookup)}, got {len(input_data)}"
            )
            return input_data

        # appLog.print_info(f"Shuffling row data with lookup ...")
        return [input_data[self.lookup[x]] for x in range(len(input_data))]

    def getLookup(self, index: int) -> int:
        if self.lookup is None:
            return index
        if (index < 0) or (index >= len(self.lookup)):
            appLog.print_error(
                f"Invalid lookup index: {index} (max:{len(self.lookup)-1})"
            )
            return index
        return self.lookup[index]


class RawImg:
    def __init__(self, width, height, pixelFormat: PixelFormatData, imgRows=[]):
        self.width = width
        self.height = height
        self.pixelFormat = pixelFormat
        self.imageRows = imgRows
        self.skipRawBytes = 0
        self.formattingExtras: dict[str, Any] | None | Any = (
            {}
        )  # Will be ignored unless set to a dict
        # appLog.print_info(f"Created {self}")

    def toCV2Image(self) -> np.ndarray:
        appLog.print_info("Converting RawImg to OpenCV image format ...")

        np_image = np.array(self.imageRows, dtype=self.pixelFormat.asNpDtypeOrNone())
        leftShiftCount = self.pixelFormat.getLeftShiftCount()
        if leftShiftCount > 0:
            np_image = np.left_shift(np_image, leftShiftCount)

        appLog.print_verbose(
            f"toCV2Image: {self.width}x{self.height} {self.pixelFormat.name()} - img_in shape: {np_image.shape}, dtype: {np_image.dtype}"
        )

        return np_image

    def __str__(self) -> str:
        return f"RawImg({self.width}x{self.height}, {self.pixelFormat.name()})"

    def getFormatStr(self) -> str:
        txt = f"{self.pixelFormat.name()}_{self.width}x{self.height}"
        if self.skipRawBytes > 0:
            txt += f"+{self.skipRawBytes}"
        return txt

    def loadImageData_fromRawFile(self, param_inputFile="/dev/stdin"):

        num_bytes = self.width * self.height * self.pixelFormat.bytesPerPixel

        if param_inputFile == "/dev/stdin":
            appLog.print_warning(f"Note: Reading {num_bytes} bytes from standard input")
        else:
            appLog.print_verbose(
                f"Note: Reading {num_bytes} bytes from {param_inputFile}"
            )

        with open(param_inputFile, "rb") as src:
            self.loadImageData_fromRawStream(src)

    def loadImageData_fromRawStream(self, src: io.BufferedIOBase):
        """
        Reads raw binary data and returns it as a list of rows.
        :param param_skipBytes: Number of bytes to skip at the start of the input file
        """
        bytes_per_pixel = self.pixelFormat.bytesPerPixel
        formatPackKind = self.pixelFormat.formatPackKind

        ################################################
        #
        # Read raw binary file to 'image_data' (as rows)
        #
        image_data = []
        appLog.print_verbose(
            f"Loading raw image data: [{self.width}x{self.height} of '{formatPackKind}' : skipBytes: {self.skipRawBytes},bytesPerPixel:{bytes_per_pixel}]"
        )
        if self.skipRawBytes > 0:
            src.read(
                self.skipRawBytes
            )  # Don't use file.seek() as this doesn't work on stdin, for example

        appLog.print_verbose(f"Applying formatting extras: {self.formattingExtras}")
        col_conversion = ShuffleLookup(
            self.width, DictUtils.get(self.formattingExtras, "conversion/cols")
        )
        row_conversion = ShuffleLookup(
            self.height, DictUtils.get(self.formattingExtras, "conversion/rows")
        )

        width_in = col_conversion.count
        height_in = row_conversion.count

        for i in range(height_in):
            try:
                row_data = struct.unpack(
                    f"{width_in}{formatPackKind}",
                    src.read(width_in * bytes_per_pixel),
                )
            except struct.error as e:
                raise HandledException(
                    f"Failed to read row {i} of {height_in}: '{e}'. "
                    f"(Expected {width_in * bytes_per_pixel} bytes, "
                    f"but had {len(src.read())} bytes)"
                )

            this_row = col_conversion.shuffle(row_data)
            image_data.append(this_row)  # [0:clip_width])

        if (self.height == height_in) and (self.width == width_in):
            self.imageRows = image_data
        else:
            img_in = np.array(image_data, dtype=self.pixelFormat.asNpDtypeOrNone())
            img_out = cv2.resize(
                img_in, (self.width, self.height), interpolation=cv2.INTER_CUBIC
            )

            _rows = img_out.tolist()
            if isinstance(_rows, list):

                appLog.print_verbose(
                    f"Scale image from {width_in}x{height_in} to {self.width}x{self.height} [4x4 CUBIC]"
                )
                self.imageRows = _rows
            else:
                appLog.print_warning(
                    f"Image rescale {width_in}x{height_in} to {self.width}x{self.height} - Unsuccessful"
                )
                self.imageRows = image_data
                self.height = len(image_data)
                self.width = width_in

    @staticmethod
    def conversionEntry_asTextSuffix(_conversion: dict[str, Any] | None) -> str:
        if _conversion is None:
            return ""
        conversion_txt = f"{DictUtils.getFlattened(_conversion)}"
        conversion_txt = (
            conversion_txt.replace(" ", "")
            .replace("'", "")
            .replace(",", "+")
            .replace(".", "_")
            .replace(":", "~")
            .removeprefix("{")
            .removesuffix("}")
            .replace("count", "")
            .replace("_~", "~")
        )
        return "+" + conversion_txt

    def export_toRawFile(self, param_outputFile="/dev/stdout"):
        if param_outputFile == "/dev/stdout":
            appLog.print_verbose("Note: Writing raw image file to standard output")
        with open(param_outputFile, "wb") as file:
            self.exportAsRaw_stream(file)

    def getImageData(self):
        obj = {}
        obj["format"] = self.pixelFormat.name()
        obj["width"] = self.width
        obj["height"] = self.height

        if self.skipRawBytes > 0:
            obj["offset"] = self.skipRawBytes

        if (
            (self.formattingExtras is not None)
            and (isinstance(self.formattingExtras, dict))
            and (len(self.formattingExtras) > 0)
        ):
            for x in self.formattingExtras:
                if x not in obj:
                    obj[x] = self.formattingExtras[x]
        return obj

    def exportAsRaw_bytes(self):
        streamOut = io.BytesIO()
        self.exportAsRaw_stream(streamOut)
        return streamOut.getvalue()

    def exportAsRaw_stream(self, streamOut):

        ################################################
        #
        # Writes image_data to raw stream
        #
        if self.skipRawBytes > 0:
            streamOut.write(bytes([0] * self.skipRawBytes))

        for this_row in self.imageRows:
            # |Logging| appLog.print_verbose(f"Writing row: {len(this_row)}{format_kind} pixels: {type(this_row)}")
            for x in this_row:
                if not isinstance(x, int):
                    raise HandledException(
                        f"Invalid pixel value: {x} in row {this_row}. Expected integer values."
                    )
            streamOut.write(
                struct.pack(
                    f"{len(this_row)}{self.pixelFormat.formatPackKind}", *this_row
                )
            )

    def exportAsPng(self, streamOut: io.IOBase | None = None):
        try:
            writer = png.Writer(
                self.width,
                self.height,
                greyscale=self.pixelFormat.isGrayscale,  # pyright: ignore[reportArgumentType]
                bitdepth=self.pixelFormat.bitDepth,
            )
            if streamOut is None:
                streamOut = io.BytesIO()
            writer.write(streamOut, self.imageRows)

            return streamOut
        except BaseException as e:
            raise HandledException(f"Export to .png file: {e}")

    def export_toPngFile(self, param_outputFile="/dev/stdout"):
        ################################################
        #
        # Write 'image_rows' to PNG file
        #

        if param_outputFile == "/dev/stdout":
            isConsoleOut = sys.stdout.isatty()

            if isConsoleOut:
                errMsg = f"Should not export a PNG Image to a terminal.\n • If this is intended, append: | cat\n • To view the image  , append: | feh -"
                raise HandledException(errMsg)
        try:
            with open(param_outputFile, "wb") as f:
                self.exportAsPng(f)
        except BaseException as e:
            raise HandledException(f"Export to .png file: {e}")

    @staticmethod
    def create_fromPngFile(
        param_inputFile: str, param_pixelFormat: PixelFormatData | None = None
    ) -> "RawImg":

        try:
            reader = png.Reader(filename=param_inputFile)
            return RawImg.create_fromPngReader(
                reader, param_pixelFormat, src=param_inputFile
            )

        except png.FormatError as e:
            raise HandledException(
                f"PNG format error {e}\n"
                f"Try using `pngcrush --fix --ow {param_inputFile}` to fix the PNG file"
            )

        except BaseException as e:
            raise HandledException(f"Reading from PngFile: {e}  {type(e)}")

    @staticmethod
    def create_fromPngReader(
        reader: png.Reader,
        param_pixelFormat: PixelFormatData | None = None,
        src: str | None = None,
    ) -> "RawImg":

        ################################################
        #
        # Write 'image_rows' to PNG file
        #
        try:
            # Read the image data
            width, height, rowData, metadata = reader.read()

            inNumPlanes = metadata.get("planes")
            if not isinstance(inNumPlanes, int) or inNumPlanes < 1:
                raise Exception(
                    f"Invalid PNG format: 'planes' must be an integer > 0, found: {inNumPlanes}"
                )
            inBitDepth = metadata.get("bitdepth", 8)
            inGreyscale = metadata.get("greyscale")
            inBytesPerPixel = inNumPlanes * (inBitDepth // 8)

            suffix = ""
            if param_pixelFormat is None:
                suffix = " (auto)"

                if (
                    (inGreyscale)
                    and (inNumPlanes == 1)
                    and (inBitDepth in [8, 10, 12, 14, 16])
                ):
                    param_pixelFormat = PIXEL_FORMATS[f"mono{inBitDepth}"]
                else:
                    param_pixelFormat = PIXEL_FORMATS["mono8"]

            sys.stderr.write(
                f"ℹ️  Importing PNG: {width}x{height} {param_pixelFormat.name()}{suffix}: (Planes: {inNumPlanes},depth:{inBitDepth},greyScale:{inGreyscale},bytesPerPixel:{inBytesPerPixel})\n"
            )
            sys.stderr.write(f"ℹ️  Metadata     : {metadata}\n")
            # Convert the row data to a list of tuples
            dataRows = []
            prev_percent = -1
            valuesPerPixel = int(inNumPlanes)  # Not: inBytesPerPixel
            for row in rowData:

                if len(row) != width * valuesPerPixel:
                    raise HandledException(
                        f"Row length mismatch: Expected {width * valuesPerPixel}, got {len(row)}  First entry:{row[0]}"
                    )
                # Convert each row to a tuple of pixel values
                dataRow = []
                for i in range(0, len(row), valuesPerPixel):
                    dataRow.append(
                        param_pixelFormat.convertPixelData_orHandledException(
                            metadata, list(row[i : i + valuesPerPixel])
                        )
                    )

                percent = math.ceil(100 * len(dataRows) / height)

                if percent != prev_percent:
                    sys.stderr.write(f"\rℹ️  Conversion Progress: {percent}%")
                    prev_percent = percent
                dataRows.append(dataRow)
            sys.stderr.write("\n")

            return RawImg(width, height, param_pixelFormat, dataRows)

        except png.FormatError as e:
            lines = [f"PNG format error: {e}"]
            if src is not None:
                lines += [f"Try using `pngcrush --fix --ow {src}` to fix the PNG file"]

            raise HandledException(lines)

        except BaseException as e:
            raise HandledException(f"Importing Png Image: {e}")

    def doSlide(self, dx: int = 0, dy: int = 0):
        if (dx == 0) and (dy == 0):
            # No shift needed, return the original rows
            return

        appLog.print_verbose(f"Transforming image: Slide[{dx},{dy}]")

        for row_index in range(len(self.imageRows)):
            self.imageRows[row_index] = shiftRow(
                self.imageRows[row_index], dx
            )  # Ensure the row is a list


def shiftRow(row, dx: int = 0):
    """
    Shifts a row of pixel data horizontally by dx pixels.
    :param row: List of pixel values in the row
    :param dx: Number of pixels to shift (positive for right, negative for left)
    :return: New row with shifted pixel values
    """
    # |Logging| appLog.print_verbose(f"shift dx:{dx}")
    row_len = len(row)
    if (dx != 0) and (len(row) == 0):
        raise HandledException("RawImg.shiftRow(): Row is empty, cannot shift.")
    if dx > 0:
        new_row = ((row[0],) * dx) + row[:-dx]
    elif dx < 0:
        new_row = row[-dx:] + ((row[-1],) * (-dx))
    else:
        # No horizontal shift
        new_row = row

    # |Logging| appLog.print_verbose(f"Row shifted({dx}): {row_len}->{len(new_row)}")
    if row_len != len(new_row):
        raise HandledException(
            f"RawImg.shiftRow(): Row length changed from {row_len} to {len(new_row)} after shifting."
        )
    return new_row
