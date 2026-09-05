# Third-Party Notices

PanCalc Tools bundles or depends on the following third-party software. Each
component remains under its own license — the notices below are provided in
compliance with those licenses.

PanCalc Tools itself is licensed under the GNU Affero General Public License
v3.0 (see [LICENSE.md](LICENSE.md)). The complete source code is available at
<https://github.com/pan-devs/pancalc-tools>.

---

## Python dependencies

The following packages may be bundled inside the distributed executable and
installer, either directly or as transitive dependencies of PyInstaller:

| Package        | License          | Copyright / Notes |
|----------------|------------------|-------------------|
| PyMuPDF        | AGPL-3.0-or-later | Artifex Software. Commercial licensing also available from Artifex. Used for PDF analysis/merge. Compatibility note: PanCalc Tools is distributed under AGPL-3.0, so this is compatible; if you modify PanCalc Tools you must share your changes under AGPL-3.0 as required. |
| Flet           | Apache-2.0       | Flet authors. GUI framework. |
| Click          | BSD-3-Clause     | Armin Ronacher and the Click contributors. |
| Rich           | MIT              | Will McGugan and contributors. |
| Textual        | MIT              | Textualize Inc. and contributors. |
| Questionary    | MIT              | Questionary contributors. |
| requests       | Apache-2.0       | Kenneth Reitz and contributors. |
| Pillow         | HPND (PIL)       | Jeffrey A. Clark and contributors. |
| python-gnupg   | LGPL-3.0         | Vinay Sajip. |
| platformdirs   | MIT              | This project is licensed under the terms of the MIT license. |
| pywin32        | PSF-2.0          | Mark Hammond and contributors (Windows build only). |

## Bundled binaries

| Component            | License          | Notes |
|----------------------|------------------|-------|
| GnuPG (`gpg.exe`)    | GPL-3.0          | Bundled inside the app to verify registry signatures. Source: <https://gnupg.org/> (the GnuPG sources are available from gnupg.org and its mirrors). |
| Visual C++ Redistributable (`vc_redist.x64.exe`) | Microsoft | Installed by the installer under the Microsoft Visual C++ Redistributable license terms, see <https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist>. |

## Add-ins installed via the registry

Add-ins downloaded from the PanCalc registry (KhiCAS, Casio utilities, Nesizm,
etc.) are not part of PanCalc Tools itself. Each is covered by the license
declared in its registry entry. See the
[pan-calc registry](https://github.com/pan-devs/pancalc-registry) for per-add-in
details.

---

## GNU Affero General Public License v3.0

PanCalc Tools is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

**No Warranty.** PanCalc Tools is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
or FITNESS FOR A PARTICULAR PURPOSE. See the GNU AGPL-3.0 for more details.

The interactive (user-facing) text of the GNU AGPL-3.0 can be found at
<https://www.gnu.org/licenses/agpl-3.0.md>.