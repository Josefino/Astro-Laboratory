# Astro Laboratory

Astro Laboratory is a local application for processing linear astronomical images. It combines adjustable image processing, an interactive browser preview, and optional integration with GraXpert and RC-Astro tools.

The interface runs at **http://127.0.0.1:8765**. Image processing takes place on your computer. No OpenAI API key or ChatGPT subscription is required.

## Supported images

- FITS: `.fits`, `.fit`, and `.fts`.
- Linear TIFF: `.tif` and `.tiff`, including supported Vaonis exports.
- Monochrome and RGB images.
- Automatic bilinear debayering for monochrome FITS images with a supported Bayer pattern in the header.

Use **linear, unstretched data**. A TIFF extension alone does not guarantee that an image is linear: check your telescope's export settings. JPEG and PNG are output formats, not supported processing inputs. The upload limit is 512 MiB per file.

## Installation and launch

### Installed application

If you have a built installer:

- **Windows:** run the EXE installer, then launch Astro Laboratory from the Start Menu.
- **macOS:** open the appropriate DMG for Apple Silicon or Intel, drag AstroLaboratory.app to Applications, and launch it.

The application opens your browser automatically. Python is not required for the installed application. Use **Quit** in the application header to stop it after processing finishes. Closing the browser tab alone does not stop the application.

This repository contains source and build scripts. It does not include prebuilt installers. See [BUILD_INSTALLERS.md](BUILD_INSTALLERS.md) to create an EXE or DMG on the corresponding operating system.

### Run from source

Use 64-bit **Python 3.11 or newer**; Python 3.12 is recommended.

On macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

On Windows:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open **http://127.0.0.1:8765**. Stop a source session with **Ctrl+C** in its terminal. The included `start-macos.command` and `start-windows.bat` are alternative launchers.

## Your first image

1. Load a linear FITS or TIFF image using the file selector.
2. Inspect the input preview. Its display stretch lets you see the linear data without changing the original file.
3. Start with moderate processing strength and noise reduction. Leave detail enhancement low until you have inspected the result.
4. Optionally enable gradient removal or your installed RC-Astro tools.
5. Click **Process image**. The viewer displays **Processing…**, the current stage, and elapsed time. Its animated bar indicates activity rather than a measured percentage.
6. Review **Input**, **After**, and the comparison views. Use **Blink input / after** for a direct comparison.
7. Download the desired exports.

The original input is preserved. Changing controls does not run a new processing job automatically: click **Process image** to apply the new settings.

## Preview and navigation

Use the zoom slider to magnify the image up to **10×**. Drag the image to pan when zoomed in. The comparison toolbar lets you inspect the input, processed image, differences, and changed regions. When generated, the background model can also be inspected.

## Processing controls

| Control | Purpose |
| --- | --- |
| Overall processing strength | Scales applicable processing adjustments, from 0–200%. At 0%, linear processing is bypassed; the preview still uses a display stretch. |
| Noise reduction | Adjusts built-in denoising, or the NoiseXTerminator blend when enabled. |
| Detail enhancement | Increases local detail; use cautiously to avoid emphasizing noise or creating harsh structure. |
| Display stretch | Makes faint linear signal visible, with a range of 1–200%. |
| Color saturation | Adjusts color intensity from 0–300%; 100% is the reference setting. |
| Green noise reduction | Reduces excess green in the displayed, stretched result. It is separate from gradient removal. |
| S-curve strength | Darkens tones below the pivot and brightens tones above it, increasing contrast. |
| S-curve pivot | Sets the tonal boundary for the S-curve. |

Display stretch, saturation, green reduction, and the S-curve affect the photographic rendering. The linear FITS export remains suitable for further linear processing.

**Save settings** stores processing controls in the current browser. **Reset values** restores defaults. Saved controls are specific to the browser and local address; background sample positions are not saved with them. The RC-Astro executable path is saved separately by the application.

## Gradient removal and GraXpert

Gradient removal is optional. Select the built-in plane method or **GraXpert** in the right-hand panel.

To use GraXpert, install it separately and enter its path in **Path to installed GraXpert**. On macOS, this can be the GraXpert application bundle. GraXpert models and executable are not bundled with Astro Laboratory.

GraXpert offers two modes in this application:

- **AI:** automatic background estimation.
- **RBF:** sample-based estimation using the green background squares.

For a large nebula, try the RBF mode with samples placed on genuine background near the image edges. Generate edge samples, inspect every square, remove unsuitable samples, and add or move samples as needed. Avoid nebulae, galaxies, bright stars, halos, and image artifacts. Edge placement alone does not guarantee clean background.

**GraXpert smoothing** ranges from **0.00 to 1.00**. It adjusts the background model rather than directly controlling correction strength. The application uses subtraction correction, scaled by overall processing strength. If GPU processing fails, disable **GraXpert GPU acceleration**.

Check the result carefully: when an extended object fills the frame, a background model may remove real object signal. Green noise reduction is a separate control for residual excess green after stretching. Photometric color calibration is not performed.

## Background noise measurement

The green GraXpert squares are also used to estimate noise from the **original linear input**. Measurement removes a local plane within each usable sample, rejects outliers, and combines robust sample estimates.

Place squares on clean background for a meaningful result. The panel provides sample diagnostics and, for RGB data, channel noise estimates. This is a background noise estimate, **not SNR**. Its numerical value depends on the image's signal units and scaling; compare values only when those are compatible.

## RC-Astro setup

Astro Laboratory requires the **standalone RC-Astro CLI executable**. Photoshop/Affinity plugins and license files cannot replace it. Install the CLI and activate the products you own on the computer where you process images.

1. Find the RC-Astro section in the right-hand panel.
2. Paste the full executable path into **Path to RC-Astro CLI executable**.
3. Click **Verify & save CLI path**.
4. Click **Check licenses** to inspect the product responses.

Select the executable file itself, not its containing folder. Paths containing spaces are supported. Leaving the field blank asks the application to locate `rc-astro` on the system PATH.

The saved path takes effect immediately and is restored on future launches. Path verification confirms that an executable file can be located; the separate license check confirms the CLI's product responses. Do not change the path during processing.

### BlurXTerminator

Enable **BlurXTerminator** for its star and PSF processing. Adjust stars with **Stellar sharpening** and **Star halos**. These native star controls are independent of overall processing strength; there is no separate BlurXTerminator intensity slider. Start gently and inspect enlarged stars before increasing sharpening.

### NoiseXTerminator

Enable **NoiseXTerminator** for denoising. Its blend uses overall processing strength and the noise reduction amount. With StarXTerminator enabled, denoising is applied to the starless image.

### StarXTerminator

Enable **StarXTerminator** to separate the image into starless and star layers. **Star brightness after StarXTerminator** controls how much of the original star layer is added back before stretching:

- **100%:** full original star-layer signal.
- **10%:** one tenth of that signal.

The recombined image is displayed as the result. Separate linear star and starless FITS files are also available for download.

## Exports

| File | Contents |
| --- | --- |
| `processed_linear.fits` | Processed linear data in floating-point FITS format. |
| `processed_stretched.fits` | The nonlinear photographic rendering in FITS format. |
| `processed_16bit.tif` | Stretched 16-bit TIFF for image editors. |
| `processed.png` | Stretched PNG for viewing or sharing. |
| `difference_linear.fits` | Signed linear difference between processed and input data. |
| `report.json` | Processing settings, steps, diagnostics, and the original input checksum. |
| `stars_linear.fits`, `starless_linear.fits` | Separate layers when StarXTerminator is used. |
| GraXpert model/correction FITS files | Additional background diagnostics when generated. |

Keep the linear FITS when you intend to continue processing elsewhere. Use the TIFF or PNG for the photographic appearance shown by the application.

## Files and settings

Source sessions store working images in the project's `work` directory by default. Installed applications use:

- **Windows:** `%LOCALAPPDATA%\AstroProcessor\work`
- **macOS:** `~/Library/Application Support/AstroProcessor/work`

The older internal name `AstroProcessor` is retained for compatibility. Installed-app logs are stored as `desktop.log` in the parent directory. Working files remain outside the application installation folder and are not automatically deleted when you uninstall it.

Advanced installed-app settings, such as a custom work directory, are described in [BUILD_INSTALLERS.md](BUILD_INSTALLERS.md). You do not need to edit configuration files to enter the RC-Astro CLI path.

## Troubleshooting

**CLI not found:** enter the actual RC-Astro CLI executable path and use **Verify & save CLI path**. A plugin or license file is not the CLI.

**CLI found, but processing fails:** use **Check licenses**, confirm that the relevant product is activated and its models are available, then inspect the processing logs.

**GraXpert does not run:** enable gradient removal, select GraXpert, check its path, and try disabling GPU acceleration.

**A nebula becomes too dark after gradient removal:** inspect the background samples/model, remove samples on real object signal, try RBF mode, or disable gradient removal to compare.

**Processing appears slow:** watch the stage and elapsed time in the viewer. External tools may take several minutes. Wait for completion before starting another job or quitting.

**NumPy cannot be installed:** confirm that the virtual environment uses a supported 64-bit Python version. Updating pip alone does not make an old Python version compatible.

**Port 8765 is already in use:** quit an existing Astro Laboratory session or stop the conflicting local service before launching again.

**Flask development-server warning:** the source launcher uses Flask's development server on the local loopback address. The warning alone is not a processing failure. The packaged desktop launcher uses its own local server lifecycle.

## Building installers

Run `build_windows.bat` on Windows or `build_macos.command` on macOS. See [BUILD_INSTALLERS.md](BUILD_INSTALLERS.md) for prerequisites, output paths, signing, and notarization.

Native installer builds and installation must be tested on their target operating systems. GraXpert, RC-Astro tools, models, and proprietary licenses are separate installations and are not distributed by this repository.

## License

See [LICENSE](LICENSE) for the repository license. Third-party dependencies and external tools retain their own licenses.
