# Windows PowerShell downloader.
# Saves each frame named by its script timestamp into .\images
# Windows forbids ":" in filenames, so ":" becomes "-"  (0:04 -> 0-04.png).
#
# How to run:
#   1. Open the "youtube-script-images" folder in File Explorer.
#   2. Right-click "download-images.ps1" -> "Run with PowerShell".
#      (If it won't run, open PowerShell in this folder and paste:
#         powershell -ExecutionPolicy Bypass -File .\download-images.ps1 )

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
New-Item -ItemType Directory -Force -Path .\images | Out-Null

$ok = 0; $fail = 0
Get-Content .\filelist.tsv | ForEach-Object {
    if (-not $_) { return }
    $parts = $_ -split "`t"
    $ts  = $parts[0]
    $url = $parts[1]
    $name = ($ts -replace ":", "-") + ".png"
    try {
        Invoke-WebRequest -Uri $url -OutFile (Join-Path ".\images" $name)
        $ok++
    } catch {
        Write-Warning "FAILED: $ts -> $url"
        $fail++
    }
}
Write-Host "Downloaded $ok images into .\images  (failures: $fail)"
