# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Kararsızım**: kullanıcıların kararsız kaldıkları konularda 2–5 seçenekli anket açtığı, üye olmayanların da oy verebildiği Django uygulaması. Kurallar, veri modeli, sayfalar ve fazlar için tek doğru kaynak [PLAN.md](PLAN.md)'dir; ilgili bölümü oradan oku. Proje fazlarla ilerler (şu an Faz 1 bitti; Faz 2 = kullanıcı sistemi). Bir fazı bitirince özetleyip dur, sonrakine kendiliğinden geçme.

## Komutlar

Windows/PowerShell; her komut proje içindeki venv ile çalışır (Python 3.14, Django 6.1):

```powershell
.\.venv\Scripts\python.exe manage.py runserver
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test                      # tüm testler (her fazın sonunda check + test geçmeli)
.\.venv\Scripts\python.exe manage.py test accounts.tests.UserModelTests.test_email_is_lowercased_on_save   # tek test
.\.venv\Scripts\python.exe manage.py makemigrations
.\.venv\Scripts\python.exe manage.py migrate
```

Lint/format aracı yok; ekleme. Ek paket eklemeden önce gerçekten gerekli mi diye sorgula.

## Mimari (birkaç dosyayı okuyunca anlaşılanlar)

- **Ayarlar ortam değişkenleriyle yönetilir** ([config/settings.py](config/settings.py)): `.env` (gitignore'da, şablon `.env.example`) `python-dotenv` ile yüklenir. `DJANGO_DEBUG` varsayılanı **False**; `DEBUG=False` iken `DJANGO_SECRET_KEY` yoksa ayarlar `RuntimeError` verir. Yani lokalde `.env` olmadan hiçbir komut çalışmaz.
- **Veritabanı:** `DATABASE_URL` boşsa SQLite, doluysa `dj_database_url` ile Supabase PostgreSQL (SSL zorunlu, `CONN_MAX_AGE=0`, `DISABLE_SERVER_SIDE_CURSORS=True` — transaction pooler 6543 için). Lokal `migrate` Supabase'in **session pooler**'ına (5432) karşı çalıştırılır; Vercel build'inde migrate çalışmaz. Yalnızca Django ORM kullanılır; Supabase Auth/supabase-js yok.
- **Özel kullanıcı modeli** ([accounts/models.py](accounts/models.py)): `AUTH_USER_MODEL = "accounts.User"`, ilk migration'dan beri. `username` ≤20 karakter, regex doğrulamalı; username ve email için `Lower(...)` ile **büyük/küçük harf duyarsız** `UniqueConstraint`; email `save()` içinde küçük harfe çevrilir. Giriş e-posta+şifre ile olacak (Faz 2). E-posta hiçbir şablonda/yanıtta gösterilmez, her yerde `username`.
- **URL yapısı:** kök `config/urls.py` → `/admin/` + `polls.urls` (`app_name="polls"`). `LOGIN_URL = "accounts:login"` henüz tanımsız bir URL'ye işaret eder; `accounts/urls.py` Faz 2'de eklenecek.
- **Anket kimliği kuralı** (Faz 3+): `Poll.id` hiçbir yerde (URL, şablon, `data-*`, JSON) görünmez; yalnızca `secrets` ile üretilen 10 karakterlik `public_id`. Seçenekler oy formunda `order` değeriyle gönderilir, Option id'si ile değil. Ayrıntı: PLAN.md 5.2.1 ve 5.3.
- **Statik dosyalar:** `static/` kaynak, `staticfiles/` üretilen çıktı (gitignore'da). WhiteNoise `CompressedManifestStaticFilesStorage` + `WHITENOISE_MANIFEST_STRICT=False` (manifest yokken testler kırılmasın). Vercel `manage.py`'yi bulup Django'yu otomatik algılar ve `collectstatic`'i kendisi çalıştırır; **`vercel.json` gerekmiyor**. Python sürümü `.python-version` ile 3.14'e sabit (Vercel 3.12/3.13/3.14 destekliyor, 3.15 yok).
- **Frontend:** Django template + saf HTML/CSS/JS; CSS framework'ü yok. Renkler `static/css/style.css`'teki `:root` değişkenleri (WCAG AA zorunlu, PLAN.md 7.3). Formlar JS kapalıyken de çalışmalı.

## Proje kuralları

- Arayüz Türkçe, kod (değişken, model, dosya adları) İngilizce; `LANGUAGE_CODE="tr"`, `TIME_ZONE="Europe/Istanbul"`.
- DRF, Celery, Redis, Docker, frontend/CSS framework'ü ekleme.
- Git: her faz kendi dalında (`faz-N-...`), commit mesajları Türkçe. Commit atılabilir; **kullanıcı istemeden `git push` yapma.**
