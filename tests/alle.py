"""Alle Regeltests (wie vor jedem Deployment): python tests/alle.py"""
import importlib
import os
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)

MODULE = sorted(f[:-3] for f in os.listdir(HIER) if f.startswith("test_") and f.endswith(".py"))


def main():
    t0 = time.monotonic()
    tests = []
    for m in MODULE:
        mod = importlib.import_module(m)
        tests += [(f"{m}.{n}", getattr(mod, n)) for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n))]
    for name, t in sorted(tests):
        t()
        print("ok ", name)
    print(f"{len(tests)} Tests bestanden in {time.monotonic() - t0:.1f} s.")


if __name__ == "__main__":
    main()
