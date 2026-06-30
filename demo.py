#!/usr/bin/env python3
"""
Minimal working example demo for the Annotator.

Annotates all images in a folder. Use left/right arrows to navigate.
Press 'H' in the window for help.
"""

from annotator import annotate_folder
from pathlib import Path


root = Path(__file__).resolve().parent
annotate_folder(str(root / 'data'))
