"""Configure pytest for travel/photos tests."""

import os
import pathlib
import sys

# Add travel/photos directory to sys.path so tests can import from app
sys.path.insert(0, str(pathlib.Path(__file__).parent))

# Change working directory to travel/photos for correct relative paths
os.chdir(pathlib.Path(__file__).parent)
