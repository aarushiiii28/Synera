# Publishes the API to a Hugging Face Docker Space.
#   .\deploy\huggingface\publish.ps1 -Space https://huggingface.co/spaces/<user>/<name>
#   .\deploy\huggingface\publish.ps1 -Space ... -DryRun      (build the package folder only, push nothing)
# Git asks for your Hugging Face username and, as the password, an access token with WRITE permission
# (huggingface.co/settings/tokens). Only files the API needs are sent; the key, databases and node_modules never are.
param(
  [Parameter(Mandatory = $true)][string]$Space,
  [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pkg = Join-Path $env:TEMP 'synera_hf_package'
if (Test-Path $pkg) { Remove-Item $pkg -Recurse -Force }
New-Item -ItemType Directory $pkg | Out-Null

Push-Location $root
$keep = '^(backend|configs|data|scripts|src)/|^pyproject\.toml$'
$files = git ls-files -co --exclude-standard | Where-Object { $_ -match $keep -and $_ -notmatch '^backend/venv/' }
foreach ($f in $files) {
  if (Test-Path -LiteralPath $f -PathType Leaf) {
    $dest = Join-Path $pkg $f
    New-Item -ItemType Directory -Force (Split-Path $dest) | Out-Null
    Copy-Item -LiteralPath $f $dest
  }
}
Pop-Location
Copy-Item (Join-Path $PSScriptRoot 'Dockerfile') (Join-Path $pkg 'Dockerfile')
Copy-Item (Join-Path $PSScriptRoot 'README.md') (Join-Path $pkg 'README.md')

$mb = [math]::Round((Get-ChildItem $pkg -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
$big = Get-ChildItem $pkg -Recurse -File | Where-Object { $_.Length -gt 10MB }
Write-Host "Package: $pkg  ($($files.Count) files, $mb MB)"
if ($big) { throw "Files over 10 MB are rejected by Hugging Face: $($big.FullName -join ', ')" }
if ($DryRun) { Write-Host 'Dry run: nothing pushed.'; return }

Push-Location $pkg
git init -q -b main
git add -A
git -c user.name='synera-deploy' -c user.email='deploy@localhost' commit -q -m 'Deploy SYNERA API'
git push --force $Space main
Pop-Location
Write-Host 'Pushed. Watch the Space build under its Logs tab.'
