# `ukko_pylibs` : Shared Python Libraries  [Tag: `v0.1.0`]

## Development Notes ##

1. **How to import**<br>
  To avoid multiple copies of python modules existing in your project always import them from `ukko_pylibs`.<br>
   Using another prefix (such as `import app.appSupport as app` will import as a new module).
   ```python
   ################################################################################
   #
   # Shared Libraries
   #
   shared_dir = os.path.abspath(f"{os.path.dirname(__file__)}/../common/")
   if shared_dir not in sys.path: sys.path.append(shared_dir)

   import ukko_pylibs.app.appSupport as app
   #
   #################################################################################
   ```

2. Care has been taken to support Python versions from **3.10.12** to **3.14**<br>
   This means that it can run with **Ubuntu 22.04**, **Ubuntu 24.04** & **Ubuntu 26.04** (Four years of LTS)

## Style ##

Style can be enforced with **`pre-commit install`**<br>

Check with: **`pre-commit run -a`**


## Full Regression Testing ##

This is done with `ukko_full` - which has test scripts and includes `ukko_bashlibs`
