# Astro Laboratory 0.9.0

Astro Laboratory processes astronomical FITS and TIFF images locally, using an English browser interface and optional GraXpert and RC-Astro integrations. It supports linear stacks and explicitly selected already-stretched images, separate starless/stars adjustments, and Screen recombination with Unscreen Stars.

The interface is available at **http://127.0.0.1:8765**. Image processing runs on your computer. External tools and their models may require their own installation, activation, and downloads.

## Contents

- [Install and launch](#install-and-launch)
- [Choose the correct input mode](#choose-the-correct-input-mode)
- [First processing session](#first-processing-session)
- [Processing controls](#processing-controls)
- [GraXpert and background samples](#graxpert-and-background-samples)
- [RC-Astro setup](#rc-astro-setup)
- [Star separation and Unscreen](#star-separation-and-unscreen)
- [Preview and exports](#preview-and-exports)
- [Saved settings and working files](#saved-settings-and-working-files)
- [Updates and troubleshooting](#updates-and-troubleshooting)
- [Build installers](#build-installers)

## Install and launch

### Installed application

**Windows:** run the EXE installer, then launch Astro Laboratory from the Start Menu. The default application directory is `%LOCALAPPDATA%\Programs\AstroLaboratory`.

**macOS:** open the DMG matching your computer's architecture, drag `AstroLaboratory.app` to Applications, and launch it.

The packaged application opens your browser automatically and does not require Python. Click **Quit** in the header to stop the server after processing finishes. Closing the browser tab alone does not stop it.

This source package includes build scripts, not prebuilt EXE/DMG installers.

### Run from source

Use 64-bit Python 3.11 or newer; Python 3.12 is recommended. Extract the source into a writable directory and open a terminal there.

macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

Windows CMD:

```bat
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe app.py
```

Open http://127.0.0.1:8765. Stop a source session with **Ctrl+C** in its terminal. Alternative source launchers are `start-macos.command` and `start-windows.bat`.

## Choose the correct input mode

Supported extensions are `.fit`, `.fits`, `.fts`, `.tif`, and `.tiff`. Inputs may be monochrome or RGB. Supported TIFF inputs use 16/32/64-bit sample data. The upload limit is **512 MiB**. Monochrome Bayer FITS images with supported Bayer metadata are debayered automatically using bilinear interpolation.

JPEG and PNG are photographic exports, not processing inputs. A FITS extension does not establish that the pixels are linear.

### Linear input

Leave **Already stretched input** unchecked for a linear stack. The display stretch reveals faint signal; it does not modify the original file. BlurXTerminator and gradient removal are available. Leave **Unscreen Stars** unchecked.

### Already-stretched input

Check **Already stretched input** when the pixel values have already received a permanent stretch. A temporary screen stretch in another editor does not, by itself, make the saved pixels nonlinear.

Select **Input white level** according to the actual signal scale:

| Selection | Use when |
| --- | --- |
| 65535 | Pixel values use a 0–65535 signal range. |
| 1 | Floating-point pixel values are normalized to 0–1. |
| 255 | Pixel values use a 0–255 signal range, even if stored in a supported FITS/TIFF container. |

The selected white level is not necessarily the storage bit depth. A 32-bit float FITS may contain either normalized values or values scaled to 65535. The application divides by this level without subtracting a black point or applying percentile normalization. If values exceed the selected range, processing stops with an error.

In this mode:

- BlurXTerminator and gradient removal are skipped.
- **Display stretch** and **Stars stretch** are bypassed.
- Denoising, detail adjustment, saturation, S-curves, and star brightness remain available.
- Unscreen Stars can be enabled with StarXTerminator.
- Data exports are marked nonlinear and do not use the `processed_linear.fits` name.

The initial upload preview still uses the standard automatic display stretch. Judge preserved brightness from the completed processing result in stretched mode.

## First processing session

1. Load a completed FITS/TIFF stack.
2. Choose linear or already-stretched mode and, if necessary, the correct white level.
3. For predictable individual controls, set **Overall processing strength** to 100%.
4. Start with modest noise/detail adjustment, saturation 100%, and S-curve strength 0%.
5. Configure optional external tools. Enable only the tools needed for this image.
6. If using StarXTerminator, start with **Star brightness 100%**. Enable Unscreen only for an already-stretched input.
7. Click **Process image**. The overlay displays the current stage and elapsed time; its animated bar indicates activity, not a measured completion percentage.
8. Inspect the result at normal size and enlarged. Adjust controls and process again.
9. Download the selected exports.

Control changes do not automatically reprocess the image. The original uploaded file is preserved. Background-noise measurements can update separately when sample settings change.

## Processing controls

### Overall processing strength

This is a multiplier for applicable processing amounts, from **0–200%**. It is not an image-brightness control.

| Value | Effect |
| --- | --- |
| 0% | Skips processing and RC-Astro operations; display rendering can still change the appearance. |
| 30% | Uses 0.3 times applicable processing amounts. |
| 100% | Uses the individual control amounts as set. |
| 200% | Uses twice those amounts; some blends can extrapolate beyond the fully processed result. |

For example, NoiseXTerminator with Noise reduction 20% and Overall strength 30% blends **6%** of its correction into the image. GraXpert correction and built-in noise/detail adjustments are also scaled.

BlurXTerminator uses its native sharpening/halo parameters without multiplying them by Overall strength; it is skipped at 0%. StarXTerminator is also skipped at 0%. Stretch, saturation, S-curves, green reduction, and Star brightness are independent of this multiplier.

### Display stretch and Stars stretch

**Display stretch** uses an arcsinh mapping to make faint linear signal visible. Its 1–200% range is a control scale, not a percentage of brightness or exposure. Increasing it also reveals more noise.

With StarXTerminator enabled, Display stretch affects the **starless object**, while **Stars stretch** controls the star layer independently. Without SXT, Display stretch affects the full image. Both are bypassed for Already stretched input.

### Noise reduction and detail enhancement

**Noise reduction** controls the denoising amount. If NoiseXTerminator is enabled, it blends that tool's result; otherwise it uses a gentle built-in weighted Gaussian correction. Overall strength multiplies this amount.

**Detail enhancement** applies limited built-in sharpening when BlurXTerminator is not selected. With BlurXTerminator selected, it supplies that tool's nonstellar sharpening amount. Inspect fine structure and noise before increasing it.

### Saturation and green reduction

**Color saturation** ranges from 0–300%; 100% is the reference value. With SXT enabled it adjusts the object, and **Stars saturation** separately adjusts the star layer. Values above 100% can emphasize color noise or clip channels.

**Green noise reduction** suppresses excess green after object rendering. It is separate from GraXpert gradient removal and is not photometric color calibration.

### S-curves

**S-curve strength** controls contrast. Values below **S-curve pivot** become darker and values above it become brighter. A high pivot, such as 90%, puts most image tones in the darkening part of the curve. Start with a moderate pivot and low strength.

With SXT enabled, the main S-curve affects the object; Stars S-curve strength and pivot affect stars independently. The application does not apply a shared curve after merging.

Display rendering affects PNG, TIFF, and the rendered FITS export. It does not apply the nonlinear curves to a linear-data FITS export.

## GraXpert and background samples

Gradient removal is optional and available in linear mode. Select **Basic plane model** or **GraXpert** in the right-hand panel.

Install GraXpert separately and enter its path in **Path to installed GraXpert**. On macOS, the application bundle or a supported executable path can be used. Its executable and AI models are not included here.

- **AI:** automatic background estimation.
- **RBF:** background estimation using the green sample squares.

For RBF, generate perimeter samples and inspect them. With sample editing enabled, click to add a square or click near an existing square to remove it. Disable sample editing to pan. Sample size is measured in original image pixels; edge inset controls suggested sample placement.

Place samples on genuine background, avoiding nebulosity, galaxies, bright stars, halos, and artifacts. At least six non-collinear samples are required for RBF. Perimeter suggestions are geometric positions, not automatic background detection.

**GraXpert smoothing** ranges from 0.00–1.00 and affects the model. Correction uses subtraction and is scaled by Overall strength. Disable GPU acceleration if GraXpert fails on your computer.

Large nebulae may fill the frame, making clean background unavailable. Inspect the background model and compare with gradient removal disabled; an incorrect model can remove real signal.

### Background noise estimate

The green squares also measure noise from the original input before processing. The method removes a local plane, rejects outliers, and combines robust sample noise estimates. RGB channel estimates and sample diagnostics are available.

This is **noise, not SNR**. Values depend on input units and scaling. Do not compare differently scaled files as if the number were a universal image-quality score. Samples containing real structure can bias the estimate. For already-stretched input, noise is not a linear-data noise measurement; processing reports use the normalized working scale.

## RC-Astro setup

Install the standalone RC-Astro CLI and activate your licensed products separately. Photoshop/Affinity plugins and license files cannot substitute for the CLI executable.

1. In the RC-Astro panel, paste the full file path into **Path to RC-Astro CLI executable**.
2. Click **Verify & save CLI path**. Leaving the field blank searches for `rc-astro` on PATH.
3. Click **Check licenses** to inspect the responses for BlurXTerminator, NoiseXTerminator, and StarXTerminator.

Paths containing spaces are supported. The path takes effect immediately and is saved for future launches. Verification locates an executable; the separate license check tests product responses. Finish processing before changing the path.

**BlurXTerminator** runs on linear data before star separation. **Stellar sharpening** and **Star halos** are its independent native star controls. There is no separate BXT intensity slider.

**NoiseXTerminator** runs on the starless layer when SXT is enabled; otherwise it runs on the full image. Its correction is blended according to Noise reduction and Overall strength.

## Star separation and Unscreen

### Linear workflow

1. Optional gradient correction.
2. BlurXTerminator, when enabled.
3. StarXTerminator separates stars from starless data.
4. NoiseXTerminator and applicable built-in adjustments process starless data.
5. The object and stars receive independent stretch, saturation, and S-curves.
6. Star brightness scales the rendered star layer immediately before final addition.

With Unscreen off, stars are extracted by `original - starless`. The linear export uses a data-layer recombination; it does not reproduce the separately stretched photographic result.

### Already-stretched workflow with Unscreen

In **Star settings**, enable **Unscreen Stars** after choosing Already stretched input and enabling StarXTerminator.

The application calculates the star layer immediately from the corresponding normalized SXT input and its unmodified starless output:

```text
stars = (original - starless) / (1 - starless)
```

It handles saturated denominators safely and bounds the result to 0–1. Unscreen is performed before NoiseXTerminator and curves. The application performs this layer arithmetic itself; it does not pass an unverified Unscreen flag to the CLI.

After independent adjustments, **Star brightness** scales the stars immediately before Screen blending:

```text
weighted_stars = adjusted_stars * Star_brightness / 100
result = 1 - (1 - adjusted_starless) * (1 - weighted_stars)
```

**100%** uses the full adjusted star layer; **33%** uses one third, and **10%** uses one tenth. Unscreen is rejected in linear mode. It changes star-layer extraction and recombination, not the star-removal neural network itself.

Start a comparison with saturation 100%, both S-curve strengths 0%, and Star brightness 100%. Then adjust object and stars separately. No extra stretch is applied in this mode.

## Preview and exports

Zoom up to **10×** and drag to pan. Turn off background-sample editing before panning. **Blink input / after** alternates the uploaded input preview and processed result. Difference/changed-region views show modifications, not proof that reconstructed details are physically accurate.

| Export | Meaning |
| --- | --- |
| `processed_linear.fits` | Linear-mode data result, before nonlinear photographic curves. |
| `processed_nonlinear.fits` | Data-layer result for already-stretched input; marked nonlinear. |
| `processed_stretched.fits` | Final rendered result, including independent layer adjustments and merging. |
| `processed_16bit.tif` | Final photographic rendering as 16-bit TIFF. |
| `processed.png` | Final photographic rendering as PNG. |
| `stars_linear.fits`, `starless_linear.fits` | Layers immediately after separation in linear mode. |
| `stars_unscreen.fits` | Nonlinear inverse-Screen star layer before later rendering adjustments. |
| `stars_nonlinear.fits`, `starless_nonlinear.fits` | Nonlinear separated layers where applicable. |
| `stars_stretched.png`, `starless_stretched.png` | Individually rendered layers; stars include Star brightness scaling. |
| `difference_linear.fits` / `difference_nonlinear.fits` | Signed data difference in the selected working domain. |
| `report.json` | Version, settings, processing steps, diagnostics, and original-file checksum. |
| GraXpert model/correction FITS files | Optional background diagnostics. |

Available exports depend on the selected tools. The separately rendered final image is represented by `processed_stretched.fits`, TIFF, and PNG; it can differ from the data-layer FITS result. Keep the original input for further processing.

## Saved settings and working files

**Save settings** stores processing values in the current browser. **Reset values** restores defaults, including linear input mode and Unscreen off. Background sample positions are not stored with these controls. RC-Astro CLI path is saved separately by the application.

Source sessions use the project's `work` directory by default. Installed applications use:

- Windows: `%LOCALAPPDATA%\AstroProcessor\work`
- macOS: `~/Library/Application Support/AstroProcessor/work`

The internal data name AstroProcessor is retained for compatibility. Logs for installed applications are in `desktop.log` in the parent directory. Working images remain outside the application installation folder and are not automatically removed by uninstalling the app.

## Updates and troubleshooting

### An old interface still appears

Stop the existing application first. An old server can occupy port 8765 while a new launch fails, leaving the browser connected to the old version. Check that the header reports **0.9.0**.

For an installed application, replacing source files alone does not update its packaged code. Rebuild the EXE/DMG and replace the installed application. On macOS, extract into a new source folder, run `bash build_macos.command`, and install the new app from `release`. Hard-refresh Chrome with **Cmd+Shift+R** on macOS or **Ctrl+F5** on Windows.

### Port 8765 is already in use

Use Quit in the existing packaged application, or Ctrl+C in the source terminal. On macOS, identify the listener:

```sh
lsof -nP -iTCP:8765 -sTCP:LISTEN
```

After confirming that it is the old Astro Laboratory process, stop its PID with `kill PID`. On Windows, locate `AstroLaboratory.exe` in Task Manager and end the old instance when it is not processing.

### Missing static/index.html

A packaged installation needs its bundled interface. Rebuild from the complete source. Windows build/installer checks stop creation when the packaged interface is missing. For a temporary Windows repair, the corresponding current `static/index.html` belongs in the installation's `_internal\static` directory.

### CLI not found or licenses fail

Use Verify & save CLI path with the actual executable, then Check licenses. Confirm product activation and model availability. Inspect job logs if processing fails.

### Dull stars

Confirm the input mode and white level. Use Star brightness 100% for diagnosis. Disable S-curves initially, use saturation 100%, and inspect separate-layer exports. Do not run BlurXTerminator on already-stretched input. Unscreen requires a matching SXT pair; version 0.9.0 extracts it before subsequent adjustments.

### GraXpert fails or darkens the nebula

Check its path, selected mode, samples, and GPU setting. Remove samples on object signal. Compare with gradient removal disabled. GraXpert is skipped in already-stretched mode.

### NumPy installation error

Check that your virtual environment uses supported 64-bit Python. Upgrading pip does not make an obsolete Python version compatible.

### Internal error or slow processing

Read the stage and elapsed time; external tools can take several minutes. For installed applications, inspect `desktop.log`; for source sessions, inspect the terminal traceback. Save `report.json` and tool logs when reporting a problem. The animated progress bar does not indicate a percentage.

The Flask development-server warning in source mode is not, by itself, a processing failure. The application serves the local loopback address.

## Build installers

- **Windows:** install 64-bit Python 3.12 and Inno Setup 6, then run `build_windows.bat`. Inno's command-line compiler is `ISCC.exe`; `Compil32.exe` is its GUI. Output: `release\AstroLaboratory-0.9.0-Windows-Setup.exe`.
- **macOS:** run `bash build_macos.command`. Output: `release/AstroLaboratory-0.9.0-macOS-arm64.dmg` or the x86_64 variant, according to the build Python architecture.

See [BUILD_INSTALLERS.md](BUILD_INSTALLERS.md) for interpreter selection, compiler paths, signing, and notarization. Build natively for each operating system and test the installed app on the target platform. External GraXpert/RC-Astro binaries, models, and proprietary licenses are not bundled.

## Version 0.9.0

This release includes separate star/object rendering, Star brightness before final merging, explicit Already stretched input with selectable white level, corrected Unscreen extraction before subsequent processing, Screen recombination, nonlinear export labeling, saved CLI path configuration, and Windows interface-packaging checks.

Automated tests cover numerical layer recombination and workflow behavior using mocked external tools. They do not guarantee identical results to PixInsight or replace validation with real CLI tools and native installers.

## License

See [LICENSE](LICENSE) in the GitHub repository. Dependencies and external tools retain their own licenses.
