from pythonforandroid.recipe import PythonRecipe


class PyaesRecipe(PythonRecipe):
    version = "1.6.1"
    url = "https://files.pythonhosted.org/packages/44/66/2c17bae31c906613795711fc78045c285048168919ace2220daa372c7d72/pyaes-{version}.tar.gz"
    sha256sum = "02c1b1405c38d3c370b085fb952dd8bea3fadcee6411ad99f312cc129c536d8f"
    depends = ["setuptools"]
    site_packages_name = "pyaes"
    call_hostpython_via_targetpython = False


recipe = PyaesRecipe()
