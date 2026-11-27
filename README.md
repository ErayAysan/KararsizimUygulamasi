# Kararsızım 🤔

Kararsız kaldığın konularda diğer kullanıcılara danışabildiğin bir anket uygulaması.
Üyeler 2–5 seçenekli anket açar; üye olan ya da olmayan herkes oy verebilir.

Proje kuralları ve fazlar için [PLAN.md](PLAN.md) dosyasına bakın.

**Teknoloji:** Python 3.14, Django 6.1, PostgreSQL (Supabase), saf HTML/CSS/JS, WhiteNoise, Vercel.

## Lokal kurulum

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env      # sonra .env içindeki değerleri düzenle
python manage.py migrate
python manage.py createsuperuser # /admin/ için
python manage.py runserver
```

`DATABASE_URL` boş bırakılırsa lokalde SQLite (`db.sqlite3`) kullanılır; lokal geliştirme ve testler için böyle bırak.
Supabase'in **session pooler (port 5432)** bağlantı dizesini `.env` içinde `SUPABASE_DATABASE_URL` olarak sakla ve komutları şu betikle çalıştır:

```powershell
.\scripts\manage-supabase.ps1 migrate
```

> Windows'ta Smart App Control açıksa `psycopg[binary]` yüklenmez (imzasız DLL). Betik bunun yerine imzalı `libpq`
> kullanır; PostgreSQL komut satırı araçlarını kurman gerekir:
> `winget install PostgreSQL.PostgreSQL.17 --location $env:LOCALAPPDATA\PostgreSQLClient --override "--mode unattended --unattendedmodeui none --enable-components commandlinetools --disable-components server,pgAdmin,stackbuilder --prefix $env:LOCALAPPDATA\PostgreSQLClient"`
> Vercel (Linux) bundan etkilenmez.

## Test

```powershell
python manage.py check
python manage.py test
```

## Deploy

GitHub'a push edilen `main` dalı Vercel'de production'a, diğer dallar preview'a deploy edilir.
Vercel ortam değişkenleri: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`,
`CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` (transaction pooler, port 6543).

## Lisans

[MIT](LICENSE)
