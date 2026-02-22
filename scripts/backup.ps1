param(
  [string]$ProjectRoot = "C:\\InternalApkHub",
  [string]$BackupRoot = "C:\\InternalApkHub\\backups"
)

$ErrorActionPreference = "Stop"

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$TargetDir = Join-Path $BackupRoot $Timestamp
New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null

$DbPath = Join-Path $ProjectRoot "data\\app.db"
$ApkPath = Join-Path $ProjectRoot "data\\apk"

if (Test-Path $DbPath) {
  Copy-Item $DbPath (Join-Path $TargetDir "app.db") -Force
}

if (Test-Path $ApkPath) {
  Copy-Item $ApkPath (Join-Path $TargetDir "apk") -Recurse -Force
}

$ZipPath = Join-Path $BackupRoot "apkhub_backup_$Timestamp.zip"
Compress-Archive -Path "$TargetDir\\*" -DestinationPath $ZipPath -Force

Write-Host "Backup complete: $ZipPath"
