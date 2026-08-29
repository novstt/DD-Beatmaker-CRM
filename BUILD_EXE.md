# D&D — Windows EXE build

This release is intended to be built on the Windows machine where the project is tested.

## 1. Open PowerShell in the project root

```powershell
cd C:\Users\Quikinnn\PycharmProjects\PythonProject6
```

## 2. Enter the desktop project

The build script handles this automatically; do not `cd desktop` first.

## 3. Put the existing D&D icon here

```text
desktop\icons\dd.ico
```

The source ZIP currently contains the SVG UI icons but not the user's custom `dd.ico`, so the build script warns if it is missing.

## 4. Build

```powershell
powershell -ExecutionPolicy Bypass -File .\build_release.ps1 -Version 1.0.0
```

The script:
- installs desktop requirements;
- installs PyInstaller;
- runs syntax checks;
- runs parser regression tests;
- bundles `desktop\icons` into the application;
- builds a windowed onedir `DD.exe`.

Output:

```text
desktop\dist\DD\DD.exe
```

## 5. Build the installer

Install Inno Setup, then open:

```text
installer\DD.iss
```

Change `MyAppVersion` to the release version if needed and click Build/Compile.

Installer output:

```text
installer\output\D&D_Setup_1.0.0.exe
```

## Important

Build the Windows EXE on Windows. A Linux/macOS build environment cannot produce a native Windows PyInstaller executable reliably for this Qt application.
