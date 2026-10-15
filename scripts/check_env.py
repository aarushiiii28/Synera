"""`make check`: print tool versions and assert the minimum versions SYNERA needs."""
from __future__ import annotations

import re
import subprocess
import sys


def version(cmd: list[str]) -> str | None:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT, shell=sys.platform == "win32").strip()
    except Exception:  # noqa: BLE001
        return None


def main() -> int:
    ok = True
    py = sys.version.split()[0]
    print(f"python {py}")
    if sys.version_info < (3, 11):
        print("  FAIL: Python 3.11+ required")
        ok = False
    node = version(["node", "--version"])
    print(f"node   {node}")
    if not node or int(re.sub(r"\D.*", "", node.lstrip("v"))) < 20:
        print("  FAIL: Node 20+ required")
        ok = False
    git = version(["git", "--version"])
    print(f"git    {git}")
    ok &= bool(git)
    for mod in ("numpy", "pandas", "scipy", "statsmodels", "sklearn", "lightgbm", "shap", "torch", "fastapi", "sqlmodel", "cryptography"):
        try:
            m = __import__(mod)
            print(f"  {mod:13s} {getattr(m, '__version__', 'ok')}")
        except ImportError:
            print(f"  {mod:13s} MISSING")
            ok = False
    import synera_core

    print(f"synera_core -> {synera_core.__file__}")
    print("ENVIRONMENT OK" if ok else "ENVIRONMENT INCOMPLETE")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
