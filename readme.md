# `ukko_pylibs` : Shared Python Libraries  [Revision: `v0.1.3-wip`] #

## Importing ##

To avoid multiple copies of python modules existing in your project always import them from `ukko_pylibs`.<br>
Using another prefix (such as `from libs.ukko_pylibs.app as app` will import as a new module).

```python
################################################################################
#
# Ensure shared Packages are available
#

packages_dir = str((Path(__file__).parent.parent/'pkgs').absolute())
if not packages_dir.endswith('/pkgs') or not os.path.exists(packages_dir):
    exit(f"❌  {__file__}\n    Misconfigured: [/path/to]/pkgs is not {packages_dir}")

if packages_dir not in sys.path:
    sys.path.append(packages_dir)
#
################################################################################

```

## Development Notes ##

Care has been taken to support Python versions from **3.10.12** to **3.14**<br>
This means that it can run with **Ubuntu 22.04**, **Ubuntu 24.04** & **Ubuntu 26.04** (Four years of LTS)

Issues:
`ukkoTestCommand verify --stdout='Hello World\n' -- echo 'Hello Worldx'` -> --stdout='Hello World\\n' when giving a suggestion ...

### Dependencies Required ###

This is largely handled by by the ukko installer for the project.

Points to note:

* The full list of dependancies is in **`requirements/requirements-python3.##.txt`**
* An example installer is in [**tools/do-create-sample-venv.sh ⧉**](tools/do-create-sample-venv.sh)

## Hidden Options ##

| Option                                                    | Example Use                                                         |
|-----------------------------------------------------------|---------------------------------------------------------------------|
| `--debug-info=[none/app-info/app-as-run/config-info/all]` | `annotatedData --debug-info=app-as-run \| jq '.appAsRun.appValues'` |

## Style ##

Style can be enforced with **`pre-commit install`**<br>

Check with: **`pre-commit run -a`**

## Organisation ##

```text
│
├── readme.md
│
├── pkgs
│   ├── ukkoCommonCollection     -- ⭐ Usually your app can just include this - it hass all the common ones in
│   │
│   ├── appAssist
│   ├── appLogging
│   ├── dictionaryWalker
│   ├── dictUtils
│   ├── escapeFormatting
│   ├── fileUtils
│   ├── imageProcessing
│   ├── markdown
│   ├── network
│   ├── prettyData
│   ├── prettyText
│   ├── schemaHandling
│   ├── sysInfo
│   ├── transferableData
│   ├── ukkoAppTemplates
│   ├── ukkoDataFormats
│   ├── ukkoStyling
│   ├── ukkoUtils
│   └── ukkoValueHandling
│
├── requirements
│   ├── requirements-python3.10.txt
│   ├── requirements-python3.12.txt
│   └── requirements-python3.14.txt
│
├── testing
│   └── test-run.sh
│
└── tools

```

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

## Full Regression Testing ##

This is done with `ukko_full` - which has test scripts and includes `ukko_bashlibs`
