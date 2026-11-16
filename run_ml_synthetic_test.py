"""Run offline labeled synthetic anomaly validation; no router changes."""
from pathlib import Path
import subprocess
import sys
root=Path(__file__).resolve().parent
raise SystemExit(subprocess.call([sys.executable,str(root/'ml_intelligence_3DC.py'),'--self-test'],cwd=root))
