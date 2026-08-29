"""D&D self-contained Windows updater.

Downloads an update package, verifies SHA-256, stages it, safely swaps the install
folder, and relaunches DD.exe. Before the swap, the updater copies itself to a
temporary location so Windows file locking cannot prevent replacement of the
updater that belongs to the old installation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, dst: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": "D&D-Updater/1.0"})
    with urllib.request.urlopen(req, timeout=180) as response, dst.open("wb") as out:
        shutil.copyfileobj(response, out)


def wait_for_pid_exit(pid: int | None) -> None:
    if not pid:
        return
    for _ in range(240):
        try:
            os.kill(pid, 0)
        except OSError:
            return
        time.sleep(0.25)
    raise RuntimeError("The D&D application did not close in time.")


def copy_self_and_relaunch(args: list[str]) -> None:
    """Run a copy of the updater outside the installation folder."""
    source = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve()
    temp_dir = Path(tempfile.gettempdir()) / "D&D-Updater"
    temp_dir.mkdir(parents=True, exist_ok=True)
    target = temp_dir / f"DDUpdater_{os.getpid()}.exe" if source.suffix.lower() == ".exe" else temp_dir / f"DDUpdater_{os.getpid()}.py"
    shutil.copy2(source, target)
    if source.suffix.lower() == ".exe":
        cmd = [str(target), "--bootstrap"] + args
    else:
        cmd = [sys.executable, str(target), "--bootstrap"] + args
    subprocess.Popen(cmd, cwd=str(temp_dir), close_fds=True)


def safe_extract(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path) as archive:
        for name in archive.namelist():
            p = Path(name)
            if p.is_absolute() or ".." in p.parts:
                raise RuntimeError("Unsafe update archive")
        archive.extractall(destination)


def show_error(message: str) -> None:
    # Do not require Qt just to report an updater error.
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, str(message), "D&D Update", 0x10)
    except Exception:
        pass


def install(args: argparse.Namespace) -> None:
    install_dir = Path(args.install_dir).resolve()
    parent = install_dir.parent
    parent.mkdir(parents=True, exist_ok=True)

    wait_for_pid_exit(args.parent_pid)

    stage = Path(tempfile.mkdtemp(prefix="dd_update_", dir=str(parent)))
    package = stage / "update.zip"
    extracted = stage / "new"
    backup = parent / f"{install_dir.name}_rollback"

    try:
        manifest_notes: list[str] = []
        manifest_version = None
        package_url = args.package_url
        expected_sha = args.sha256

        if args.manifest:
            req = urllib.request.Request(args.manifest, headers={"User-Agent": "D&D-Updater/1.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
            if not isinstance(data, dict):
                raise RuntimeError("Invalid update manifest")
            package_url = data.get("package_url") or data.get("update_url")
            expected_sha = data.get("sha256")
            manifest_notes = data.get("notes") or []
            manifest_version = data.get("version")

        if not package_url:
            raise RuntimeError("Update package URL is missing.")
        if not expected_sha:
            raise RuntimeError("SHA-256 is missing from the update manifest.")

        download(str(package_url), package)
        actual_sha = sha256(package).lower()
        if actual_sha != str(expected_sha).lower():
            raise RuntimeError("Update verification failed: SHA-256 does not match.")

        extracted.mkdir()
        safe_extract(package, extracted)
        if not (extracted / args.exe).exists():
            raise RuntimeError(f"Update package does not contain {args.exe}.")

        if backup.exists():
            shutil.rmtree(backup, ignore_errors=True)
        if install_dir.exists():
            os.replace(str(install_dir), str(backup))

        try:
            os.replace(str(extracted), str(install_dir))
        except Exception:
            if install_dir.exists():
                shutil.rmtree(install_dir, ignore_errors=True)
            if backup.exists():
                os.replace(str(backup), str(install_dir))
            raise

        appdata = os.environ.get("APPDATA")
        pending = (Path(appdata) if appdata else Path.home()) / "D&D" / "pending_update.json"
        pending.parent.mkdir(parents=True, exist_ok=True)
        pending.write_text(
            json.dumps({"version": manifest_version, "notes": manifest_notes}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        subprocess.Popen([str(install_dir / args.exe), "--updated"], cwd=str(install_dir), close_fds=True)

    except Exception:
        if not install_dir.exists() and backup.exists():
            os.replace(str(backup), str(install_dir))
        raise
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--manifest")
    parser.add_argument("--install-dir", required=True)
    parser.add_argument("--parent-pid", type=int)
    parser.add_argument("--package-url")
    parser.add_argument("--sha256")
    parser.add_argument("--exe", default="DD.exe")
    args = parser.parse_args()

    raw_args = sys.argv[1:]
    if not args.bootstrap:
        # A bundled updater in the installed app must execute from a temporary copy
        # before touching the directory that contains itself.
        copy_self_and_relaunch(raw_args)
        return 0

    try:
        install(args)
        return 0
    except Exception as exc:
        show_error(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
