# `ukko_pylibs` : Shared Python Libraries  [Revision: `v0.2.4-wip` ] #

## Example Usage ##

```python
from ukkoCommonCollection import app

APP_VERSION = "1.0.2"

def main():

    appChoices = app.Define(
        {
            "version": APP_VERSION,
            "description": f"I Say Hello",
            "options": [
                {"name": "person", "default": "Fred", "mayBeDirect": True},
                {"name": "helloCount", "min": 1, "max": 30, "default": 1},
            ],
        }
    ).parseParams()

    if appChoices["person"].lower() == "mary":
        app.error_exit_withSuggestion(
            "Mary doesn't like you.",
            f"Try {app.appInfo_cmdWithVariant_styled({'person':'Tom'})} instead",
        )

    for _ in range(appChoices["helloCount"]):
        print(f"Hello {appChoices['person'].title()}")

if __name__ == "__main__":
    app.doRun(main)
```

## Importing ##

The simplest way to import the most commonly used entries is to:

```python
from ukkoCommonCollection import (
    styling,
    ns_asText,
    asJsonStr,
    appLog,
    app,
    appConfig,
    PrettyData,
    dictUtils,
    ukkoUtils,
    prettyText,
)
```

You can ensure that the packages are available for import via several different ways:

1. Use **`do-build-and-install.sh`** installer:

    ```bash
    #!/bin/bash -eu

    function apps_doInstallOrClean()
    {
        installEditablePythonPkgs "git@github.com:smc-collaborate/ukko_pylibs"  --ref='ver:v0.2.3'
        do_pyInstall_orClean "hello.py"
    }

    # shellcheck source=/dev/null
    source "$(dirname "$(realpath -m "${BASH_SOURCE[0]}")")/libs/_loader-shim.inc.bash"
    ```

    If using this installer then debugging is a breeze, as it auto-suggests adding **`_links/ukko_pylibs/pkgs`** to `.vscode/settings.json`:

    ```json
    {
        "python.analysis.extraPaths":[
            "${workspaceFolder}/libs",
            "${workspaceFolder}/_links/ukko_pylibs/pkgs"
        ]
    }
    ```

2. Use **pip install**:

   ```bash
   pip install -e "${CHECKOUT_DIR}/pkgs/"
   ```

3. Add the entry to the **`requirements.txt`** file:

    ```requirements.txt
    -e git+ssh://git@github.com/smc-collaborate/ukko_pylibs@HASH#egg=ukko_fullCollection&subdirectory=pkgs
    ```

In the latter two import methods, for debugging you may want to add `"${CHECKOUT_DIR}/pkgs"` to `.vscode/settings.json`:

```json
{
    "python.analysis.extraPaths":[
        "${workspaceFolder}/libs",
        "${env:HOME}/gits-shared/github.com/smc-collaborate/ukko_pylibs/branch_v0.2.3/pkgs"
    ]
}
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
├── requirements.txt
├── pkgs
│   ├── pyproject.toml
│   │
│   ├── ukkoCommonCollection     -- ⭐ Usually your app can just include this - it collects all the common functionality
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
│   ├── osAccess
│   ├── transferableData
│   ├── ukkoAppTemplates
│   ├── ukkoDataFormats
│   ├── ukkoStyling
│   ├── ukkoUtils
│   └── ukkoValueHandling
│
├── readme.md
│
├── testing
│   └── test-run.sh
└── tools

```

The unusual entries are:

| Package                    | Functionality                                                    |
|----------------------------|------------------------------------------------------------------|
| **`ukkoCommonCollection`** | A collection of the common functionality for ease of integration |
| **`ukkoAppTemplates`**     | A collection of app templates                                    |

## Full Regression Testing ##

This is done with `ukko_full` - which has test scripts and includes `ukko_bashlibs`

## Dev notes ##

Note: For ubuntu:22.04 (Python 3.10) compliance, we need to change styling from PEP695's type parameter syntax:

eg:

```python
class SparseList[ContentKind]:
```

to the older

```python
from typing import Generic, TypeVar

ContentKind = TypeVar("ContentKind")

class SparseList(Generic[ContentKind]):
```
