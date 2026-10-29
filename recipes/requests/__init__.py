from pythonforandroid.recipe import PythonRecipe


class RequestsRecipe(PythonRecipe):
    version = "2.34.2"
    url = "https://files.pythonhosted.org/packages/ac/c3/e2a2b89f2d3e2179abd6d00ebd70bff6273f37fb3e0cc209f48b39d00cbf/requests-{version}.tar.gz"
    sha256sum = "f288924cae4e29463698d6d60bc6a4da69c89185ad1e0bcc4104f584e960b9ed"
    depends = ["setuptools", "certifi", "chardet", "idna", "urllib3"]
    site_packages_name = "requests"
    call_hostpython_via_targetpython = False


recipe = RequestsRecipe()
