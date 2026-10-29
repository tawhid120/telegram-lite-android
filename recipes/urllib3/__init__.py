from pythonforandroid.recipe import PythonRecipe


class Urllib3Recipe(PythonRecipe):
    version = "2.8.0"
    url = "https://files.pythonhosted.org/packages/e3/05/b17359e1cefb4f909b5e40b1b90a496d987258916dbbf88e842c729f510e/urllib3-{version}.tar.gz"
    sha256sum = "63bf2ead4c879426ebf22ef2a781eeb4aa3b4ae798a0435506f8687fd5bb9b63"
    depends = ["setuptools"]
    site_packages_name = "urllib3"
    call_hostpython_via_targetpython = False


recipe = Urllib3Recipe()
