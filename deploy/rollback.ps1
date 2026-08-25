# ============================================================
# Trendcord - Rollback (VDS uzerinde calisir)
#   .\rollback.ps1              -> bir onceki release'e ANINDA don (saniyeler)
#   .\rollback.ps1 <commit>     -> istenen commit'i yeni release olarak kur
#   .\rollback.ps1 -List        -> release'leri ve yedekleri listele
# Termux'tan: ssh VDS "powershell -File C:/trendcord/repo/deploy/rollback.ps1"
# ============================================================
param([string]$Commit = "", [switch]$List)
$ErrorActionPreference = "Stop"

$BASE = "C:\trendcord"
$CFG = Get-Content "$BASE\config\app.json" | ConvertFrom-Json

function Switch-Current([string]$Target, [string]$Label) {
    if (Test-Path "$BASE\current") { cmd /c rmdir "$BASE\current" | Out-Null }
    cmd /c mklink /J "$BASE\current" "$Target" | Out-Null
    switch ($CFG.Method) {
        "task"    { schtasks /Run /TN $CFG.Name | Out-Null; Start-Sleep 5;
                    $ok = (schtasks /Query /TN $CFG.Name) -match "Running|Haz|r" }
        "service" { Restart-Service $CFG.Name; Start-Sleep 5;
                    $ok = (Get-Service $CFG.Name).Status -eq "Running" }
        default   {
                    Get-Process python* -ErrorAction SilentlyContinue |
                        Where-Object { $_.Path -like "*$env:USERNAME*" } |
                        Stop-Process -Force -ErrorAction SilentlyContinue
                    Start-Process -WindowStyle Hidden -WorkingDirectory "$BASE\current" `
                        -FilePath "python" -ArgumentList "main.py"
                    Start-Sleep 5
                    $ok = [bool](Get-Process python* -ErrorAction SilentlyContinue)
                  }
    }
    if ($ok) { Write-Host "OK: $Label aktif" -ForegroundColor Green }
    else {
        Write-Host "!! Servis kalkmadi - journal:" -ForegroundColor Red
        Write-Host "   onceki surume donmek icin tekrar: rollback.ps1"
        exit 1
    }
}

if ($List) {
    Write-Host "=== Releases (yeni -> eski) ==="
    Get-ChildItem "$BASE\releases" -Directory | Sort-Object Name -Descending |
        ForEach-Object { $mark = if ((Get-Item "$BASE\current").FullName -eq $_.FullName) {" <== AKTIF"} else {""}
                        "$($_.Name)$mark" }
    Write-Host "`n=== Veri yedekleri ==="
    Get-ChildItem "$BASE\backups" -Filter *.zip | Sort-Object Name -Descending |
        Select-Object -First 10 -ExpandProperty Name
    exit
}

if ($Commit) {
    # Istenen commit'ten yeni release kur
    $STAMP = "$(Get-Date -Format yyyyMMdd-HHmmss)-rb"
    $REL = "$BASE\releases\$STAMP"
    Write-Host "==> Commit $Commit yeni release olarak kuruluyor ($STAMP)..."
    Push-Location "$BASE\repo"
    git fetch --all --quiet
    $TMP_TAR = "$env:TEMP\tc-rb.tar"
    git archive --format=tar --output="$TMP_TAR" $Commit
    Pop-Location
    tar -xf "$TMP_TAR" -C $REL
    if ($LASTEXITCODE -ne 0) { throw "tar cikarma basarisiz" }
    Remove-Item $TMP_TAR -Force
    Copy-Item "$BASE\shared\.env" "$REL\.env"
    cmd /c mklink /J "$REL\data" "$BASE\shared\data" | Out-Null
    python -m venv "$REL\venv"
    & "$REL\venv\Scripts\pip.exe" install -r "$REL\requirements.txt" --quiet --disable-pip-version-check
    & "$REL\venv\Scripts\python.exe" -m py_compile "$REL\main.py"
    if ($LASTEXITCODE -ne 0) { throw "py_compile basarisiz" }
    Switch-Current $REL "$STAMP ($Commit)"
} else {
    # Aninda onceki release'e don
    $cur = (Get-Item "$BASE\current").FullName
    $prev = Get-ChildItem "$BASE\releases" -Directory |
        Sort-Object Name -Descending |
        Where-Object { $_.FullName -ne $cur } |
        Select-Object -First 1
    if (-not $prev) { Write-Host "Geri alinacak baska release yok!"; exit 1 }
    Write-Host "==> Onceki release'e donuluyor: $($prev.Name)"
    Switch-Current $prev.FullName $prev.Name
}
