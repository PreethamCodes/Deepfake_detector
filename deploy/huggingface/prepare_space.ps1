<#
.SYNOPSIS
Copies the SHODHA AI backend into a Hugging Face Space folder.

.DESCRIPTION
Copies only what the Space needs: the truthscan package, dependency metadata, model notices,
the repository's backend Dockerfile and the Space README. Checkpoints, data, uploads and the
frontend are excluded.
Existing files with the same names in the destination are replaced; .git is left untouched.

.EXAMPLE
powershell -ExecutionPolicy Bypass -File deploy\huggingface\prepare_space.ps1 -Destination ..\shodha-ai
#>
param([Parameter(Mandatory = $true)][string]$Destination)

$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..\..")
New-Item -ItemType Directory -Force $Destination | Out-Null
$dest = Resolve-Path $Destination

if (Test-Path (Join-Path $dest "truthscan")) { Remove-Item -Recurse -Force (Join-Path $dest "truthscan") }
Copy-Item -Recurse (Join-Path $root "truthscan") $dest
Get-ChildItem -Path (Join-Path $dest "truthscan") -Recurse -Directory -Filter "__pycache__" |
    Remove-Item -Recurse -Force

foreach ($name in "Dockerfile", "pyproject.toml", "uv.lock", ".python-version") {
    Copy-Item (Join-Path $root $name) $dest -Force
}
New-Item -ItemType Directory -Force (Join-Path $dest "docs") | Out-Null
foreach ($name in "GenD-NOTICES.md", "AASIST-NOTICE.txt") {
    Copy-Item (Join-Path $root "docs\$name") (Join-Path $dest "docs") -Force
}
Copy-Item (Join-Path $PSScriptRoot "README.md") $dest -Force
Write-Output "Space files ready in $dest"
