import sys
from pathlib import Path

# Make `data_access` importable the same way app.py imports it.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
