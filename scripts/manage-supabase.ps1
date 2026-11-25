# manage.py komutlarını Supabase veritabanına karşı çalıştırır.
# Kullanım:  .\scripts\manage-supabase.ps1 migrate
#            .\scripts\manage-supabase.ps1 createsuperuser
#
# Gereksinimler:
#  - .env içinde SUPABASE_DATABASE_URL (session pooler, port 5432). Lokal DATABASE_URL boş kalır (SQLite).
#  - Windows Smart App Control, psycopg-binary'nin imzasız DLL'ini engellediği için imzalı libpq
#    (PostgreSQL komut satırı araçları) kullanılır: $env:LOCALAPPDATA\PostgreSQLClient\bin
param([Parameter(ValueFromRemainingArguments = $true)] [string[]] $ManageArgs)

$root = Split-Path -Parent $PSScriptRoot
$libpq = Join-Path $env:LOCALAPPDATA "PostgreSQLClient\bin"
$line = Get-Content (Join-Path $root ".env") | Where-Object { $_ -match '^SUPABASE_DATABASE_URL=.+' } | Select-Object -First 1
if (-not $line) { throw ".env içinde SUPABASE_DATABASE_URL tanımlı değil." }

# Betik çağıranın PowerShell oturumunda çalışır; değişkenler sızıp sonraki komutları
# (özellikle `manage.py test`) Supabase'e bağlamasın diye işten sonra geri alınır.
$saved = @{ DATABASE_URL = $env:DATABASE_URL; PSYCOPG_IMPL = $env:PSYCOPG_IMPL; PATH = $env:PATH }
try {
    $env:DATABASE_URL = $line.Substring("SUPABASE_DATABASE_URL=".Length)
    $env:PSYCOPG_IMPL = "python"
    if (Test-Path $libpq) { $env:PATH = "$libpq;$env:PATH" }
    & (Join-Path $root ".venv\Scripts\python.exe") (Join-Path $root "manage.py") @ManageArgs
}
finally {
    $env:DATABASE_URL = $saved.DATABASE_URL
    $env:PSYCOPG_IMPL = $saved.PSYCOPG_IMPL
    $env:PATH = $saved.PATH
}
