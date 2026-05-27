from .version import __version__


def main(*args, **kwargs):
    from .assertFlip import main as _main
    return _main(*args, **kwargs)
