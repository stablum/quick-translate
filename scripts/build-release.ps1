Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

$version = @'
from pathlib import Path
import tomllib

data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
print(data["project"]["version"])
'@ | uv run python -

$appName = "quick-translate"
$distRoot = Join-Path $repoRoot "dist"
$buildRoot = Join-Path $repoRoot "build"
$appDistDir = Join-Path $distRoot $appName
$zipPath = Join-Path $distRoot "$appName-$version.zip"

if (Test-Path $appDistDir) {
    Remove-Item $appDistDir -Recurse -Force
}

if (Test-Path $buildRoot) {
    Remove-Item $buildRoot -Recurse -Force
}

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

uv sync --group dev

uv run pyinstaller `
    --noconfirm `
    --clean `
    --windowed `
    --onedir `
    --name $appName `
    --paths src `
    src\quick_translate\__main__.py

Copy-Item config.example.toml (Join-Path $appDistDir "config.toml")
Copy-Item prompt_template.txt (Join-Path $appDistDir "prompt_template.txt")
Copy-Item .env.example (Join-Path $appDistDir ".env.example")
Copy-Item README.md (Join-Path $appDistDir "README.md")

Compress-Archive -Path $appDistDir -DestinationPath $zipPath -Force
Remove-Item (Join-Path $repoRoot "quick-translate.spec") -Force -ErrorAction SilentlyContinue
Write-Host "Created $zipPath"
