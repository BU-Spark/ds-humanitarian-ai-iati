"""Knowledge base for retrieval over the hunger-graph activities.

Run from fa26/:  python -m kb.build | python -m kb.search "..." | python -m kb.evaluate
"""
import sys
from pathlib import Path

# kb modules share config.py with the pipeline in src/
_SRC = str(Path(__file__).resolve().parents[1] / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
