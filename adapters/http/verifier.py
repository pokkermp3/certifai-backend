"""
adapters/http/verifier.py

Loads the verifier HTML from a separate file at import time.
Keeping HTML out of Python strings makes both easier to maintain.
"""
import os

_dir = os.path.dirname(__file__)
_path = os.path.join(_dir, "verifier.html")

with open(_path, "r", encoding="utf-8") as _f:
    VERIFIER_HTML = _f.read()