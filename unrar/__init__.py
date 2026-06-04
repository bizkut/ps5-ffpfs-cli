"""Self-contained UnRAR Python bindings.

This package compiles the official UnRAR C++ source into a native Python
extension. No external unrar/7z binaries are required.
"""

import os
import sys

if hasattr(sys, '_MEIPASS'):
    # In a PyInstaller bundle, extension modules collected via --collect-binaries
    # are extracted to sys._MEIPASS, but since this package is loaded from the
    # zipped PYZ archive, the standard importer won't find them unless we add
    # the physical directory to the package's __path__.
    _pkg_dir = os.path.join(sys._MEIPASS, 'unrar')
    if os.path.exists(_pkg_dir) and _pkg_dir not in __path__:
        __path__.append(_pkg_dir)

from unrar.rarfile import RarFile, BadRarFile, RarWrongPassword, NeedFirstVolume

__all__ = ["RarFile", "BadRarFile", "RarWrongPassword", "NeedFirstVolume"]
