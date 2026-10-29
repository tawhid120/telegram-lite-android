from pythonforandroid.recipe import PythonRecipe


class SixRecipe(PythonRecipe):
    version = "1.17.0"
    url = "https://files.pythonhosted.org/packages/94/e7/b2c673351809dca68a0e064b6af791aa332cf192da575fd474ed7d6f16a2/six-{version}.tar.gz"
    sha256sum = "ff70335d468e7eb6ec65b95b99d3a2836546063f63acc5171de367e834932a81"
    depends = ["setuptools"]
    site_packages_name = "six"
    call_hostpython_via_targetpython = False


recipe = SixRecipe()
