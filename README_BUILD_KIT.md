# Astro Laboratory 0.8.0 — EXE / DMG build kit

This complete source package includes the current English interface, GraXpert and RC-Astro adapters, sample-background noise measurement, S-curve, star brightness, saturation 0–300%, saved/reset settings, automatic Bayer import, three-column layout, Input/After blinking and the processing overlay.

Start with **BUILD_INSTALLERS.md** for native installer builds:

- Windows: install 64-bit Python 3.12 and Inno Setup 6, then run `build_windows.bat`.
- macOS: install Python 3.12, then run `bash build_macos.command`.

These scripts build an EXE setup wizard on Windows and a drag-to-install APP/DMG on macOS. They cannot cross-build the other operating system. End users do not need Python. GraXpert and licensed RC-Astro products are separate installations.

For running the source directly, create a Python 3.11+ virtual environment, install `requirements.txt`, and run `app.py`, then open http://127.0.0.1:8765. The older source launchers `start-macos.command` and `start-windows.bat` remain available.

For installed-app runtime settings, use `packaging/desktop.example.json` as described in BUILD_INSTALLERS.md. The installed app keeps photos/work files outside its installation folder and provides a Quit button in the browser header.

No prebuilt EXE/DMG binaries, private settings, API keys, license keys, working images, Python virtual environments, or caches are included.

Verified in the Linux build workspace: 53 application tests, Python/Bash/JavaScript syntax, actual local HTTP startup, static-resource serving and authenticated shutdown. Final native packaging, signing, EXE installation and DMG installation require verification on the target Windows/macOS computer.

## RC-Astro CLI path
In the RC-Astro panel, paste the executable path and click **Verify & save CLI path**. The path takes effect immediately and persists across application launches. Then click **Check licenses**. A Photoshop/Affinity plugin or license file cannot replace the CLI executable.
