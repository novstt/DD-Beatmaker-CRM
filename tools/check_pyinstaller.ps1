$ErrorActionPreference="Stop"
Write-Host "Python:" (python --version)
Write-Host "PyInstaller:"
python -m PyInstaller --version
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$upd = Join-Path $root "updater\updater.py"
if (-not (Test-Path $upd)) { throw "Missing $upd" }
$out = Join-Path $root "updater\dist_check"
$work = Join-Path $root "updater\build_check"
Remove-Item -Recurse -Force $out,$work -ErrorAction SilentlyContinue
python -m PyInstaller --noconfirm --clean --onefile --windowed --name DDUpdater --distpath $out --workpath $work --specpath $work $upd
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
$exe = Join-Path $out "DDUpdater.exe"
if (-not (Test-Path $exe)) { throw "DDUpdater.exe was not produced." }
Write-Host "OK:" $exe -ForegroundColor Green
