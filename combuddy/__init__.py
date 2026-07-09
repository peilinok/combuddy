from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("combuddy")
except PackageNotFoundError:          # source tree / frozen build missing .dist-info
    __version__ = "0.0.0+dev"
