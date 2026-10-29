from pythonforandroid.recipe import PythonRecipe


class TelethonRecipe(PythonRecipe):
    version = "1.45.0"
    url = "https://files.pythonhosted.org/packages/d5/07/b23b6cc73cd994763fbd641d196904f56cc966035eda841275b5689c6e5f/telethon-{version}.tar.gz"
    sha256sum = "4cb7ae269b8ab9dad9fc490b859f0bc2f885121e990f5b20407b1faa0db2a1d9"
    depends = ["setuptools", "pyaes", "rsa"]
    site_packages_name = "telethon"
    call_hostpython_via_targetpython = False


recipe = TelethonRecipe()
