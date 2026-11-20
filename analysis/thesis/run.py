"""
Reproduce the figures and tables of the thesis from data/.

  prepare.py   prepared dataset
  regimes.py   Markov-switching model (a few minutes)
  simulate.py  price paths under the solar scenarios (Figure 6)
  figures.py   all figures and tables -> output/thesis/

Usage
  python analysis/thesis/run.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import figures   # noqa: E402
import prepare   # noqa: E402
import regimes   # noqa: E402
import simulate  # noqa: E402

for name, step in [("prepare", prepare.prepare), ("regimes", regimes.main),
                   ("simulate", simulate.main), ("figures", figures.main)]:
    t0 = time.time()
    print(f"── {name}")
    step()
    print(f"   {time.time() - t0:.0f} s")
