param(
    [switch]$RunTests
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
$GridRescueDir = Split-Path -Parent (Split-Path -Parent $Root)
$OutputDir = Join-Path $GridRescueDir 'outputs'
$ReleaseDir = Join-Path $Root 'release'
$BackupDirs = @(
    'D:\桌面\GridRescue\_Wave11\backup_release',
    'C:\Users\ASUS\Documents\GridRescue_Submission_Backup'
)

Set-Location $Root
$env:PYTHONPATH = Join-Path $Root 'src'

if ($RunTests) {
    python -m pytest -q
    if ($LASTEXITCODE -ne 0) { throw "pytest failed with exit code $LASTEXITCODE" }
}

python scripts\audit_claims.py
if ($LASTEXITCODE -ne 0) { throw "claim audit failed with exit code $LASTEXITCODE" }

python scripts\check_submission_ready.py --run-smoke
if ($LASTEXITCODE -ne 0) { throw "submission readiness check failed with exit code $LASTEXITCODE" }

python scripts\build_submission.py
if ($LASTEXITCODE -ne 0) { throw "submission build failed with exit code $LASTEXITCODE" }

$ZipName = 'GridRescue_Wave11_P1_Submission.zip'
$ShaName = 'GridRescue_Wave11_P1_Submission_SHA256.txt'
New-Item -ItemType Directory -Force -Path $ReleaseDir | Out-Null
Copy-Item -LiteralPath (Join-Path $OutputDir $ZipName) -Destination $ReleaseDir -Force
Copy-Item -LiteralPath (Join-Path $OutputDir $ShaName) -Destination $ReleaseDir -Force

foreach ($BackupDir in $BackupDirs) {
    New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
    Copy-Item -LiteralPath (Join-Path $ReleaseDir $ZipName) -Destination $BackupDir -Force
    Copy-Item -LiteralPath (Join-Path $ReleaseDir $ShaName) -Destination $BackupDir -Force
}

$Hash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $ReleaseDir $ZipName)).Hash.ToLowerInvariant()
$Result = [ordered]@{
    package = Join-Path $ReleaseDir $ZipName
    sha256 = $Hash
    backups = $BackupDirs
}
$Result | ConvertTo-Json -Depth 3
