# ============================================================
# Trendcord - VDS tek seferlik kurulum (Windows Server 2019)
# Cikti dosyalari sunucuda calisir. Termux'tan:
#   scp deploy/*.ps1 Kullanici@VDS:C:/trendcord-setup/
#   ssh Kullanici@VDS "powershell -File C:/trendcord-setup/setup_vds.ps1"
#
# Yapilanlar:
#   1) MEVCUT DURUM ANALIZI (git, python, sshd, nasil calisiyor?)
#   2) Klasor yapisi: C:\trendcord\{repo,releases,shared,backups}
#   3) Calistirma yontemi tespiti (gorev/service/dogrudan python)
# ============================================================
$ErrorActionPreference = "Stop"

$BASE = "C:\trendcord"

Write-Host "`n=== [1/3] MEVCUT DURUM ANALIZI ===" -ForegroundColor Cyan

Write-Host "`n-- Git:" -NoNewline
try { git --version } catch { Write-Host "YOK! https://git-scm.com/download/win kurun" -ForegroundColor Red }

Write-Host "-- Python:" -NoNewline
try { python --version } catch { Write-Host "YOK! python.org kurulumu gerekli" -ForegroundColor Red }

Write-Host "-- OpenSSH Sunucu:"
Get-Service sshd -ErrorAction SilentlyContinue | Format-Table Name, Status -AutoSize
if (-not (Get-Service sshd -ErrorAction SilentlyContinue)) {
    Write-Host "   Kuruluyor..."
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
    Start-Service sshd
    Set-Service -Name sshd -StartupType Automatic
}

Write-Host "-- Trendcord su an nasil calisiyor?"
Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -match "trendcord|python" } |
    Select-Object TaskName, State | Format-Table -AutoSize
Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match "trendcord|nssm" } |
    Select-Object Name, Status | Format-Table -AutoSize
Get-Process python* -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, Path | Format-Table -AutoSize

Write-Host "-- Mevcut kurulum var mi?:"
foreach ($p in @("C:\trendcord", "C:\Users\$env:USERNAME\trendcord")) {
    if (Test-Path $p) { Write-Host "   VAR: $p" }
}

Write-Host "`n=== [2/3] KLASOR YAPISI ===" -ForegroundColor Cyan
foreach ($d in @("$BASE\repo", "$BASE\releases", "$BASE\shared\data", "$BASE\backups", "$BASE\config")) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}
if (-not (Test-Path "$BASE\repo\.git")) {
    Write-Host "GitHub repo adresini gir (orn: https://github.com/mrcbrbn5361/trendcord.git):"
    $URL = Read-Host "URL"
    git clone $URL "$BASE\repo"
}
if (-not (Test-Path "$BASE\shared\.env")) {
    Write-Host "UYARI: $BASE\shared\.env yok! Termux'tan tasi:" -ForegroundColor Yellow
    Write-Host "  scp ~/trendcord/.env Kullanici@VDS:C:/trendcord/shared/.env"
}

Write-Host "`n=== [3/3] CALISTIRMA YONTEMI ===" -ForegroundColor Cyan
Write-Host "Deploy sonrasi uygulama nasil yeniden baslatilsin?"
Write-Host "  1) Zamanlanmis gorev (Scheduled Task)"
Write-Host "  2) Service/NSSM"
Write-Host "  3) Dogrudan python (konsol)"
$m = Read-Host "Secim (1/2/3)"
$cfg = @{ Method = "proc"; Name = "" }
switch ($m) {
    "1" {
        $tn = Read-Host "Gorev adi"
        $cfg = @{ Method = "task"; Name = $tn }
    }
    "2" {
        $sn = Read-Host "Servis adi"
        $cfg = @{ Method = "service"; Name = $sn }
    }
}
$cfg | ConvertTo-Json | Set-Content "$BASE\config\app.json"

Write-Host "`n=== SSH ANAHTARI (Termux tarafindan baglanti icin) ===" -ForegroundColor Cyan
Write-Host "Termux'taki public key icerigini yapistirin (tek satir, bos gec=atla):"
$k = Read-Host "ssh-ed25519 ..."
if ($k) {
    $isAdminGroup = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
        ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if ($isAdminGroup) {
        # Administrator kullanicilar icin OZEL DOSYA - klasik authorized_keys CALISMAZ!
        $f = "C:\ProgramData\ssh\administrators_authorized_keys"
        Add-Content -Path $f -Value $k
        icacls $f /inheritance:r /grant "SYSTEM:F" /grant "BUILTIN\Administrators:F" | Out-Null
    } else {
        Add-Content -Path "$env:USERPROFILE\.ssh\authorized_keys" -Value $k
    }
    Write-Host "Anahtar eklendi."
}

Write-Host "`n=== PAROLA GIRISINI KAPATMA (ONERILEN, SON ADIM) ===" -ForegroundColor Yellow
Write-Host "Once Termux'tan 'ssh Kullanici@VDS' ile SIFRESIZ girisi test edin!"
$a = Read-Host "Test ettiniz mi, parola girisi kapatilsin mi? (evet/hayir)"
if ($a -eq "evet") {
    $c = "C:\ProgramData\ssh\sshd_config"
    Copy-Item $c "$c.bak-$(Get-Date -Format yyyyMMddHHmmss)"
    (Get-Content $c) -replace "^#?PasswordAuthentication.*", "PasswordAuthentication no" |
        Set-Content $c
    Restart-Service sshd
    Write-Host "Parola girisi KAPATILDI. Bu oturumu kapatmayin, yeni baglantiyi ayri pencerede test edin!" -ForegroundColor Red
}

Write-Host "`nKurulum tamam. Artik deploy icin Termux'tan: ./deploy.sh" -ForegroundColor Green
