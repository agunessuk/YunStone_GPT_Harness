# Python 3.9+ required. No automatic Python installation.
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
if (Get-Command python -ErrorAction SilentlyContinue) {
    & python "$PSScriptRoot/install.py" @args
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 "$PSScriptRoot/install.py" @args
} else {
    Write-Error 'Python 3.9 or later is required.'
    exit 1
}
exit $LASTEXITCODE
