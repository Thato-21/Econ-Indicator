[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Asset = "XAUUSD",

    [Parameter(Position = 1)]
    [string]$Evidence = "examples/xauusd_evidence.json",

    [string]$Python
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

function Find-Python {
    if ($Python) {
        if (-not (Test-Path -LiteralPath $Python)) {
            throw "The Python executable '$Python' does not exist."
        }
        return (Resolve-Path -LiteralPath $Python).Path
    }

    $knownPaths = @(
        "C:\msys64\ucrt64\bin\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe"
    )
    foreach ($candidate in $knownPaths) {
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $command = Get-Command python.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notlike "*\WindowsApps\*" } |
        Select-Object -First 1
    if ($command) {
        return $command.Source
    }

    throw "Python 3.12+ was not found. Install Python from python.org, then rerun this script."
}

$PythonExe = Find-Python
$EvidencePath = if ([System.IO.Path]::IsPathRooted($Evidence)) {
    $Evidence
} else {
    Join-Path $ProjectRoot $Evidence
}

if (-not (Test-Path -LiteralPath $EvidencePath)) {
    throw "Evidence file '$EvidencePath' does not exist."
}

$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    & $PythonExe -m macro_engine.cli $Asset $EvidencePath
    if ($LASTEXITCODE -ne 0) {
        throw "The macro engine exited with code $LASTEXITCODE."
    }
} finally {
    $env:PYTHONPATH = $previousPythonPath
}

