param(
    [Parameter(Mandatory=$true)][string]$Version,
    [string]$ManifestUrl = "",
    [string]$PackageUrl = ""
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Desktop = Join-Path $Root "desktop"
$UpdaterDir = Join-Path $Root "updater"
$Dist = Join-Path $Desktop "dist"
$Release = Join-Path $Root "release"

Write-Host "D&D production build $Version" -ForegroundColor Cyan
Set-Location $Desktop

python -m pip install -r requirements.txt
python -m pip install pyinstaller

@"
APP_VERSION = "$Version"
"@ | Set-Content -Path (Join-Path $Desktop "version.py") -Encoding UTF8

if (-not $ManifestUrl) {
    $example = Join-Path $UpdaterDir "update.json.example"
    if (Test-Path $example) {
        try { $ManifestUrl = ((Get-Content $example -Raw | ConvertFrom-Json).manifest_url) } catch {}
    }
}
if (-not $ManifestUrl) { $ManifestUrl = "" }
@{ manifest_url = $ManifestUrl } | ConvertTo-Json | Set-Content (Join-Path $Desktop "update_config.json") -Encoding UTF8

python -m py_compile main.py api_client.py version.py test_parser_regression.py
python test_parser_regression.py

Remove-Item -Recurse -Force $Dist -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $Desktop "build") -ErrorAction SilentlyContinue
$Icon = Join-Path $Desktop "icons\dd.ico"
$args = @("--noconfirm","--clean","--windowed","--onedir","--name","DD","--add-data","icons;icons","main.py")
if (Test-Path $Icon) { $args = @("--noconfirm","--clean","--windowed","--onedir","--name","DD","--icon",$Icon,"--add-data","icons;icons","main.py") }
python -m PyInstaller @args
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed while building the D&D client (exit code $LASTEXITCODE)." }

$ClientDir = Join-Path $Dist "DD"
$ClientExe = Join-Path $ClientDir "DD.exe"
if (-not (Test-Path $ClientExe)) { throw "Client EXE was not created: $ClientExe" }

# Build updater from the same clean source tree.
Set-Location $Root
$updBuild = Join-Path $UpdaterDir "build"
$updDist = Join-Path $UpdaterDir "dist"
Remove-Item -Recurse -Force $updBuild,$updDist -ErrorAction SilentlyContinue
Write-Host "Building updater with explicit output paths..." -ForegroundColor DarkCyan
$UpdaterScript = Join-Path $UpdaterDir "updater.py"
$PyInstallerArgs = @(
    "-m","PyInstaller",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name","DDUpdater",
    "--distpath",$updDist,
    "--workpath",$updBuild,
    "--specpath",$updBuild,
    $UpdaterScript
)
python @PyInstallerArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed while building DDUpdater.exe (exit code $LASTEXITCODE)." }

$UpdaterExe = Join-Path $updDist "DDUpdater.exe"
if (-not (Test-Path $UpdaterExe)) {
    $candidates = Get-ChildItem -Path $updDist -Filter "DDUpdater.exe" -Recurse -File -ErrorAction SilentlyContinue
    if ($candidates.Count -gt 0) {
        $UpdaterExe = $candidates[0].FullName
    } else {
        throw "Updater EXE was not created. Expected: $UpdaterExe"
    }
}

New-Item -ItemType Directory -Force (Join-Path $ClientDir "updater") | Out-Null
Copy-Item $UpdaterExe (Join-Path $ClientDir "updater\DDUpdater.exe") -Force

Remove-Item -Recurse -Force $Release -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force $Release | Out-Null
$Package = Join-Path $Release ("DD_{0}.zip" -f $Version)
Compress-Archive -Path (Join-Path $ClientDir "*") -DestinationPath $Package -Force
$Sha = (Get-FileHash $Package -Algorithm SHA256).Hash.ToLowerInvariant()
$Manifest = [ordered]@{
    version = $Version
    channel = "stable"
    package_url = $PackageUrl
    sha256 = $Sha
    notes = @(
        "Finance & Payments: stable revenue split and messenger earnings",
        "Statistics: accurate personal revenue and multi-currency display",
        "User Experience: dynamic greeting and reliability fixes"
    )
}
$ManifestPath = Join-Path $Release "update.json"
$Manifest | ConvertTo-Json -Depth 5 | Set-Content $ManifestPath -Encoding UTF8

Write-Host ""
Write-Host "Client EXE : $ClientExe" -ForegroundColor Green
Write-Host "Updater EXE: $UpdaterExe" -ForegroundColor Green
Write-Host "Release ZIP: $Package" -ForegroundColor Green
Write-Host "SHA-256    : $Sha" -ForegroundColor Green
Write-Host "Manifest   : $ManifestPath" -ForegroundColor Green
Write-Host "Git is NOT required." -ForegroundColor Cyan
