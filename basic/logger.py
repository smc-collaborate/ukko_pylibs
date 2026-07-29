import os, sys
from pathlib import Path

################################################################################
#
# Add project root directory to system path


shared_dir = os.path.abspath(f"{Path(__file__).parent}/../../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.basic.class_SimpleLogger import SimpleLogger

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


appLog = SimpleLogger("ukko_pylibs", onVerbosityThresholdChange=logger_traditional_set)
