from pythonforandroid.recipe import PythonRecipe


class CertifiRecipe(PythonRecipe):
    version = "2026.10.23"
    url = "https://files.pythonhosted.org/packages/fd/11/b524cbd9bbdaca58608e4cf4053fd463417549e1959fa8d3aa18319f9555/certifi-{version}.tar.gz"
    sha256sum = "a9895e6e2758b371e0545e321a3a8fd1fcfd9829ada8824a936dfb16aaaf36cd"
    depends = ["setuptools"]
    site_packages_name = "certifi"
    call_hostpython_via_targetpython = False


recipe = CertifiRecipe()
