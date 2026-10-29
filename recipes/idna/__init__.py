from pythonforandroid.recipe import PythonRecipe


class IdnaRecipe(PythonRecipe):
    version = "3.20"
    url = "https://files.pythonhosted.org/packages/f5/08/8eea9d4b8302028f3abb2c0813953f7aec26d33b7a8960ed760e65ff29fa/idna-{version}.tar.gz"
    sha256sum = "a7db850025b95ded1eae8a46181a1a6c56c92c96f0e2b005d9ff8dc0210cab44"
    depends = ["setuptools"]
    site_packages_name = "idna"
    call_hostpython_via_targetpython = False


recipe = IdnaRecipe()
