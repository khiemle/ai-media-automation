# setup-windows.ps1
# One-time bootstrap for the Windows render machine.
# Run as Administrator in PowerShell 7+.
#
# Usage:
#   .\scripts\setup-windows.ps1 `
#     -GithubRepo "khiemle/ai-media-automation" `
#     -GithubRunnerToken "YOUR_TOKEN"
#
# Get the runner token from:
#   GitHub repo → Settings → Actions → Runners → New self-hosted runner → Windows
#   Copy the value after --token in the config step.

param(
    [Parameter(Mandatory=$true)]
    [string]$GithubRepo,

    [Parameter(Mandatory=$true)]
    [string]$GithubRunnerToken,

    [string]$RepoPath    = "C:\ai-media",
    [string]$RenderRoot  = "C:\render",
    [string]$RunnerPath  = "C:\actions-runner",
    [string]$RunnerVersion = "2.325.0"
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # speeds up Invoke-WebRequest

Write-Host "`n=== AI Media Automation - Windows Setup ===" -ForegroundColor Cyan

# ── 1. Verify prerequisites ──────────────────────────────────────────────────
Write-Host "`n[1/6] Checking prerequisites..." -ForegroundColor Yellow

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "Docker is not installed or not in PATH. Install Docker Desktop first."
    exit 1
}
docker info | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker Desktop is not running. Start it and re-run this script."
    exit 1
}
Write-Host "  Docker OK"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    Write-Error "GitHub CLI (gh) is not installed. Run: winget install --id GitHub.cli"
    exit 1
}
Write-Host "  GitHub CLI OK"

# ── 2. Create required directories ──────────────────────────────────────────
Write-Host "`n[2/6] Creating directories..." -ForegroundColor Yellow
$dirs = @(
    "$RenderRoot\output",
    "$RenderRoot\assets\video_db",
    "$RenderRoot\assets\music",
    "$RenderRoot\models",
    $RepoPath,
    $RunnerPath
)
foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    Write-Host "  OK  $dir"
}

# ── 3. Clone the repository ──────────────────────────────────────────────────
Write-Host "`n[3/6] Cloning repository..." -ForegroundColor Yellow
if (Test-Path "$RepoPath\.git") {
    Write-Host "  Already cloned at $RepoPath - skipping"
} else {
    gh repo clone $GithubRepo $RepoPath
    Write-Host "  Cloned -> $RepoPath"
}

# ── 4. Authenticate Docker with GHCR ────────────────────────────────────────
Write-Host "`n[4/6] Authenticating Docker with GHCR..." -ForegroundColor Yellow
gh auth token | docker login ghcr.io -u (gh api user --jq .login) --password-stdin
Write-Host "  Docker authenticated with ghcr.io"

# ── 5. Set up GitHub Actions self-hosted runner ──────────────────────────────
Write-Host "`n[5/6] Setting up GitHub Actions runner..." -ForegroundColor Yellow
Set-Location $RunnerPath

if (-not (Test-Path "$RunnerPath\svc.cmd")) {
    $zipUrl  = "https://github.com/actions/runner/releases/download/v$RunnerVersion/actions-runner-win-x64-$RunnerVersion.zip"
    $zipPath = "$RunnerPath\runner.zip"
    Write-Host "  Downloading runner v$RunnerVersion..."
    Invoke-WebRequest -Uri $zipUrl -OutFile $zipPath
    Expand-Archive -Path $zipPath -DestinationPath $RunnerPath -Force
    Remove-Item $zipPath
    Write-Host "  Extracted"
}

$repoUrl = "https://github.com/$GithubRepo"
.\config.cmd `
    --url   $repoUrl `
    --token $GithubRunnerToken `
    --name  "windows-render" `
    --labels "self-hosted,windows,render" `
    --work  "$RunnerPath\_work" `
    --unattended `
    --replace

$taskName = "GitHubActionsRunner-windows-render"

$existingTask = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "  Task already exists, stopping..."
    Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
}

$action   = New-ScheduledTaskAction -Execute "$RunnerPath\run.cmd" -WorkingDirectory $RunnerPath
$trigger  = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([System.TimeSpan]::Zero) `
                -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
$currentUser = "$env:USERDOMAIN\$env:USERNAME"
$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType S4U -RunLevel Highest
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

Start-ScheduledTask -TaskName $taskName
Write-Host "  Runner registered as scheduled task '$taskName' and started"

# ── 6. Open firewall ports ───────────────────────────────────────────────────
Write-Host "`n[6/6] Opening firewall ports..." -ForegroundColor Yellow
@(
    @{ Port = 3000; Name = "AI-Media-Frontend" },
    @{ Port = 8080; Name = "AI-Media-API" }
) | ForEach-Object {
    if (-not (Get-NetFirewallRule -DisplayName $_.Name -ErrorAction SilentlyContinue)) {
        New-NetFirewallRule -DisplayName $_.Name -Direction Inbound `
            -Protocol TCP -LocalPort $_.Port -Action Allow | Out-Null
        Write-Host "  Opened port $($_.Port)"
    } else {
        Write-Host "  Port $($_.Port) already open"
    }
}

# ── Verify GPU visibility ────────────────────────────────────────────────────
Write-Host "`nVerifying GPU in Docker..." -ForegroundColor Yellow
docker run --rm --gpus all nvidia/cuda:12.3.2-base-ubuntu22.04 nvidia-smi
if ($LASTEXITCODE -ne 0) {
    Write-Warning "GPU not visible to Docker. Check Docker Desktop -> Settings -> Resources -> GPU."
} else {
    Write-Host "  GPU OK"
}

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host "`n=== Setup complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. From your Mac terminal, run the 'gh secret set' commands in the spec"
Write-Host "  2. Push to main (or run the Deploy workflow manually in GitHub Actions)"
Write-Host "  3. Open http://localhost:3000 in a browser on this machine"
Write-Host "     Or http://<this-machine-ip>:3000 from your Mac"
Write-Host ""
Write-Host "Render output : $RenderRoot\output"
Write-Host "Asset library : $RenderRoot\assets"
Write-Host "Models        : $RenderRoot\models"
Write-Host "Runner logs   : $RunnerPath\_diag"
