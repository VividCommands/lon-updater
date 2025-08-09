#!/usr/bin/env python3
"""Self‑updater for Lon.exe

This script downloads the latest release of Lon.exe from a configurable URL,
verifies its SHA‑256 checksum, gracefully terminates any running instance of
Lon.exe, backs up the existing executable and replaces it atomically.  
On any error the updater restores the previous version and logs a descriptive
message.  Logs are written to `logs/updater.log`.

The updater is designed to be built into a standalone executable using
PyInstaller.  When run as a console application on Windows it will display
a message box asking for confirmation to proceed.
"""

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from urllib import request, error as urlerror
from typing import Optional


def setup_logging(log_dir: str) -> None:
    """Initialise the log directory and return a file handle for logging.

    Logging is performed by appending lines to a text file.  Each line
    contains a timestamp and a message.
    """
    os.makedirs(log_dir, exist_ok=True)
    global _log_file
    _log_file = open(os.path.join(log_dir, 'updater.log'), 'a', encoding='utf-8')


def log(msg: str) -> None:
    """Write a timestamped message to the log file and standard output."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"{timestamp} - {msg}\n"
    try:
        _log_file.write(line)
        _log_file.flush()
    except Exception:
        # if logging fails, still print to console
        pass
    sys.stdout.write(line)
    sys.stdout.flush()


def load_config(path: str) -> dict:
    """Load updater configuration from a JSON file."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def confirm_update() -> bool:
    """Display a confirmation dialog and return True if user selects Yes.

    Uses a native Windows message box when available.  Falls back to a
    console prompt on other platforms or when the message box call fails.
    """
    message = "Update available. Proceed?"
    title = "Lon Updater"
    # Try native Windows message box
    if os.name == 'nt':
        try:
            MB_YESNO = 0x04
            result = ctypes.windll.user32.MessageBoxW(0, message, title, MB_YESNO)
            return result == 6  # IDYES
        except Exception:
            pass
    # Fallback console prompt
    while True:
        sys.stdout.write(f"{message} [y/N]: ")
        choice = input().strip().lower()
        if choice in ('y', 'yes'):
            return True
        if choice in ('n', 'no', ''):
            return False


def download_to_temp(url: str, description: str) -> Optional[str]:
    """Download the file at `url` into a temporary file and return its path.

    On any download error this function logs the error and returns None.
    """
    try:
        log(f"Downloading {description} from {url}")
        with request.urlopen(url, timeout=30) as resp:
            if resp.status >= 400:
                log(f"Failed to download {description}: HTTP {resp.status}")
                return None
            # Create a named temporary file in binary mode
            fd, tmp_path = tempfile.mkstemp(suffix=os.path.splitext(url)[-1])
            with os.fdopen(fd, 'wb') as tmp_file:
                shutil.copyfileobj(resp, tmp_file)
        return tmp_path
    except urlerror.URLError as ex:
        log(f"Network error downloading {description}: {ex}")
    except Exception as ex:
        log(f"Unexpected error downloading {description}: {ex}")
    return None


def read_remote_checksum(url: str) -> Optional[str]:
    """Download a checksum file and return the hex digest found within.

    Accepts either a raw checksum (first token on first line) or the
    standard `sha256sum` format (`<digest> <filename>`).  Returns None on
    failure.
    """
    tmp_path = download_to_temp(url, "checksum")
    if not tmp_path:
        return None
    try:
        with open(tmp_path, 'r', encoding='utf-8') as f:
            content = f.read().strip().split()
            if not content:
                log("Checksum file is empty")
                return None
            checksum = content[0].strip()
            return checksum
    except Exception as ex:
        log(f"Failed to read checksum file: {ex}")
    finally:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
    return None


def sha256_of_file(path: str) -> str:
    """Compute the SHA‑256 digest of the specified file and return it as hex."""
    hasher = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def is_process_running(name: str) -> bool:
    """Check if a process with the given image name is running (Windows only)."""
    if os.name != 'nt':
        return False
    try:
        output = subprocess.check_output(['tasklist'], text=True, stderr=subprocess.DEVNULL)
        # Each line of tasklist output begins with the process name
        for line in output.splitlines():
            if line.lower().startswith(name.lower()):
                return True
    except Exception:
        pass
    return False


def terminate_process(name: str) -> bool:
    """Attempt to gracefully terminate a running process by image name.

    Returns True if the process is not running or if termination succeeded.
    """
    if os.name != 'nt':
        return True  # non‑Windows platforms do not run Lon.exe
    if not is_process_running(name):
        return True
    log(f"{name} is currently running. Attempting to terminate.")
    try:
        # /T kills the process tree, /F forcefully terminates
        subprocess.run(['taskkill', '/IM', name, '/T', '/F'], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        # Give Windows a moment to close the process
        for _ in range(10):
            if not is_process_running(name):
                break
            time.sleep(0.5)
        if is_process_running(name):
            log(f"Unable to terminate {name}; it may require manual closure.")
            return False
        return True
    except Exception as ex:
        log(f"Error terminating {name}: {ex}")
        return False


def backup_file(src_path: str, backup_dir: str) -> Optional[str]:
    """Create a timestamped backup of `src_path` in `backup_dir`.

    Returns the path to the backup file, or None on error.
    """
    try:
        os.makedirs(backup_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = os.path.splitext(os.path.basename(src_path))[0]
        backup_name = f"{base_name}_{timestamp}.exe"
        backup_path = os.path.join(backup_dir, backup_name)
        shutil.copy2(src_path, backup_path)
        log(f"Backed up current executable to {backup_path}")
        return backup_path
    except Exception as ex:
        log(f"Failed to create backup of {src_path}: {ex}")
        return None


def atomic_replace(src: str, dest: str) -> bool:
    """Atomically replace `dest` with the contents of `src`.

    This function attempts to replace the file at `dest` with `src` in a safe
    manner.  It first copies `src` to a temporary file in the destination
    directory and then moves it over `dest`.  If the replacement fails,
    neither file should be corrupted.
    """
    dest_dir = os.path.dirname(dest)
    try:
        os.makedirs(dest_dir, exist_ok=True)
        tmp_dest = dest + '.new'
        shutil.copy2(src, tmp_dest)
        # On Windows os.replace performs an atomic replacement
        os.replace(tmp_dest, dest)
        return True
    except Exception as ex:
        log(f"Failed to replace {dest}: {ex}")
        # Clean up temporary file if it exists
        try:
            if os.path.exists(tmp_dest):
                os.remove(tmp_dest)
        except Exception:
            pass
        return False


def main():
    config_path = os.path.join(os.path.dirname(sys.argv[0]), 'updater.config.json')
    if not os.path.exists(config_path):
        sys.stderr.write(f"Configuration file not found: {config_path}\n")
        sys.exit(1)

    config = load_config(config_path)
    # Setup logging
    log_dir = os.path.join(os.path.dirname(sys.argv[0]), 'logs')
    setup_logging(log_dir)
    log("========== Starting Lon Updater ==========")
    log(f"Using config: {config_path}")

    releases_url = config.get('releases_url')
    checksum_url = config.get('expected_sha256_url')
    process_name = config.get('app_process_name', 'Lon.exe')
    install_path = config.get('install_path')
    backup_path = config.get('backup_path')
    min_version = config.get('min_version')

    if not releases_url or not checksum_url or not install_path or not backup_path:
        log("Configuration is missing required fields (releases_url, expected_sha256_url, install_path, backup_path)")
        sys.exit(1)

    if not os.path.isfile(install_path):
        log(f"Current installation not found at {install_path}")
        # It might be the first installation; proceed

    # Download latest checksum and parse digest
    expected_digest = read_remote_checksum(checksum_url)
    if not expected_digest:
        log("Unable to retrieve expected checksum. Aborting.")
        sys.exit(1)
    log(f"Expected SHA‑256: {expected_digest}")

    # Download release file to temporary location
    download_path = download_to_temp(releases_url, "Lon.exe")
    if not download_path:
        log("Failed to download new release. Aborting.")
        sys.exit(1)
    # Compute downloaded file's hash
    new_digest = sha256_of_file(download_path)
    log(f"Downloaded file SHA‑256: {new_digest}")
    if new_digest.lower() != expected_digest.lower():
        log("Checksum mismatch! Aborting update.")
        try:
            os.remove(download_path)
        except Exception:
            pass
        sys.exit(1)
    log("Checksum verified.")

    # Check if the existing file already matches the new one
    if os.path.isfile(install_path):
        try:
            current_digest = sha256_of_file(install_path)
            if current_digest.lower() == new_digest.lower():
                log("Installed Lon.exe is already up to date. No update necessary.")
                os.remove(download_path)
                sys.exit(0)
        except Exception as ex:
            log(f"Could not compute current executable checksum: {ex}")

    # Ask the user for confirmation
    if not confirm_update():
        log("User declined update.")
        os.remove(download_path)
        sys.exit(0)

    # Terminate the running process if needed
    if not terminate_process(process_name):
        log("Update aborted because the application could not be closed.")
        os.remove(download_path)
        sys.exit(1)

    # Backup current executable if it exists
    backup_created = None
    if os.path.isfile(install_path):
        backup_created = backup_file(install_path, backup_path)
        if not backup_created:
            log("Failed to create backup; aborting update.")
            os.remove(download_path)
            sys.exit(1)

    # Replace the executable
    if not atomic_replace(download_path, install_path):
        log("Failed to install update. Attempting rollback.")
        if backup_created:
            try:
                shutil.copy2(backup_created, install_path)
                log("Rollback succeeded.")
            except Exception as ex:
                log(f"Rollback failed: {ex}")
        os.remove(download_path)
        sys.exit(1)

    # Clean up downloaded file
    try:
        os.remove(download_path)
    except Exception:
        pass

    log("Update completed successfully.")
    log("==========================================")


if __name__ == '__main__':
    main()