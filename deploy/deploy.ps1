# ============================================================
# Trendcord - Deploy (VDS uzerinde calisir)
# Cagirma: powershell -File C:\trendcord\repo\deploy\deploy.ps1 [-Commit <hash>]
# Termux'tan: ssh VDS "powershell -File C:/trendcord/repo/deploy/deploy.ps1"
#
# Akis: repo'da git fetch -> istenen commit'i releases\<stamp> dizinine cikar
#   -> shared\.env + shared\data bagla -> veri yedegi al
#   -> venv + pip + py_compile saglamasi -> current junction ATOMIK degisir
#   -> uygulama kalkmazsa OTOMATIK onceki release'e donulur -> son 5 saklanir
# ============================================================
param([string]$Commit = "")
$ErrorActionPreference = "Stop"

$BASE = "C:\trendcord"
$STAMP = Get-Date -Format "yyyyMMdd-HHmmss"
$REL = "$BASE\releases\$STAMP"
$CFG = Get-Content "$BASE\config\app.json" | ConvertFrom-Json

function Restart-App {
    switch ($CFG.Method) {
        "task"    { schtasks /End /TN $CFG.Name 2>$null | Out-Null; Start-Sleep 2;
                    schtasks /Run /TN $CFG.Name | Out-Null; Start-Sleep 5; return $true }
        "service" { Restart-Service $CFG.Name; Start-Sleep 5; return $true }
        default   {
            Get-Process python* -ErrorAction SilentlyContinue |
                Where-Object { $_.Path -like "*$env:USERNAME*" } |
                Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Process -WindowStyle Hidden -WorkingDirectory "$BASE\current" `
                -FilePath "python" -ArgumentList "main.py"
            Start-Sleep 5
            return $true
        }
    }
}
function Test-AppAlive {
    switch ($CFG.Method) {
        "task"    { (schtasks /Query /TN $CFG.Name) -match "Running|Haz|r" }
        "service" { (Get-Service $CFG.Name).Status -eq "Running" }
        default   { [bool](Get-Process python* -ErrorAction SilentlyContinue) }
    }
}

Write-Host "==> Deploy basliyor: $STAMP"

# 1) Kaynagi guncelle ve istenen commit'i belirle
Push-Location "$BASE\repo"
git fetch --all --quiet
$TARGET = if ($Commit) { $Commit } else { git rev-parse origin/main }
Write-Host "    Commit: $TARGET"

# 2) Temiz cikarma (git archive - kirli dosya tasinmaz)
New-Item -ItemType Directory -Force -Path $REL | Out-Null
$TMP_TAR = "$env:TEMP\tc-rel.tar"
git archive --format=tar --output="$TMP_TAR" $TARGET
Pop-Location
tar -xf "$TMP_TAR" -C $REL
if ($LASTEXITCODE -ne 0) { throw "tar cikarma basarisiz" }
Remove-Item $TMP_TAR -Force

# 3) Kalici veri ve gizli bilgiler (.env kopyalanir - uygulama sadece baslangicta okur;
#    data JUNCTION ile baglanir - canli veri kaybi olmaz, admin yetkisi gerekmez)
Copy-Item "$BASE\shared\.env" "$REL\.env"
cmd /c mklink /J "$REL\data" "$BASE\shared\data" | Out-Null

# 4) Veri yedegi (switch'ten ONCE; SQLite online backup - kilit yok)
# Yedek basarisiz olsa bile deploy durmaz: veriler shared/data'da dokunulmamis
try {
    $BAK_TMP = "$env:TEMP\tc-bak-$STAMP"
    if (Test-Path $BAK_TMP) { Remove-Item $BAK_TMP -Recurse -Force }
    python "$BASE\repo\deploy\backup_data.py" "$BASE\shared\data" $BAK_TMP
    if ((Get-ChildItem $BAK_TMP -ErrorAction SilentlyContinue | Measure-Object).Count -gt 0) {
        Compress-Archive -Path "$BAK_TMP\*" -DestinationPath "$BASE\backups\data-$STAMP.zip" -Force
        Write-Host "    Veri yedegi: backups\data-$STAMP.zip"
    }
    Remove-Item $BAK_TMP -Recurse -Force -ErrorAction SilentlyContinue
} catch {
    Write-Host "    ! Yedek alinamadi (deploy devam ediyor): $_" -ForegroundColor Yellow
}

# 5) Bagimliliklar + sozdizimi saglamasi
python -m venv "$REL\venv"
& "$REL\venv\Scripts\pip.exe" install -r "$REL\requirements.txt" --quiet --disable-pip-version-check
& "$REL\venv\Scripts\python.exe" -m py_compile "$REL\main.py"
if ($LASTEXITCODE -ne 0) { throw "py_compile basarisiz - release atiliyor" }

# 6) Atomik junction degisimi
$PREV = if (Test-Path "$BASE\current") { (Get-Item "$BASE\current").Target } else { $null }
$tmp = "$BASE\current.$STAMP"
cmd /c mklink /J "$tmp" "$REL" | Out-Null
if (Test-Path "$BASE\current") { cmd /c rmdir "$BASE\current" | Out-Null }
Move-Item -Force $tmp "$BASE\current"
Write-Host "    current -> $STAMP"

# 7) Yeniden baslat ve dogrula
Restart-App | Out-Null
if (-not (Test-AppAlive)) {
    Write-Host "!! DEPLOY BASARISIZ - onceki surume donuluyor..." -ForegroundColor Red
    if ($PREV -and (Test-Path $PREV)) {
        cmd /c rmdir "$BASE\current" | Out-Null
        cmd /c mklink /J "$BASE\current" "$PREV" | Out-Null
        Restart-App | Out-Null
        Write-Host "    Geri alindi: $PREV aktif"
    }
    exit 1
}

Write-Host "==> Deploy TAMAM: $STAMP aktif" -ForegroundColor Green

# 8) Eski release'leri temizle (son 5)
Get-ChildItem "$BASE\releases" -Directory |
    Sort-Object Name -Descending | Select-Object -Skip 5 |
    Remove-Item -Recurse -Force
