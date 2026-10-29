from pythonforandroid.recipe import PythonRecipe


class FiletypeRecipe(PythonRecipe):
    version = "1.2.0"
    url = "https://files.pythonhosted.org/packages/bb/29/745f7d30d47fe0f251d3ad3dc2978a23141917661998763bebb6da007eb1/filetype-{version}.tar.gz"
    sha256sum = "66b56cd6474bf41d8c54660347d37afcc3f7d1970648de365c102ef77548aadb"
    depends = ["setuptools"]
    site_packages_name = "filetype"
    call_hostpython_via_targetpython = False


recipe = FiletypeRecipe()
