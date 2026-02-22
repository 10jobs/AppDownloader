param(
  [string]$ProjectRoot = "C:\\InternalApkHub",
  [string]$PythonExe = "C:\\Python312\\python.exe",
  [string]$NssmPath = "C:\\tools\\nssm\\win64\\nssm.exe",
  [string]$ServiceName = "InternalApkHub",
  [string]$Host = "0.0.0.0",
  [int]$Port = 8080
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $NssmPath)) {
  throw "nssm not found at: $NssmPath"
}

if (-not (Test-Path $PythonExe)) {
  throw "Python not found at: $PythonExe"
}

$AppArgs = "-m uvicorn appdownloader.main:app --host $Host --port $Port"

& $NssmPath stop $ServiceName | Out-Null
& $NssmPath remove $ServiceName confirm | Out-Null

& $NssmPath install $ServiceName $PythonExe $AppArgs
& $NssmPath set $ServiceName AppDirectory $ProjectRoot
& $NssmPath set $ServiceName Start SERVICE_AUTO_START
& $NssmPath set $ServiceName DisplayName "Internal APK Hub"
& $NssmPath set $ServiceName Description "Internal APK upload/download service"

Write-Host "Service installed: $ServiceName"
Write-Host "Start with: nssm start $ServiceName"
