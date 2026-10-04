# =====================================================================
# push_update.ps1
# Commit + push update ke GitHub supaya Streamlit Cloud ter-redeploy.
# Jalankan dari mana saja di dalam repo:
#   powershell -ExecutionPolicy Bypass -File .\push_update.ps1 -Message "pesan commit"
# Opsi:
#   -Branch main     branch tujuan (default: main)
#   -MaxFileMB 50    batas ukuran file per commit (GitHub menolak > 100 MB)
#   -Yes             lewati konfirmasi
# =====================================================================
[CmdletBinding()]
param(
    [string]$Message,
    [string]$Branch = "main",
    [int]$MaxFileMB = 50,
    [switch]$Yes
)

function Info($m) { Write-Host $m -ForegroundColor Cyan }
function Warn($m) { Write-Host "PERINGATAN: $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "GAGAL: $m" -ForegroundColor Red; exit 1 }

# --- 0. Pastikan di dalam repo git --------------------------------------
$root = git rev-parse --show-toplevel 2>$null
if (-not $root) { Fail "Folder ini bukan repo git." }
Set-Location $root
Info "Repo: $root"

$current = git rev-parse --abbrev-ref HEAD
if ($current -ne $Branch) {
    Fail "Branch aktif '$current', bukan '$Branch'. Pindah dulu atau pakai -Branch $current."
}

# --- 1. File wajib untuk deploy -----------------------------------------
$required = @(
    ".streamlit/config.toml",
    "requirements.txt",
    "app/main.py",
    "data/processed/df_geo.parquet"
)
foreach ($f in $required) {
    if (-not (Test-Path $f)) { Fail "File wajib tidak ditemukan: $f" }
}

# --- 2. Folder app/static (file statis untuk peta) ----------------------
if (Test-Path "app/static") {
    $n = (Get-ChildItem "app/static" -Recurse -File | Measure-Object).Count
    if ($n -eq 0) { Warn "app/static ada tetapi kosong." }
    $cfg = Select-String -Path ".streamlit/config.toml" -Pattern "enableStaticServing\s*=\s*true" -Quiet
    if (-not $cfg) {
        Fail "app/static dipakai, tetapi .streamlit/config.toml belum berisi 'enableStaticServing = true' di bagian [server]."
    }
} else {
    Warn "app/static belum ada (abaikan bila belum memakai file statis)."
}

# --- 3. .gitignore: jangan sampai app/static/*.geojson ikut terabaikan ---
if (Test-Path ".gitignore") {
    $gi = Get-Content ".gitignore" -Raw
    if (($gi -match '(?m)^\*\.geojson\s*$') -and ($gi -notmatch '(?m)^!app/static/')) {
        Add-Content ".gitignore" "`n!app/static/*.geojson"
        Info "Menambahkan pengecualian .gitignore: !app/static/*.geojson"
    }
}

# --- 4. Stage semua perubahan -------------------------------------------
git add -A
if ($LASTEXITCODE -ne 0) { Fail "git add gagal." }

# --- 5. Pastikan file di app/static benar-benar terlacak git -------------
if (Test-Path "app/static") {
    Get-ChildItem "app/static" -Recurse -File | ForEach-Object {
        $rel = ($_.FullName.Substring($root.Length + 1)) -replace '\\', '/'
        git ls-files --error-unmatch $rel 2>$null | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Warn "Tidak terlacak git (kena .gitignore?): $rel"
        }
    }
}

# --- 6. Pemeriksaan ukuran dan file terlarang ---------------------------
$staged  = git diff --cached --name-only --diff-filter=AM
$blocked = @()
foreach ($f in $staged) {
    if ($f -match '^(\.venv/|data/_big_local/|\.streamlit/secrets\.toml$|\.env$)') {
        $blocked += "dilarang masuk repo: $f"
        continue
    }
    if (Test-Path -LiteralPath $f) {
        $mb = (Get-Item -LiteralPath $f).Length / 1MB
        if ($mb -gt $MaxFileMB) {
            $blocked += ("{0:N1} MB (> {1} MB): {2}" -f $mb, $MaxFileMB, $f)
        } elseif ($mb -gt 25) {
            Warn ("File besar {0:N1} MB: {1}" -f $mb, $f)
        }
    }
}
if ($blocked.Count -gt 0) {
    git reset -q
    $blocked | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Fail "Ada file yang tidak boleh di-push. Staging sudah dibatalkan; perbaiki .gitignore atau ukuran file lalu jalankan ulang."
}

# --- 7. Pemeriksaan token rahasia (Mapbox) ------------------------------
$diff = git diff --cached -U0
if ($diff -match '\bsk\.[A-Za-z0-9_\-]{20,}') {
    git reset -q
    Fail "Terdeteksi token Mapbox RAHASIA (sk.). Pindahkan ke .streamlit/secrets.toml (di-ignore) dan jangan commit."
}
if ($diff -match '\bpk\.[A-Za-z0-9_\-]{20,}') {
    Warn "Terdeteksi token publik Mapbox (pk.) di perubahan. Batasi per-URL di dashboard Mapbox, atau pindahkan ke Secrets Streamlit."
}

# --- 8. Ringkasan dan konfirmasi ----------------------------------------
Info "`nRingkasan perubahan:"
git status --short
git diff --cached --quiet
$adaPerubahan = ($LASTEXITCODE -ne 0)

if ($adaPerubahan -and -not $Yes) {
    $jawab = Read-Host "`nLanjut commit dan push? (y/n)"
    if ($jawab -notin @("y", "Y", "ya", "Ya")) { git reset -q; Fail "Dibatalkan oleh pengguna." }
}

# --- 9. Commit ----------------------------------------------------------
if ($adaPerubahan) {
    if (-not $Message) {
        $Message = Read-Host "Pesan commit (Enter = default)"
        if (-not $Message) { $Message = "Update web story " + (Get-Date -Format "yyyy-MM-dd HH:mm") }
    }
    git commit -m $Message
    if ($LASTEXITCODE -ne 0) { Fail "git commit gagal." }
} else {
    Info "Tidak ada perubahan baru untuk di-commit."
}

# --- 10. Sinkronkan dengan remote, lalu push ----------------------------
git fetch origin
if ($LASTEXITCODE -ne 0) { Fail "git fetch gagal. Periksa koneksi/autentikasi GitHub." }

$ahead = [int](git rev-list --count "origin/$Branch..HEAD")
if (-not $adaPerubahan -and $ahead -eq 0) {
    Info "Tidak ada yang perlu di-push. Remote sudah terbaru."
    exit 0
}

git pull --rebase origin $Branch
if ($LASTEXITCODE -ne 0) {
    Fail "Rebase gagal/konflik. Selesaikan konflik lalu 'git rebase --continue', atau batalkan dengan 'git rebase --abort'."
}

git push origin $Branch
if ($LASTEXITCODE -ne 0) {
    Fail "git push gagal. Jangan pakai --force; kirim pesan error di atas untuk didiagnosis."
}

Write-Host "`nBERHASIL di-push ke origin/$Branch." -ForegroundColor Green
git log -1 --oneline
Info "Streamlit Cloud akan otomatis redeploy (biasanya 1-3 menit). Pantau di dashboard share.streamlit.io."
