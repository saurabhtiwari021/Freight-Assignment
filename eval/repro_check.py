"""Run the pipeline 3 times in FRESH processes (different PYTHONHASHSEED each) and diff.

Run:  python eval/repro_check.py [--exclude-reason]

With --exclude-reason, compares every column except 'reason' (for --llm runs where
wording may vary but verdicts, note ids and numbers must match).
"""
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
EXCLUDE_REASON = "--exclude-reason" in sys.argv
extra_args = [a for a in sys.argv[1:] if a != "--exclude-reason"]

outs = []
for i, seed in enumerate(("0", "1234", "random"), start=1):
    path = ROOT / "reports" / f"repro_run{i}.csv"
    env = {**os.environ, "PYTHONHASHSEED": seed}
    cmd = [sys.executable, "-m", "costwatch.run", "--out", str(path)] + extra_args
    subprocess.run(cmd, cwd=ROOT, env=env, check=True, capture_output=True)
    outs.append(path)

if EXCLUDE_REASON:
    # Compare everything except the 'reason' column
    dfs = [pd.read_csv(p).drop(columns=["reason"], errors="ignore") for p in outs]
    hashes = [hashlib.sha256(d.to_csv(index=False).encode()).hexdigest() for d in dfs]
    label = "(excluding reason column)"
else:
    hashes = [hashlib.sha256(p.read_bytes()).hexdigest() for p in outs]
    label = "(byte-for-byte)"

result_path = ROOT / "reports" / "repro_check.txt"
lines = []
for p, h in zip(outs, hashes):
    line = f"{p.name}  sha256={h[:16]}..."
    print(line)
    lines.append(line)
same = len(set(hashes)) == 1
msg = f"IDENTICAL across 3 runs {label}" if same else f"MISMATCH - investigate {label}"
print(msg)
lines.append(msg)
result_path.write_text("\n".join(lines) + "\n")
sys.exit(0 if same else 1)
