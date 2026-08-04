import os, sys
from pathlib import Path
import time


from appLogging.class_SimpleLogger import SimpleLogger

################################################################################


def logger_traditional_set(logLevel: int):
    import logging

    if logLevel == SimpleLogger.MsgKind_ERROR:
        logging.getLogger().setLevel(logging.ERROR)
    elif logLevel == SimpleLogger.MsgKind_WARNING:
        logging.getLogger().setLevel(logging.WARNING)
    elif logLevel == SimpleLogger.MsgKind_INFO:
        logging.getLogger().setLevel(logging.INFO)
    elif logLevel == SimpleLogger.MsgKind_DETAIL:
        logging.getLogger().setLevel(logging.DEBUG)
    elif logLevel == SimpleLogger.MsgKind_TEDIOUS:
        logging.getLogger().setLevel(logging.DEBUG - 1)


appLog = SimpleLogger(
    "ukkoAppLogging", onVerbosityThresholdChange=logger_traditional_set
)


first_ns: int | None = None


def timeFromStart_text(time_in_ns: int | None = None) -> str:
    global first_ns

    time_ns = time_in_ns if time_in_ns is not None else time.monotonic_ns()
    if first_ns is None:
        first_ns = time_ns
        return "0 ms [Start]"
    else:
        diff_ms = (time_ns - first_ns) / 1_000_000  # Convert to milliseconds
        return f"{diff_ms:.1f} msᵀ"  # ᵀ marker indicates a warning - assuming time is synced perfectly between the spacecraft and this system
