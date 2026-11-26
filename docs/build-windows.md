# Build the Windows package

Use Windows 64-bit and CPython 3.13.18. The v0.1.0 build used the standard GIL, MSVC x86-64 build of [Astral's 20261124 CPython distribution](https://github.com/astral-sh/python-build-standalone/releases/tag/20261124). Validate the downloaded runtime against the release asset hash first.

Run these commands from the repository root in PowerShell.

```powershell
python -m venv .venv
$python = ".\.venv\Scripts\python.exe"
& $python -m pip install --only-binary=:all: -r requirements.txt -r requirements-build.txt
& $python test_converter.py
& $python -m PyInstaller --noconfirm --noupx --onedir --windowed --name "CLIP Drop" --collect-data tkinterdnd2 "CLIP Drop.pyw"
& $python package_windows.py CLIP-Drop-v0.1.1-win-x64.zip --app "dist/CLIP Drop" --readme README.md
& $python package_windows.py CLIP-Drop-v0.1.1-win-x64.zip
```

Extract the ZIP into a separate folder to test the included executable. The ZIP contains the user manual, three sample projects, runtime licenses and a SHA-256 manifest. To update the PDF, run `python docs/build_manual.py` with ReportLab and the Windows BIZ UD Gothic fonts installed. CLIP samples copied from `samples` can be converted without changing the copies in the repository.
