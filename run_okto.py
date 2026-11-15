"""Runs Okto from a source checkout without installing it (used by okto.cmd)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from okto.cli import entry

entry()
