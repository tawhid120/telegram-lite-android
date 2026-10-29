from pythonforandroid.recipe import PythonRecipe


class RsaRecipe(PythonRecipe):
    version = "4.9.1"
    url = "https://files.pythonhosted.org/packages/da/8a/22b7beea3ee0d44b1916c0c1cb0ee3af23b700b6da9f04991899d0c555d4/rsa-{version}.tar.gz"
    sha256sum = "e7bdbfdb5497da4c07dfd35530e1a902659db6ff241e39d9953cad06ebd0ae75"
    depends = ["setuptools", "pyasn1"]
    site_packages_name = "rsa"
    call_hostpython_via_targetpython = False


recipe = RsaRecipe()
