"""
SPDX-FileCopyrightText: 2025 DESY and the Constellation authors
SPDX-License-Identifier: EUPL-1.2
"""

from constellation.core.satellite import Satellite

from . import __version__


class altai(Satellite, version=__version__):
    pass
