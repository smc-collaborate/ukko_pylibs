# `ukko_pylibs` : Shared Python Libraries  [Revision: `v0.1.3-wip`] #

## Importing ##

To avoid multiple copies of python modules existing in your project always import them from `ukko_pylibs`.<br>
Using another prefix (such as `from libs.ukko_pylibs.app as app` will import as a new module).

```python
#####################################################################
#
# Shared Libraries
#

shared_dir = os.path.abspath(f"{Path(__file__).parent}/../libs/")
if shared_dir not in sys.path: sys.path.append(shared_dir)

from ukko_pylibs import app,Utils,appLog
#
#####################################################################
```

## Development Notes ##

Care has been taken to support Python versions from **3.10.12** to **3.14**<br>
This means that it can run with **Ubuntu 22.04**, **Ubuntu 24.04** & **Ubuntu 26.04** (Four years of LTS)

Issues:
`ukkoTestCommand verify --stdout='Hello World\n' -- echo 'Hello Worldx'` -> --stdout='Hello World\\n' when giving a suggestion ...

### Dependencies Required ###

This is largely handled by by the ukko installer for the project, but a shorthand guide is:

```bash

python3 -m venv .venv
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

```

## Hidden Options ##

| Option                                                    | Example Use                                                         |
|-----------------------------------------------------------|---------------------------------------------------------------------|
| `--debug-info=[none/app-info/app-as-run/config-info/all]` | `annotatedData --debug-info=app-as-run \| jq '.appAsRun.appValues'` |

## Style ##

Style can be enforced with **`pre-commit install`**<br>

Check with: **`pre-commit run -a`**

## Organisation ##

There is a heirachy:

To avoid circular imports:

### Basic Modules ##

| Module               | Permitted ukko Module level dependencies       |
|----------------------|------------------------------------------------|
| `external`           | None                                           |
| `basic`              | `basic` + `_external`                          |

### Mid Level Modules ##

| Module               | Permitted ukko Module level dependencies       |
|----------------------|------------------------------------------------|
| `imageProcessing`    | (self) + Basic Modules                         |
| `markdown`           | (self) + Basic Modules                         |
| `transferableData`   | (self) + Basic Modules                         |

### High Level Modules ###

| Module               | Permitted ukko Module level dependencies       |
|----------------------|------------------------------------------------|
| `network`            | (self) + Basic Modules + Mid Level Modules     |
| `schemaHandling`     | (self) + Basic Modules + Mid Level Modules     |
| `app`                | (self) + Basic Modules + Mid Level Modules     |

The exceptions are app Templates which are full apps:

* **schemaHandling/`appTemplate_schemas.py`**

```text
.
├── appAssist
│   ├── appChoices.py
│   ├── appHelp.py
│   ├── appSupport.py
│   ├── class_Configuration.py
│   └── class_ParamSpec.py
├── appTemplates
│   ├── jsonLineStreaming.py
│   └── ukko_pylibs -> ..
├── basic
│   ├── class_DataContents.py
│   ├── class_HandledException.py
│   ├── class_JsonData.py
│   ├── class_SimpleLogger.py
│   ├── escapeFormatting.py
│   ├── fileUtils.py
│   ├── logger.py
│   ├── prettyTable.py
│   ├── simpleUtils.py
│   ├── sparseLists.py
│   ├── styling.py
│   ├── sysInfo.py
│   └── valueHandling.py
├── _external
│   └── parseProtoBuf.py
├── imageProcessing
│   ├── class_PixelFormatData.py
│   ├── __init__.py
│   └── rawimgProcess.py
├── __init__.py
├── _lib_testing
│   ├── __pycache__
│   │   └── test-PrettyTables.cpython-312.pyc
│   ├── samples
│   │   ├── render-barred.json
│   │   ├── table-small.json
│   │   └── table-wide.json
│   ├── test-PrettyTables.py
│   ├── test-run.sh
│   └── ukko_pylibs -> ..
├── markdown
│   └── class_MarkdownTable.py
├── network
│   ├── appAccess.py
│   ├── basicTcpServer.py
│   ├── class_CmdServers.py
│   ├── class_DataLink_.py
│   ├── class_DataStreamer.py
│   ├── class_IPhyConnection.py
│   ├── class_PhyConnection_Serial.py
│   ├── class_PhyConnection_Tcp.py
│   ├── __init__.py
│   └── shared_link_code.py
├── readme.md
├── schemaHandling
│   ├── appTemplate_schemas.py
│   ├── class_MarkdownSchemaDoc.py
│   └── schemaProcessing.py
└── transferableData
    ├── class_ITransferableData.py
    ├── customising.py
    └── __init__.py

```

## Full Regression Testing ##

This is done with `ukko_full` - which has test scripts and includes `ukko_bashlibs`
