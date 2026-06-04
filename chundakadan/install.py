# Copyright (c) 2026, Chundakadan
# Install / migrate hooks. Lives at chundakadan.install.* — wired
# from chundakadan/hooks.py as `before_install` + `before_migrate`.

import subprocess
import sys


# Pinned to match chundakadan/pyproject.toml so a manual install AND
# the auto-installer pull the exact same version.
_FIREBASE_ADMIN_PIN = "firebase-admin>=6.5.0,<8.0.0"


def ensure_firebase_admin_installed(*args, **kwargs):
    """Idempotent: `pip install firebase-admin` if it isn't already
    importable in this Python env. Skips silently when already
    installed; logs without failing if install fails (so a migrate
    doesn't break in restricted/Frappe-Cloud-like environments where
    pip might be read-only — deps come from pyproject.toml there
    anyway).

    Wired as both `before_install` (first-time `bench install-app
    chundakadan`) and `before_migrate` (every `bench migrate`). Means:
      - Fresh clone + bench migrate → firebase-admin appears
      - Upgrade existing bench → if dep was somehow stripped, restored
      - Frappe Cloud deploy → pyproject.toml handles it via build
        step; this hook is a safety net.
    """
    try:
        import firebase_admin  # noqa: F401
        return
    except ImportError:
        pass

    print(f"chundakadan.install: installing {_FIREBASE_ADMIN_PIN}…")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", _FIREBASE_ADMIN_PIN],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        print("chundakadan.install: firebase-admin installed ✓")
    except Exception as e:
        # Non-fatal — push notifications will just no-op (with a log
        # entry in chundakadan.push.import) until firebase-admin is
        # available. The rest of the migrate proceeds normally.
        print(
            f"chundakadan.install: could not auto-install firebase-admin: {e}\n"
            "  Push notifications will be disabled. To enable, run:\n"
            "    bench pip install firebase-admin"
        )
