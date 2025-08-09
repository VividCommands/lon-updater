# Lon.exe Updater

This project provides a lightweight self‑updating utility for **Lon.exe**.  
It is designed to run on Windows and offer a smooth update experience similar to the existing macro EXE setup.  
The updater confirms with the user, downloads the latest release from GitHub, verifies file integrity, backs up the current executable and replaces it atomically.  

## Features

* **User confirmation** – prompts the user with a simple Yes/No dialog before updating.  
* **Configurable source** – the release URL and expected checksum are supplied via a JSON config file (`updater.config.json`), so no code changes are required to update the download source.  
* **Integrity check** – verifies the downloaded file against a published SHA‑256 checksum.  
* **Safe replacement** – gracefully stops any running instance of **Lon.exe**, backs up the existing executable, installs the new version and rolls back on failure.  
* **Logging** – writes detailed logs to `logs/updater.log` with timestamps for troubleshooting.  
* **No unnecessary elevation** – the updater only requests administrative privileges when required (e.g. installing to a protected location).  

## Repository Layout

```
lon-updater/
├── README.md              # You are here
├── LICENSE                # MIT license
├── .gitignore             # Ignore binaries, logs, caches
├── updater.py             # Main updater implementation
├── build.sh               # Example build script using PyInstaller
├── updater_config_example.json  # Sample configuration file
└── sample_release/
    ├── Lon.exe            # Example application binary (placeholder)
    └── Lon.exe.sha256     # Corresponding checksum file
```

## Getting Started

1. **Clone or download this repository.**  
   ```sh
   git clone https://github.com/<your‑org>/lon-updater.git
   cd lon-updater
   ```

2. **Install dependencies.**  
   The updater itself only relies on the Python standard library.  
   To build a standalone `.exe`, you need [PyInstaller](https://pyinstaller.org/):
   ```sh
   python -m pip install --upgrade pip
   python -m pip install pyinstaller
   ```

3. **Configure the updater.**  
   Copy `updater_config_example.json` to `updater.config.json` and edit the values to point at your release asset and checksum files.  
   ```json
   {
     "releases_url": "https://github.com/<owner>/lon/releases/latest",
     "expected_sha256_url": "https://github.com/<owner>/lon/releases/latest/download/Lon.exe.sha256",
     "app_process_name": "Lon.exe",
     "install_path": "C:/Program Files/Lon/Lon.exe",
     "backup_path": "C:/ProgramData/Lon/Backup",
     "min_version": "1.0.0"
   }
   ```

4. **Run the updater.**  
   Place `updater.exe` (built via `build.sh`) alongside `updater.config.json` and execute it.  
   The updater will prompt the user and perform the update if a new version is available.

## Building the Updater

The provided `build.sh` script shows an example of how to package `updater.py` into a single executable using PyInstaller.  
It creates a one‑file Windows console application.

```sh
./build.sh
```

This produces `dist/updater.exe`.  
Publish the resulting `updater.exe` along with `updater.config.json` in your desired distribution location (e.g. GitHub Releases).

## Publishing a New Lon.exe Release

1. Compile or otherwise produce your new `Lon.exe`.  
2. Calculate its SHA‑256 checksum:
   ```sh
   certutil -hashfile Lon.exe SHA256
   ```
   Copy the resulting checksum into a file named `Lon.exe.sha256` (the file should contain only the hex digest and an optional trailing newline).
3. Create a new release in the **Lon** repository on GitHub.  
   Attach both `Lon.exe` and `Lon.exe.sha256` as release assets.  
   Ensure the asset names match those referenced in your `updater.config.json`.
4. Update `releases_url` and `expected_sha256_url` in `updater.config.json` if necessary.

## Troubleshooting & Rollback

* **No Internet / Download Failure:** If the updater cannot reach the release or checksum URL, it logs the error and aborts without modifying the current installation.
* **Checksum Mismatch:** If the downloaded file fails the integrity check, the updater aborts and notifies the user.
* **Permission Errors:** When installing to a protected directory (e.g. `Program Files`), Windows may require elevation.  The updater will attempt the copy and log an error if it fails; run the updater as administrator if necessary.
* **Rollback:** If replacement fails after the backup has been created, the updater will restore the backup automatically and alert the user.

## Security Considerations

The updater verifies downloads against a published checksum and only connects to HTTPS URLs.  To further improve security you may consider:

* Signing the `Lon.exe` and `updater.exe` binaries with an Authenticode certificate.
* Hosting releases on a trusted domain (e.g. GitHub) with HTTPS and integrity metadata.

## License

This project is licensed under the [MIT License](LICENSE).
