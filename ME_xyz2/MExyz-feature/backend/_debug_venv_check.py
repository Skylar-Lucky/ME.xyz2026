"""Debug: diagnose why `python -m venv .venv` fails copying venvlauncher.exe."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "debug-d0b56f.log"
SESSION = "d0b56f"
ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
TARGET = VENV / "Scripts" / "python.exe"
SRC = Path(sys.base_prefix) / "Lib" / "venv" / "scripts" / "nt" / "venvlauncher.exe"


def log(hypothesis_id: str, location: str, message: str, data: dict) -> None:
    # #region agent log
    payload = {
        "sessionId": SESSION,
        "runId": "venv-diag",
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data,
        "timestamp": int(time.time() * 1000),
    }
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    # #endregion


def main() -> None:
    log(
        "A",
        "_debug_venv_check.py:env",
        "python/env paths",
        {
            "sys_executable": sys.executable,
            "base_prefix": sys.base_prefix,
            "cwd": os.getcwd(),
            "venv_exists": VENV.exists(),
            "target_exists": TARGET.exists(),
            "src_exists": SRC.exists(),
            "src": str(SRC),
            "target": str(TARGET),
        },
    )

    lockers: list[dict] = []
    try:
        # #region agent log
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*ME_xyz*backend*.venv*' "
             "-or $_.Name -match 'python|uvicorn' } | Select-Object ProcessId,Name,ExecutablePath | ConvertTo-Json -Compress"],
            text=True,
            stderr=subprocess.STDOUT,
        )
        # #endregion
        parsed = json.loads(out) if out.strip() else []
        if isinstance(parsed, dict):
            parsed = [parsed]
        for p in parsed:
            path = p.get("ExecutablePath") or ""
            if "ME_xyz" in path.replace("/", "\\") and ".venv" in path:
                lockers.append({"pid": p.get("ProcessId"), "name": p.get("Name"), "path": path})
    except Exception as e:
        log("A", "_debug_venv_check.py:proc", "process scan failed", {"error": str(e)})

    log(
        "A",
        "_debug_venv_check.py:lockers",
        "processes using backend .venv",
        {"count": len(lockers), "lockers": lockers},
    )

    # Hypothesis B: source venvlauncher missing / broken Anaconda
    log(
        "B",
        "_debug_venv_check.py:src",
        "source venvlauncher status",
        {
            "exists": SRC.exists(),
            "size": SRC.stat().st_size if SRC.exists() else None,
        },
    )

    # Hypothesis C: destination locked / cannot overwrite
    copy_ok = False
    copy_err = None
    if SRC.exists() and TARGET.exists():
        try:
            shutil.copy2(SRC, TARGET)
            copy_ok = True
        except Exception as e:
            copy_err = f"{type(e).__name__}: {e}"
    elif not TARGET.exists():
        copy_err = "target missing"
    else:
        copy_err = "source missing"

    log(
        "C",
        "_debug_venv_check.py:copy",
        "direct copy venvlauncher -> Scripts/python.exe",
        {"ok": copy_ok, "error": copy_err},
    )

    # Hypothesis D: write permission on Scripts dir
    scripts = VENV / "Scripts"
    can_write = False
    write_err = None
    probe = scripts / "_agent_write_probe.tmp"
    try:
        probe.write_text("ok", encoding="utf-8")
        can_write = True
        probe.unlink(missing_ok=True)
    except Exception as e:
        write_err = f"{type(e).__name__}: {e}"

    log(
        "D",
        "_debug_venv_check.py:write",
        "Scripts dir write probe",
        {"can_write": can_write, "error": write_err},
    )

    # Hypothesis E: venv create to fresh path works
    fresh = ROOT / ".venv_agent_probe"
    if fresh.exists():
        shutil.rmtree(fresh, ignore_errors=True)
    create_ok = False
    create_err = None
    try:
        subprocess.check_call([sys.executable, "-m", "venv", str(fresh)], stderr=subprocess.STDOUT)
        create_ok = (fresh / "Scripts" / "python.exe").exists()
    except Exception as e:
        create_err = f"{type(e).__name__}: {e}"
    finally:
        if fresh.exists():
            shutil.rmtree(fresh, ignore_errors=True)

    log(
        "E",
        "_debug_venv_check.py:fresh",
        "venv create on fresh path",
        {"ok": create_ok, "error": create_err},
    )

    print("Wrote diagnostics to", LOG)


if __name__ == "__main__":
    main()
