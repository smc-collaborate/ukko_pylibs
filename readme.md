# `ukko_pylibs` : Shared Python Libraries  [Revision: `v0.1.3-wip`]
## Importing ##

To avoid multiple copies of python modules existing in your project always import them from `ukko_pylibs`.<br>
Using another prefix (such as `from libs.ukko_pylibs.app as app` will import as a new module).
```python
#####################################################################
#
# Shared Libraries
#

shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../libs/")
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

## Hidden Options ##

| Option                                               | Example Use                                                         |
|------------------------------------------------------|---------------------------------------------------------------------|
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

```
├── app
│   ├── appSupport.py
│   ├── class_Configuration.py
│   └── class_ParamSpec.py
├── basic
│   ├── class_DataContents.py
│   ├── class_HandledException.py
│   ├── fileUtils.py
│   ├── logger.py
│   ├── simpleUtils.py
│   └── valueHandling.py
├── _external
│   └── parseProtoBuf.py
├── imageProcessing
│   ├── class_PixelFormatData.py
│   └── rawimgProcess.py
├── markdown
│   └── class_MarkdownTable.py
├── network
│   ├── basicTcpServer.py
│   ├── class_CmdServers.py
│   ├── class_DataLink_.py
│   ├── class_DataStreamer.py
│   ├── class_IPhyConnection.py
│   ├── class_PhyConnection_Serial.py
│   ├── class_PhyConnection_Tcp.py
│   └── shared_link_code.py
├── readme.md
├── schemaHandling
│   ├── appTemplate_schemas.py
│   ├── class_MarkdownSchemaDoc.py
│   └── schemaProcessing.py
└── transferableData
    ├── class_ITransferableData.py
    └── customising.py
```

## Full Regression Testing ##

This is done with `ukko_full` - which has test scripts and includes `ukko_bashlibs`
