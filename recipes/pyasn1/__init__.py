from pythonforandroid.recipe import PythonRecipe


class Pyasn1Recipe(PythonRecipe):
    version = "0.6.5"
    url = "https://files.pythonhosted.org/packages/88/7e/3c0da41061a2021cac7cd524fd57092adbe5b515e8bf9005702e366802e2/pyasn1-{version}.tar.gz"
    sha256sum = "6b11616a6bcf3a40e635f082bb232fa57b5e0dd7f517bd7ddd69ec3794508a47"
    depends = ["setuptools"]
    site_packages_name = "pyasn1"
    call_hostpython_via_targetpython = False


recipe = Pyasn1Recipe()
