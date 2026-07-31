#!/usr/bin/env bash
PROJ_DIR="$(dirname "$(realpath -m "${BASH_SOURCE[0]}")")/../"

cd "${PROJ_DIR}" || exit 13

##################
#

python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate # to enter the virtual environment - may be at other locations

python3_subver="$(python3 --version | sed 's|^Python 3\.||g' | sed 's|\..*$||g')"

requirements_fname="requirements/requirements-python3.${python3_subver}.txt"
pip install -r "${requirements_fname}" | grep -v "^Requirement already satisfied:"
echo "Installed from: ${requirements_fname}"

font_target=".venv/lib/python3.${python3_subver}/site-packages/cv2/qt/fonts"
if [[ ! -d "/usr/share/fonts/truetype/dejavu" ]] && [[ -d "$font_target" ]] ; then
    #
    # Install fonts for QT apps - otherwise it complains about not finding them
    #
    ln -s "$font_target" "/usr/share/fonts/truetype/dejavu"
fi


# |Alernative Python| try:
# |Alernative Python|
# |Alernative Python|   import os
# |Alernative Python|
# |Alernative Python|   if not os.path.exists("/usr/share/fonts/truetype/dejavu"):
# |Alernative Python|       import cv2
# |Alernative Python|       font_target = os.path.join(os.path.dirname(cv2.__file__), "qt", "fonts")
# |Alernative Python|       if os.path.exists(font_target):
# |Alernative Python|            os.mklink("/usr/share/fonts/truetype/dejavu",font_target)
# |Alernative Python| except:
# |Alernative Python|   pass
# |Alernative Python|
