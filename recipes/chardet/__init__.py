from pythonforandroid.recipe import PythonRecipe


class ChardetRecipe(PythonRecipe):
    version = "7.7.0"
    url = "https://files.pythonhosted.org/packages/47/92/3d893ac5d338b9a9af34c5b517d77492dcea8a10254254eead4215a96f3f/chardet-{version}.tar.gz"
    sha256sum = "0ba38a05201b0abf7570c12d8af45c30b2af835bd5cc52bfc7105082eda82c1e"
    depends = ["setuptools"]
    site_packages_name = "chardet"
    call_hostpython_via_targetpython = False


recipe = ChardetRecipe()
