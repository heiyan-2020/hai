"""Make the plugin's scripts/ importable from the test modules."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
