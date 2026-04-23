import base64
import hashlib
import json
import os
import shutil
import sys
import tempfile
from typing import Any, NoReturn, Tuple

################################################################################
#
# Shared Libraries
#
shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic import simpleUtils
from ukko_pylibs.basic.simpleUtils import Utils as Utils
import ukko_pylibs.basic.appSupport as app
from ukko_pylibs.basic.class_HandledException import HandledException

################################################################################
#


def raiseHandledException(errmsg: str) -> NoReturn:
    raise HandledException(errmsg)


def loadJsonWithExtras(
    string_or_path: str, inputKind: str = "JSON", exceptionOnError: bool = True
) -> tuple[str | None, dict[str, Any]]:
    jParams_ = string_or_path
    if jParams_ == "-":
        jParams_ = "@/dev/stdin"
    jParams_filePath = (
        jParams_[1:]
        if (jParams_.startswith("@") and not jParams_.startswith("@/dev/"))
        else None
    )
    inputJson = loadJson(jParams_)
    if inputJson is None:
        inputJson = {}
    return (jParams_filePath, inputJson)


def jsonObjFromFileWithExtras(
    inputJsonFile: str, inputKind: str = "JSON", giveWarningOnFileMissing: bool = True
) -> dict[str, Any]:

    result = loadJsonDictFromFile(
        inputJsonFile,
        inputKind,
        exceptionOnError=False,
        giveWarningOnFileMissing=giveWarningOnFileMissing,
    )
    result["_src"] = inputJsonFile

    return result


def loadJsonFromFile(
    inputJsonFile: str,
    inputKind: str = "JSON",
    exceptionOnError: bool = True,
    note_deprecation: bool = True,
) -> Any:
    if note_deprecation:
        app.deprecationWarning(
            "The function 'loadJsonFromFile' is deprecated. Please use 'loadJsonDictFromFile' if appropriate"
        )

    return loadJsonDictFromFile(inputJsonFile, inputKind, exceptionOnError)


def loadJsonDictFromFile(
    inputJsonFile: str,
    inputKind: str = "JSON",
    exceptionOnError: bool = True,
    giveWarningOnFileMissing: bool = True,
) -> dict[str, Any]:
    fname_friendly = app.pathDisplay(inputJsonFile)
    errmsg = "Unknown Error"
    showWarning = True
    try:
        if inputJsonFile == "/dev/stdin":
            app.appLog.print_verbose(f"Note: Reading {inputKind} from standard input")
        if not os.path.exists(inputJsonFile) and not giveWarningOnFileMissing:
            # Avoid throwing exception on missing file if we're not giving a warning about it.
            # This eases our debugging process when we halt on raised exceptions
            showWarning = False
            errmsg = f"The {inputKind} '{fname_friendly}' was not found."
        else:
            with open(inputJsonFile, "r") as file:
                return json.load(file)
    except FileNotFoundError:
        if not giveWarningOnFileMissing:
            showWarning = False
        errmsg = f"The {inputKind} '{fname_friendly}' was not found."
    except json.JSONDecodeError:

        errmsg = f"The {inputKind} '{fname_friendly}' doesn't contain valid JSON"
    except Exception as e:
        errmsg = f"The {inputKind} '{fname_friendly}' gave an exception: {e}"

    except KeyboardInterrupt as e:
        app.exitOnException(e)
    except SystemExit as e:
        app.exitOnException(e)

    if showWarning:
        app.appLog.print_warning(errmsg)
    if exceptionOnError:
        raiseHandledException(errmsg)
    else:
        return {"error": errmsg}


def loadJson(
    inputJson: str,
    inputKind: str = "JSON",
    exceptionOnError: bool = True,
    assumeDict: bool = False,
) -> dict[str, Any] | None:
    sourceDescription = inputJson
    errmsg = "Unknown Error"
    if (inputJson == None) or (inputJson == "") or (inputJson == "null"):
        return None
    inputJsonFile = "??"

    try:
        if (inputJson == "-") or (inputJson == "@-") or (inputJson == "@"):
            inputJson = "@/dev/stdin"
        loadedJson: dict[str, Any] = {}
        if inputJson.startswith("@"):
            if assumeDict:
                return loadJsonDictFromFile(inputJson[1:], inputKind, exceptionOnError)
            else:
                return loadJsonFromFile(inputJson[1:], inputKind, exceptionOnError)
        else:
            sourceDescription = f"'{inputJson}'"
            loadedJson = json.loads(inputJson)
        return loadedJson
    except json.JSONDecodeError:
        errmsg = f"Unable to load {inputKind}: {sourceDescription} wasn't valid JSON"
    except Exception as e:
        errmsg = f"Unable to load {inputKind} from '{app.pathDisplay(inputJson)}': A [{type(e).__name__}] exception occurred: {e}"

    if exceptionOnError:
        raiseHandledException(errmsg)
    else:
        return {"error": errmsg}


def loadJson_dict_withSourceDescription_orException(
    inputJson: str, inputKind: str = "JSON", defaultDescription: str = "input"
) -> Tuple[dict[str, Any], str]:
    result = loadJson_dict(inputJson, inputKind, exceptionOnError=True)
    sourceDescription = defaultDescription
    if (inputJson == None) or (inputJson == "") or (inputJson == "null"):
        pass
    elif (
        (inputJson == "-")
        or (inputJson == "@-")
        or (inputJson == "@")
        or (inputJson == "@/dev/stdin")
    ):
        pass
    elif inputJson.startswith("@"):
        sourceDescription = f"{app.pathDisplay(inputJson[1:])}"

    return (result, sourceDescription)


def loadJson_dict(
    inputJson: str, inputKind: str = "JSON", exceptionOnError: bool = True
) -> dict[str, Any]:
    result = loadJson(inputJson, inputKind, exceptionOnError, assumeDict=True)
    if not isinstance(result, dict):
        if exceptionOnError:
            raiseHandledException(
                f"Expected {inputKind} to be a JSON object , but got: {type(result).__name__}"
            )
        else:
            result = {"error": "Not a JSON Object", "contents": result}
    return result


def loadBytesFromFile_orHandledException(
    inputBinaryFile: str, what: str = "binary data"
) -> bytes:
    try:
        if inputBinaryFile == "-":
            inputBinaryFile = "/dev/stdin"
        if inputBinaryFile == "/dev/stdin":
            app.appLog.print_info(f"Note: Reading {what} from standard input")
        with open(inputBinaryFile, "rb") as file:
            file_bytes = file.read()
        return file_bytes
    except Exception as e:
        raiseHandledException(
            f"Unable to load {what} from file '{app.pathDisplay(inputBinaryFile)}': A [{type(e).__name__}] exception occurred: {e}"
        )


def exportToFile_orHandledException(
    outputFilename: str, fileContents, format: str = "data", isText: bool = False
) -> Tuple[str, int]:
    try:
        if (outputFilename == "-") or (outputFilename == "/dev/stdin"):
            outputFilename = "/dev/stdout"
        app.appLog.print_verbose(
            f"Exporting {format:<4} to {outputFilename} ({'None' if (fileContents is None) else simpleUtils.pluralize(len(fileContents), 'byte')})"
        )

        if outputFilename == "/dev/null":
            return outputFilename, 0
        if fileContents is None:
            if not outputFilename.startswith("/dev/"):
                app.appLog.print_verbose(
                    f"Exporting {format:<4} -- erasing output file '{outputFilename}'"
                )
                if os.path.exists(outputFilename):
                    try:
                        os.remove(outputFilename)
                    except PermissionError:
                        raiseHandledException(
                            f"Permission denied to delete the file '{outputFilename}'"
                        )
                    except Exception as e:
                        raiseHandledException(
                            f"An error occurred while deleting the file '{outputFilename}': {e}"
                        )
            return outputFilename, 0

        if outputFilename == "/dev/stderr":
            pass
        else:
            if outputFilename == "/dev/stdout":

                isConsoleOut = sys.stdout.isatty()

                if (isConsoleOut) and not (isText):
                    errMsg = f"Should not export binary data (such as {format}) to a terminal.  Did you intend to add: | xxd ?\n • If this is intended,  append: | cat"
                    if (
                        (format.lower() == "image")
                        or (format.lower() == "png")
                        or (format.lower().startswith("image/"))
                    ):
                        errMsg += f"\n • To view the {(format+','):<8} append: | feh -"
                    if "annotateddata" in format.lower():
                        errMsg += "\n • To view as JSON,      append: --outputFormat=json:files"
                    if "protobuf" in format.lower():
                        errMsg += (
                            "\n • To view the protobuf, append: | protoc --decode_raw"
                        )
                    raise HandledException(errMsg)
        with open(outputFilename, "wb") as file:
            file_bytes = file.write(fileContents)
            return outputFilename, file_bytes

    except Exception as e:
        prefix = ""
        if isinstance(e, HandledException):
            prefix = f"A '{type(e).__name__}' exception occurred: "
        raise HandledException(
            f"Unable to export to file '{outputFilename}'\n{prefix}{e}"
        )


def md5_create_verifier(fname: str, base_path: str | None = None) -> str:
    with open(fname, "rb") as file:
        raw_bytes = file.read()
        md5hash_value = hashlib.md5(raw_bytes).hexdigest()
    if base_path is not None:
        relative_path = os.path.relpath(fname, base_path)
    else:
        relative_path = fname
    return md5hash_value + "  " + relative_path


def create_cleanOutputDir(path: str | None, config_txt: str | None):
    if not path:
        return
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)
    if config_txt is None:
        return
    with open(f"{path}/config.json", "w") as text_file:
        text_file.write(config_txt)


def doExportBitstream(
    bitstream: bytes | None,
    exportOption: str,
    format: str = "unknown",
    ext: str = ".raw",
    suggestedFilenameNoExt: str | None = None,
) -> dict[str, Any]:
    if bitstream is None:
        return {}
    if exportOption == "none":
        return {}
    result: dict[str, Any] = {"numBytes": len(bitstream)}

    if format != "unknown" and format != "bitstream":
        result["format"] = format

    # |Logging| appLog.print_verbose(f"!!!!!! doExportBitstream: exportOption:{exportOption} format:{format} ext:{ext}")
    if exportOption != "overview":
        result["md5"] = hashlib.md5(bitstream).hexdigest()
        out_filename = None
        if exportOption == "base64":
            result["base64"] = base64.b64encode(bitstream).decode("utf-8")
        elif exportOption.startswith("file:"):
            out_filename = exportOption.removeprefix("file:").removesuffix(ext) + ext
        elif exportOption == "file" or exportOption == "files":
            if (suggestedFilenameNoExt is not None) and (suggestedFilenameNoExt != ""):
                out_filename = suggestedFilenameNoExt + ext
            else:
                prefix = f"{format.replace('/','_')}".removesuffix(
                    ext.removeprefix(".")
                ).removesuffix("_")

                out_filename = (
                    tempfile.gettempdir().removesuffix("/")
                    + "/"
                    + prefix
                    + "_"
                    + result["md5"]
                    + ext
                )

        if out_filename is not None:
            with open(out_filename, "wb") as fileout:
                app.appLog.print_verbose(f"Exporting to {fileout.name}")
                fileout.write(bitstream)
                result["file"] = fileout.name
    return result


def filenameSanitise(link: str | list[str], nicen: bool = True) -> str:
    """Takes a string (or strings) and returns a basic, filesafe path
    Note: This path is not guaranteed to be unique, use MD5sum if that is needed"""
    if link is None:
        return ""
    elif isinstance(link, list):
        links: list[str] = []
        for obj in link:
            txt = filenameSanitise(obj)
            if txt != "":
                links.append(txt)
        return os.path.sep.join(links)
    else:
        txt = str(link)
        replace_chars = ["\\", "/", ":", '"', "<", ">", "|", "*", "?"]
        if nicen:
            replace_chars += [" ", "$", "&", "'", "!", "(", ")"]
        for ch in replace_chars:
            txt = txt.replace(ch, "_")

        while txt.startswith("_"):
            txt = txt[1:]
        while txt.endswith("_"):
            txt = txt[:-1]

        while "__" in txt:
            txt = txt.replace("__", "_")
        return txt
