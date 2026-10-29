from pythonforandroid.recipe import Recipe
from os.path import join
from pythonforandroid.util import ensure_dir


class LibThorVGRecipe(Recipe):
    name = "libthorvg"
    version = "1.0.5"

    def should_build(self, arch):
        return False

    def get_include_dir(self, arch):
        include_dir = join(self.get_build_dir(arch.arch), "install", "include")
        ensure_dir(join(include_dir, "thorvg-1"))
        return include_dir

    def build_arch(self, arch):
        pass


recipe = LibThorVGRecipe()
