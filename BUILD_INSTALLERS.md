# Build EXE and DMG installers

This package includes the complete current source and two native build scripts. End users do not need Python. GraXpert and RC-Astro are separate installed/licensed applications; their installers, models and keys are not included.

The application name is Astro Laboratory. The executable/bundle name is AstroLaboratory. Build version: 0.9.0.

## Windows: EXE setup wizard

Build on Windows 10/11 using 64-bit Python 3.12 (or 3.11+) and Inno Setup 6.

1. Install Python from https://www.python.org/downloads/windows/ and Inno Setup from https://jrsoftware.org/isdl.php.
2. Extract this package into a writable folder. Do not build inside Program Files.
3. Double-click `build_windows.bat`.

The script creates its own `.build-venv`, installs runtime/build dependencies, packages the Python application with PyInstaller, and compiles an Inno Setup installer.

Outputs:

- `dist\AstroLaboratory\AstroLaboratory.exe`: portable application folder. Distribute the entire folder, not only its EXE.
- `release\AstroLaboratory-0.9.0-Windows-Setup.exe`: actual installation wizard, with Start Menu shortcut, optional desktop shortcut and uninstaller.

Installation is per-user under `%LOCALAPPDATA%\Programs\AstroLaboratory` and does not request administrator rights. Work files are stored separately in `%LOCALAPPDATA%\AstroProcessor\work`, so reinstalling/uninstalling the application does not delete photographs. User settings remain in the browser for http://127.0.0.1:8765.

If Python is not selected correctly:

```bat
set "ASTRO_BUILD_PYTHON=C:\Path\To\python.exe"
build_windows.bat
```

By default the script uses `py -3.12` when creating the build environment. For an incompatible pre-existing `.build-venv`, rename it and run again. If Inno Setup is not detected:

```bat
set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
build_windows.bat
```

The installer is unsigned unless you add your own Authenticode signing configuration. This package does not contain a signing certificate. Test the installed application on a Windows computer with no Python before sharing it.

## macOS: APP in a DMG

Build on macOS with Python 3.12 (or 3.11+) and the built-in `hdiutil` command.

```sh
bash build_macos.command
```

If the interpreter is not named `python3.12`:

```sh
ASTRO_BUILD_PYTHON='/absolute/path/to/python3.12' bash build_macos.command
```

Outputs:

- `dist/AstroLaboratory.app`
- `release/AstroLaboratory-0.9.0-macOS-arm64.dmg` on native Apple Silicon Python, or `...-x86_64.dmg` on Intel/x86 Python.

Open the DMG and drag AstroLaboratory.app to Applications. This is a standard drag-to-install DMG, not a PKG installation wizard. No Python is needed on the target computer. Work files are stored in `~/Library/Application Support/AstroProcessor/work`, outside the app bundle and disk image.

Build separately for Apple Silicon and Intel using the corresponding Python architecture. The build does not create a universal binary. Compatibility depends on the build macOS version and the collected library deployment targets; test on the oldest target macOS you intend to support. This runtime has no tkinter requirement: the UI is in the browser.

PyInstaller can create an ad-hoc-signed app for local testing. For normal public distribution, use your own Developer ID Application certificate and notarization credentials:

```sh
export CODESIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)'
export NOTARY_PROFILE='your-notarytool-keychain-profile'
bash build_macos.command
```

The build signs the app through PyInstaller, signs the DMG, submits it with `xcrun notarytool`, then staples and validates the notarization ticket. The keychain profile must already exist; this script never requests or embeds Apple credentials. No Apple account or certificate is supplied by this package. Notarization failures must be resolved before public release.

## Launch, logs and external tools

Launching the installed app starts the loopback server and opens the browser. A second launch reopens an existing recognized instance instead of starting a second server. If another application uses port 8765, launch displays an error. **Quit** in the web header stops the local server; finish image processing first. Closing a browser tab alone does not quit the server.

Logs:

- Windows: `%LOCALAPPDATA%\AstroProcessor\desktop.log`
- macOS: `~/Library/Application Support/AstroProcessor/desktop.log`

Finder-launched apps may have a different PATH from Terminal. If the RC-Astro CLI is not found, create `desktop.json` next to the above log file, following `packaging/desktop.example.json`, and enter its full executable path in `rc_astro_path`. The same file can specify `graxpert_path` and `work_directory`. Paths must be JSON strings: on Windows use `/` or escaped `\\` separators. Restart the app after editing.

GraXpert can also be configured in the web interface. RC-Astro licenses must already be activated on each target computer. The installer does not activate or bundle third-party licenses.

## What has and has not been verified

The scripts and installer definitions have been prepared and their Python/shell/JavaScript syntax checked. Native EXE/DMG builds cannot be executed in this Linux workspace. Their final signing, installation and target-platform behavior must be tested on Windows/macOS. There are no prebuilt EXE/DMG binaries in this source package.

When publishing an installer, preserve any required third-party license notices. This package is a build kit, not a declaration of a new license for all included open-source dependencies or your external proprietary plugins.

Internal data directories retain the AstroProcessor name for compatibility with earlier installations. The installer proposes AstroLaboratory even after an earlier installation; you can choose another destination manually.
