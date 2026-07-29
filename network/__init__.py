################################################################################
#
# Shared Libraries
#
import os, sys
from pathlib import Path

shared_dir = os.path.abspath(f"{Path(__file__).parent}/../")
if shared_dir not in sys.path:
    sys.path.append(shared_dir)

from ukko_pylibs.network.basicTcpServer import BasicTcpServer

__all__ = [
    "BasicTcpServer",
]
