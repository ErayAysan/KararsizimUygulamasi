# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Kararsızım**: kullanıcıların kararsız kaldıkları konularda 2–5 seçenekli anket açtığı, üye olmayanların da oy verebildiği Django uygulaması. Kurallar, veri modeli, sayfalar ve fazlar için tek doğru kaynak [PLAN.md](PLAN.md)'dir; ilgili bölümü oradan oku. Proje fazlarla ilerler (Faz 1-4 bitti ve canlıda; Faz 5 = arayüz cilası `faz-5-arayuz` dalında; Faz 6+ plandaki "şimdilik YAPMA" listesidir, kullanıcı istemeden başlama). Bir fazı bitirince özetleyip dur, sonrakine kendiliğinden geçme.

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
- **Supabase'e komut çalıştırma:** Lokal `.env`'de `DATABASE_URL` **boş** kalır (SQLite; testler de SQLite'ta koşar), Supabase bağlantısı `SUPABASE_DATABASE_URL`'dedir. Supabase'e karşı komut için `.\scripts\manage-supabase.ps1 migrate` kullan; betik değişkenleri yalnızca o komut için ayarlar. **Supabase'e karşı `manage.py test` çalıştırma** (Django orada `test_postgres` veritabanı açar). Bağlantı dizesini/şifreyi asla ekrana yazdırma.
- **Windows Smart App Control** imzasız DLL'leri engeller: `psycopg-binary` lokalde yüklenmez. Betik bunun yerine imzalı libpq (`%LOCALAPPDATA%\PostgreSQLClient\bin`, EnterpriseDB) + `PSYCOPG_IMPL=python` kullanır. Vercel (Linux) etkilenmez. Smart App Control'ü kapatma.
- **Supabase güvenliği:** Proje `kararsizim` (Frankfurt; proje kodu bilerek burada yazılı değil, panelden bak), Data API kapalı. Django her yeni tablo oluşturduğunda (yeni migration Supabase'e uygulandıktan sonra) `public` şemasındaki tüm tablolarda RLS açılmalı (policy eklemeden; tablo sahibi `postgres` etkilenmez) ve Security Advisor kontrol edilmeli.
- **Özel kullanıcı modeli** ([accounts/models.py](accounts/models.py)): `AUTH_USER_MODEL = "accounts.User"`, ilk migration'dan beri. `username` ≤20 karakter, regex doğrulamalı; username ve email için `Lower(...)` ile **büyük/küçük harf duyarsız** `UniqueConstraint`; email `save()` içinde küçük harfe çevrilir. Giriş e-posta+şifre ile olacak (Faz 2). E-posta hiçbir şablonda/yanıtta gösterilmez, her yerde `username`.
- **URL yapısı:** kök `config/urls.py` → `/admin/` + `accounts.urls` (`kayit/ giris/ cikis/`) + `polls.urls` (`app_name="polls"`: liste `/`, `anket/yeni/`, `anket/<public_id>/`). `anket/yeni/` kodlu yoldan önce tanımlı.
- **Anket kimliği kuralı:** `Poll.id` hiçbir yerde (URL, şablon, `data-*`, JSON) görünmez; yalnızca `secrets` ile üretilen 10 karakterlik `public_id` ([polls/models.py](polls/models.py): `Poll.save()` çakışmada en fazla 5 kez yeni kod dener, kod asla değişmez). `polls/converters.py` yalnızca `[23456789a-hjkmnp-z]{10}` desenini kabul eder, gerisi 404. Seçenekler oy formunda `order` değeriyle gönderilir (şablonlarda `option.order`), Option id'si ile değil. `polls/tests.py::NumericIdLeakTests` sayısal id sızıntısını test eder. Ayrıntı: PLAN.md 5.2.1 ve 5.3.
- **Anket formu** ([polls/forms.py](polls/forms.py)): `PollForm` ModelForm değil; seçenekler aynı adlı `option` girdileri olarak gelir, şablon her zaman 5 alan çizer (JS kapalıyken hepsi görünür, boşlar yok sayılır), JS ([static/js/main.js](static/js/main.js)) alanları gösterip gizler. Misafir `anket/yeni/`ye gelirse `messages` ile "giriş yapmalısın" mesajı gösterilip `redirect_to_login` yapılır.
- **Oylama** ([polls/views.py](polls/views.py), [polls/middleware.py](polls/middleware.py)): `Vote` üye XOR misafir (`user` ya da `voter_token`, DB `CheckConstraint`) ve aynı kişi/anket için koşullu `UniqueConstraint`'ler. `VoterTokenMiddleware` her ziyaretçiye imzalı `kararsizim_voter` çerezi (UUID) verir; `request.voter_token_is_new` doğruysa misafir oyu reddedilir (çerezsiz tarayıcı sınırsız oy vermesin). Seçenek `order` ile bulunur, yalnızca o anketin seçenekleri aranır. **Sonuç görünürlüğü** (`poll_detail`): yüzdeler/oy sayıları yalnızca oy vermiş kişiye ve anket sahibine gösterilir; diğerleri seçenekleri ve toplam oyu görür. Yüzde "yarıdan yukarı" yuvarlanır (`_percent`). Anket listesinde `Count(..., distinct=True)` şart (iki join çarpılmasın). Testler `polls/test_voting.py` içinde.
- **Yeni tablo içeren faz:** Önce migration'ı Supabase'e uygula (`manage-supabase.ps1 migrate`) ve RLS'yi aç, **sonra** `main`'e birleştir/push et; aksi hâlde Vercel'e çıkan kod var olmayan tabloyu sorgular.
- **Statik dosyalar:** `static/` kaynak, `staticfiles/` üretilen çıktı (gitignore'da). WhiteNoise `CompressedManifestStaticFilesStorage` + `WHITENOISE_MANIFEST_STRICT=False` (manifest yokken testler kırılmasın). Vercel `manage.py`'yi bulup Django'yu otomatik algılar ve `collectstatic`'i kendisi çalıştırır; **`vercel.json` gerekmiyor**. Python sürümü `.python-version` ile 3.14'e sabit (Vercel 3.12/3.13/3.14 destekliyor, 3.15 yok).
- **Frontend:** Django template + saf HTML/CSS/JS; CSS framework'ü yok. Renkler `static/css/style.css`'teki `:root` değişkenleri. Formlar JS kapalıyken de çalışmalı.
- **Kontrast (WCAG AA) bir testtir:** `polls/test_design.py::ContrastTests` paletteki renk çiftlerini CSS'ten okuyup hesaplar (metin ≥ 4,5:1, kenarlık/odak/seçili durum ≥ 3:1). Yeni renk ya da yeni metin/arka plan çifti eklersen çifti o teste de ekle. Form alanı ve seçenek kartı kenarlığı `--border-strong` kullanır (`--border` yalnızca dekoratif). Seçili oy seçeneği `--selected` (parlak kırmızı) kalın çerçeve + kalın yazı + ✓ işaretiyle gösterilir; durum yalnızca renge bağlı değildir.
- **Hata sayfaları:** `404.html` `base.html`'i genişletir; `500.html` ve `403_csrf.html` bilerek **bağımsızdır** (statik dosya/şablon bağlamı olmadan çizilir, kullanıcı bilgisi yoktur). Django bunları adıyla bulur, ayar gerekmez; DEBUG açıkken teknik sayfa görünür, bu yüzden DEBUG kapalı (`DJANGO_DEBUG=False`) sunucuda bak.
- **JS iyileştirmeleri** ([static/js/main.js](static/js/main.js)): dinamik seçenek alanları ve `form[method=post]` için çift gönderim engeli (`data-submitting`; geri/ileri önbelleğinde `pageshow` ile açılır). Sonuç çubuğu animasyonu yalnızca CSS (`@keyframes bar-fill`); `prefers-reduced-motion` tüm animasyonları kapatır.
- **Erişilebilirlik:** Sayfa başında "İçeriğe geç" bağlantısı (`#icerik`), her sayfada tek `<h1>`, her girdide `<label>`, sonuç çubuklarında `role="img"` + `aria-label`, hata mesajlarında `role="alert"`.

- **BOM tuzağı:** Windows PowerShell 5.1'de `Set-Content/Out-File -Encoding utf8` dosyanın başına BOM ekler. `requirements.txt` bu yüzden Vercel build'ini kırdı (`PYTHON_REQUIREMENTS_PARSE_ERROR`), `.env`'de de ilk anahtarı bozar. `requirements.txt`/`.env` gibi dosyaları BOM'suz yaz (Write/Edit aracı ya da `[IO.File]::WriteAllText(..., (New-Object Text.UTF8Encoding $false))`).

## Proje kuralları

- Arayüz Türkçe, kod (değişken, model, dosya adları) İngilizce; `LANGUAGE_CODE="tr"`, `TIME_ZONE="Europe/Istanbul"`.
- DRF, Celery, Redis, Docker, frontend/CSS framework'ü ekleme.
- Git: her faz kendi dalında (`faz-N-...`), commit mesajları Türkçe. Commit atılabilir; **kullanıcı istemeden `git push` yapma.**
