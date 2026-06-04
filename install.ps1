# md2pdf Windows Installer
# Run from PowerShell as a regular user (no admin required).
#
# Usage:
#   .\install.ps1           # install everything
#   .\install.ps1 -Check    # only verify what is already present
#
# Requirements: PowerShell 5.1+ (built into Windows 10/11)

[CmdletBinding()]
param(
    [switch]$Check
)

$ErrorActionPreference = 'Stop'
$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Definition

$CHROME_VERSION  = "148.0.7778.97"
$CHROME_CACHE    = "$env:USERPROFILE\.cache\puppeteer\chrome-headless-shell\win64-$CHROME_VERSION\chrome-headless-shell-win64"
$CHROME_BIN      = "$CHROME_CACHE\chrome-headless-shell.exe"
$CHROME_URL      = "https://storage.googleapis.com/chrome-for-testing-public/$CHROME_VERSION/win64/chrome-headless-shell-win64.zip"

function Write-OK   { param($msg) Write-Host "  [OK] $msg"   -ForegroundColor Green  }
function Write-Warn { param($msg) Write-Host "  [!]  $msg"   -ForegroundColor Yellow }
function Write-Err  { param($msg) Write-Host "  [X]  $msg"   -ForegroundColor Red    }
function Write-Info { param($msg) Write-Host "  --> $msg"    -ForegroundColor Cyan   }

Write-Host ""
Write-Host "  md2pdf installer (Windows)" -ForegroundColor White
Write-Host "  ==========================" -ForegroundColor White
Write-Host ""

# ── 1. Python ─────────────────────────────────────────────────────────────────
$python = $null
foreach ($cmd in @('python', 'python3', 'py')) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match 'Python (\d+)\.(\d+)') {
            $major = [int]$Matches[1]; $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 9) { $python = $cmd; break }
        }
    } catch {}
}
if (-not $python) {
    Write-Err "Python 3.9+ not found. Download from https://python.org"
    Write-Err "Make sure to check 'Add Python to PATH' during installation."
    exit 1
}
$pyVer = & $python --version 2>&1
Write-OK "$pyVer found"

# ── 2. pip ─────────────────────────────────────────────────────────────────────
try { & $python -m pip --version | Out-Null } catch {
    Write-Err "pip not found. Run: $python -m ensurepip"
    exit 1
}

$packages = @('weasyprint', 'markdown', 'pymdown-extensions', 'pygments')
$PythonInstallMode = 'system'

function Install-PythonPackages {
    param(
        [Parameter(Mandatory = $true)][string]$PythonCmd
    )

    & $PythonCmd -m pip install --quiet @packages
    return ($LASTEXITCODE -eq 0)
}

if ($Check) {
    foreach ($pkg in $packages) {
        $import = $pkg -replace 'pymdown-extensions', 'pymdownx'
        $result = & $python -c "import $import" 2>&1
        if ($LASTEXITCODE -eq 0) { Write-OK "Python package: $pkg" }
        else                     { Write-Warn "Python package missing: $pkg" }
    }
} else {
    Write-Info "Installing Python packages..."
    if (Install-PythonPackages -PythonCmd $python) {
        Write-OK "Python packages installed"
    } else {
        Write-Warn "Global pip install failed."
        Write-Host ""
        Write-Host "  Python package install fallback"
        Write-Host "  1) Create new virtual environment (.venv)"
        Write-Host "  2) Use existing virtual environment"
        Write-Host "  3) Abort"

        while ($true) {
            $choice = Read-Host "Choose [1/2/3]"
            switch ($choice) {
                '1' {
                    $defaultVenv = Join-Path $SCRIPT_DIR '.venv'
                    $venvPath = Read-Host "Venv path [$defaultVenv]"
                    if ([string]::IsNullOrWhiteSpace($venvPath)) { $venvPath = $defaultVenv }

                    Write-Info "Creating virtual environment at: $venvPath"
                    & $python -m venv $venvPath
                    if ($LASTEXITCODE -ne 0) {
                        Write-Err "Failed to create virtual environment."
                        continue
                    }

                    $venvPython = Join-Path $venvPath 'Scripts\python.exe'
                    if (-not (Test-Path $venvPython)) {
                        Write-Err "Invalid virtual environment. Missing: $venvPython"
                        continue
                    }

                    if (Install-PythonPackages -PythonCmd $venvPython) {
                        Write-OK "Python packages installed in virtual environment"
                        $PythonInstallMode = "venv:$venvPath"
                        break
                    } else {
                        Write-Err "Install failed in created virtual environment."
                    }
                }
                '2' {
                    $venvPath = Read-Host "Path to existing virtual environment"
                    if ([string]::IsNullOrWhiteSpace($venvPath)) {
                        Write-Warn "No path provided."
                        continue
                    }

                    $venvPython = Join-Path $venvPath 'Scripts\python.exe'
                    if (-not (Test-Path $venvPython)) {
                        Write-Err "Not a valid virtual environment: $venvPath"
                        continue
                    }

                    if (Install-PythonPackages -PythonCmd $venvPython) {
                        Write-OK "Python packages installed in existing virtual environment"
                        $PythonInstallMode = "venv:$venvPath"
                        break
                    } else {
                        Write-Err "Install failed in existing virtual environment."
                    }
                }
                '3' {
                    Write-Err "Aborted by user."
                    exit 1
                }
                default {
                    Write-Warn "Invalid choice. Enter 1, 2, or 3."
                }
            }
        }
    }
}

# ── 3. Node.js ─────────────────────────────────────────────────────────────────
$node = $null
foreach ($cmd in @('node', 'node.exe')) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match 'v(\d+)\.') {
            if ([int]$Matches[1] -ge 18) { $node = $cmd; break }
        }
    } catch {}
}
if (-not $node) {
    Write-Err "Node.js 18+ not found. Download from https://nodejs.org"
    exit 1
}
$nodeVer = & $node --version 2>&1
Write-OK "Node $nodeVer found"

# ── 4. npm packages ─────────────────────────────────────────────────────────────
if ($Check) {
    $mmdc = Join-Path $SCRIPT_DIR 'node_modules\.bin\mmdc.cmd'
    if (Test-Path $mmdc) { Write-OK "mmdc found" }
    else                 { Write-Warn "mmdc not found (run install.ps1 without -Check)" }
} else {
    Write-Info "Installing Node packages..."
    Push-Location $SCRIPT_DIR
    npm install --silent
    if ($LASTEXITCODE -ne 0) { Write-Err "npm install failed"; exit 1 }
    Pop-Location
    Write-OK "Node packages installed"
}

# ── 5. Chromium headless shell ─────────────────────────────────────────────────
if ($Check) {
    if (Test-Path $CHROME_BIN) { Write-OK "chrome-headless-shell found" }
    else                       { Write-Warn "chrome-headless-shell missing at: $CHROME_BIN" }
} else {
    if (Test-Path $CHROME_BIN) {
        Write-OK "chrome-headless-shell already present — skipping download"
    } else {
        Write-Info "Downloading Chromium headless shell $CHROME_VERSION (~113 MB)..."
        $tmp = [System.IO.Path]::GetTempFileName() + ".zip"
        try {
            # Use TLS 1.2+
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
            $wc = New-Object Net.WebClient
            $wc.DownloadFile($CHROME_URL, $tmp)
        } catch {
            Write-Err "Download failed: $_"
            Write-Err "Try downloading manually from: $CHROME_URL"
            exit 1
        }

        $extractTo = Split-Path -Parent $CHROME_CACHE
        New-Item -ItemType Directory -Force -Path $extractTo | Out-Null
        Write-Info "Extracting..."
        Expand-Archive -LiteralPath $tmp -DestinationPath $extractTo -Force
        Remove-Item $tmp -Force

        if (Test-Path $CHROME_BIN) { Write-OK "chrome-headless-shell installed" }
        else {
            Write-Err "Extraction succeeded but binary not found at expected path:"
            Write-Err "  $CHROME_BIN"
            Write-Err "Please check the extracted folder under: $extractTo"
            exit 1
        }
    }
}

# ── 6. Verify mmdc ─────────────────────────────────────────────────────────────
if (-not $Check) {
    $mmdc = Join-Path $SCRIPT_DIR 'node_modules\.bin\mmdc.cmd'
    if (Test-Path $mmdc) {
        Write-Info "Verifying mmdc..."
        $testMmd = [System.IO.Path]::GetTempFileName() + ".mmd"
        $testPng = [System.IO.Path]::GetTempFileName() + ".png"
        "graph TD; A-->B" | Set-Content $testMmd
        & $mmdc -i $testMmd -o $testPng 2>&1 | Out-Null
        if (Test-Path $testPng) {
            Write-OK "mmdc works"
            Remove-Item $testMmd, $testPng -Force -ErrorAction SilentlyContinue
        } else {
            Write-Warn "mmdc test failed — Mermaid diagrams may not render"
        }
    }
}

# ── 7. Summary ─────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  Installation complete." -ForegroundColor Green
Write-Host ""
if ($PythonInstallMode -like 'venv:*') {
    $venvPath = $PythonInstallMode.Substring(5)
    Write-Host "  Python packages installed in virtual environment: $venvPath"
    Write-Host "  Activate before running md2pdf:"
    Write-Host "    & '$venvPath\Scripts\Activate.ps1'"
    Write-Host ""
}
Write-Host "  Usage:"
Write-Host "    python $SCRIPT_DIR\md2pdf.py <docs-dir\>             # portrait, default margins"
Write-Host "    python $SCRIPT_DIR\md2pdf.py <docs-dir\> out.pdf     # explicit output"
Write-Host "    python $SCRIPT_DIR\md2pdf.py docs\ out.pdf -o l      # landscape"
Write-Host "    python $SCRIPT_DIR\md2pdf.py docs\ out.pdf -m 15 10 20 10  # custom margins"
Write-Host ""
Write-Host "  Add an alias in your PowerShell profile:"
Write-Host "    function md2pdf { python '$SCRIPT_DIR\md2pdf.py' @args }"
Write-Host "    (Add the line above to: `$PROFILE)"
Write-Host ""
