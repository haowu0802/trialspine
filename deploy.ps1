# Deploy trialspine to Fly.io (US West / sjc)
# Uses local Docker Desktop (--local-only), same pattern as workforce.
#
# First time:
#   1. fly auth login
#   2. fly apps create trialspine --org personal
#   3. fly postgres create --name haowu-trialspine-db --region sjc --vm-size shared-cpu-1x --volume-size 1
#   4. fly postgres attach haowu-trialspine-db -a trialspine
#   5. .\deploy.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Get-Command fly -ErrorAction SilentlyContinue)) {
    Write-Host "flyctl not found. Install: iwr https://fly.io/install.ps1 -useb | iex" -ForegroundColor Yellow
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker not found. Start Docker Desktop, then retry." -ForegroundColor Yellow
    exit 1
}

Write-Host "Deploying trialspine (region sjc, local Docker build)..." -ForegroundColor Cyan
fly deploy --local-only --wait-timeout 10m

if ($LASTEXITCODE -eq 0) {
    Write-Host "Done. Open: https://trialspine.fly.dev/" -ForegroundColor Green
    Write-Host "Health: https://trialspine.fly.dev/health" -ForegroundColor Green
} else {
    Write-Host "Deploy reported failure. Check:" -ForegroundColor Yellow
    Write-Host "  https://trialspine.fly.dev/health" -ForegroundColor Yellow
    Write-Host "  fly status --app trialspine" -ForegroundColor Yellow
    exit $LASTEXITCODE
}
