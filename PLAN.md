# Kararsızım — Proje Planı (Claude Code için)

> Bu dosya, **Kararsızım** web uygulamasının tüm detaylarını içerir. Claude Code bu dosyayı projenin "tek doğru kaynağı" olarak kullanmalıdır.
> Dosyayı reponun köküne `PLAN.md` olarak koy. Her fazı ayrı ayrı uygulat (bkz. en alttaki **"Claude Code'a verilecek promptlar"** bölümü).

---

## 1. Proje Özeti

**Kararsızım**, kullanıcıların kararsız kaldıkları konularda diğer kullanıcılara danışmak için anket açabildiği bir web uygulamasıdır.

Örnek: *"Bugün sinemaya mı gitsem, müzeye mi?"* sorusu ve 2–5 seçenek → diğer kullanıcılar oy verir → soru sahibi sonuca bakıp karar verir.

### Temel kurallar
| Kural | Açıklama |
|---|---|
| Takip yok | Takipçi/takip edilen sistemi **yok**. Herkes platformdaki tüm anketleri görür. |
| Misafir erişimi | Üye olmayan kullanıcılar anketleri **görüntüleyebilir** ve **oy verebilir**. |
| Anket oluşturma | Yalnızca **üye** kullanıcılar anket oluşturabilir. |
| Seçenek sayısı | En az **2**, en fazla **5** seçenek. |
| Gizlilik | Anketlerde yalnızca **kullanıcı adı** görünür. E-posta ve şifre asla gösterilmez. |
| Amaç | Önce çalışan bir **prototip**. Karmaşık teknolojilerden kaçınılacak. |

---

## 2. Teknoloji Yığını

| Katman | Teknoloji | Not |
|---|---|---|
| Backend | Python 3.14 + Django 6.1 | Django'nun hazır auth, ORM, form, admin, template sistemi kullanılacak. (Vercel'in desteklediği en yeni Python 3.14'tür; `.python-version` ile sabitlenir.) |
| Veritabanı | Supabase (PostgreSQL) | Django ORM ile doğrudan Postgres bağlantısı. **Supabase Auth / supabase-js kullanılmayacak.** |
| Frontend | Django template + saf HTML / CSS / JavaScript | React, Vue, Tailwind, Bootstrap vb. **yok**. Aynı repo içinde. |
| Statik dosyalar | WhiteNoise | Vercel üzerinde CSS/JS servis etmek için. |
| Deployment | Vercel (Python runtime) | |
| Ortam değişkenleri | `python-dotenv` (lokal) + Vercel Environment Variables | |

### `requirements.txt` (başlangıç)
```
Django>=6.1,<6.2
psycopg[binary]>=3.3
dj-database-url>=3.1
whitenoise>=6.12
python-dotenv>=1.2
```
Ek paket eklemeden önce gerçekten gerekli olup olmadığı sorgulanmalı.

---

## 3. Genel Kurallar (Claude Code için)

1. **Basit tut.** Prototip hedefleniyor. Celery, Redis, Docker, DRF, frontend framework'ü, CSS framework'ü ekleme.
2. **Arayüz dili Türkçe**, kod (değişken, fonksiyon, model, dosya adları) **İngilizce**. URL'ler Türkçe olabilir (`/anket/yeni/`).
3. `LANGUAGE_CODE = "tr"`, `TIME_ZONE = "Europe/Istanbul"`, `USE_TZ = True`.
4. Gizli bilgiler (SECRET_KEY, DATABASE_URL) **asla** koda yazılmaz; `.env` ve `.env.example` kullanılır. `.env` `.gitignore`'da olmalı.
5. Her fazın sonunda: `python manage.py check`, `python manage.py test` çalışmalı ve geçmeli.
6. Formlar JavaScript kapalıyken de çalışmalı (progressive enhancement). JS sadece deneyimi iyileştirir.
7. Bir fazı bitirince dur, ne yaptığını özetle ve bir sonraki faza kendiliğinden geçme.
8. Kütüphane / platform davranışından emin değilsen (özellikle Vercel ve Supabase ayarları) güncel resmi dokümana bak.

---

## 4. Proje Yapısı

```
kararsizim/
├── manage.py
├── requirements.txt
├── vercel.json
├── .env.example
├── .gitignore
├── README.md
├── PLAN.md                 ← bu dosya
├── CLAUDE.md               ← kısa kurallar (Faz 1'de oluşturulacak)
├── config/                 ← Django proje ayarları
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── accounts/               ← kullanıcı sistemi
│   ├── models.py  forms.py  views.py  urls.py  admin.py  tests.py
├── polls/                  ← anket ve oylama
│   ├── models.py  forms.py  views.py  urls.py  admin.py  tests.py
│   └── middleware.py       ← misafir oy kimliği (voter token)
├── templates/
│   ├── base.html
│   ├── partials/ (navbar.html, messages.html, poll_card.html)
│   ├── accounts/ (register.html, login.html)
│   └── polls/ (poll_list.html, poll_detail.html, poll_create.html)
└── static/
    ├── css/style.css
    ├── js/main.js
    └── img/ (logo.svg, favicon)
```

---

## 5. Veri Modeli

### 5.1 `accounts.User` (özel kullanıcı modeli)
> **Önemli:** Özel kullanıcı modeli **ilk migration'dan önce** oluşturulmalı. Sonradan değiştirmek zordur.

`AbstractUser`'dan türetilir. `AUTH_USER_MODEL = "accounts.User"`.

| Alan | Tip | Kural |
|---|---|---|
| `username` | CharField(20) | Benzersiz, 3–20 karakter, sadece harf, rakam, `_` ve `.`. Büyük/küçük harf duyarsız benzersizlik (`Ahmet` ve `ahmet` aynı sayılır). |
| `email` | EmailField | **Benzersiz**, zorunlu, küçük harfe çevrilerek kaydedilir. |
| `password` | Django'nun hash'li şifresi | Django'nun varsayılan şifre doğrulayıcıları (min. 8 karakter vb.). |
| `date_joined` | Hazır | |

- Giriş **e-posta + şifre** ile yapılır (e-posta ile giriş için basit bir authentication backend veya login formunda e-postadan kullanıcıyı bulma).
- Şablonlarda ve yanıtlarda **asla** `email` gösterilmez; her yerde `username` kullanılır.

### 5.2 `polls.Poll`
| Alan | Tip | Kural |
|---|---|---|
| `id` | BigAutoField | **Sadece veritabanı içinde kullanılır, hiçbir yerde dışarı gösterilmez.** |
| `public_id` | CharField(10), `unique=True`, `db_index=True`, `editable=False` | URL'de kullanılan rastgele, benzersiz kod (bkz. 5.2.1) |
| `author` | FK → User (`on_delete=CASCADE`, `related_name="polls"`) | Zorunlu |
| `question` | CharField(200) | 5–200 karakter, baştaki/sondaki boşluklar temizlenir |
| `created_at` | DateTimeField(auto_now_add) | İndeksli, listeleme bu alana göre yeniden eskiye |

Yardımcı: `total_votes` (property veya `annotate(Count("votes"))`), `get_absolute_url()` → `/anket/<public_id>/`.

#### 5.2.1 Anket URL kimliği (`public_id`) — önemli
Anket adresleri `/anket/1/`, `/anket/2/` gibi **sırayla artan sayılar olmamalı**. Sıralı sayılar toplam anket sayısını ele verir ve adresleri tahmin etmeyi kolaylaştırır.

- Her anket oluşturulurken **10 karakterlik rastgele bir kod** üretilir. Örnek: `/anket/k7m2qx9fha/`
- Kod Python'un **`secrets`** modülüyle üretilir (`random` modülü kullanılmaz):
  ```python
  import secrets
  PUBLIC_ID_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"  # karışan 0/o, 1/l/i yok
  PUBLIC_ID_LENGTH = 10

  def generate_public_id():
      return "".join(secrets.choice(PUBLIC_ID_ALPHABET) for _ in range(PUBLIC_ID_LENGTH))
  ```
  31 harfli alfabe ve 10 karakterle yaklaşık 8 × 10¹⁴ olasılık var; çakışma pratikte imkansız.
- **Benzersizlik iki katmanda garanti edilir:**
  1. Veritabanında `unique=True` kısıtı.
  2. `Poll.save()` içinde, yeni kayıtsa kod üretilir ve kayıt `transaction.atomic()` içinde denenir; nadir bir çakışmada `IntegrityError` yakalanıp **yeni kodla en fazla 5 kez** tekrar denenir.
- Kod sadece küçük harf ve rakamdan oluştuğu için URL'de büyük/küçük harf karışıklığı olmaz.
- Kod bir kez üretilir ve **asla değişmez** (paylaşılan bağlantılar bozulmasın).
- Sayısal `id` hiçbir şablonda, URL'de, form alanında, HTML `data-*` niteliğinde veya JSON yanıtında **görünmez**. Her yerde `public_id` veya `get_absolute_url()` kullanılır.
- Admin panelinde `public_id` salt okunur olarak listelenir ve aranabilir.

### 5.3 `polls.Option`
| Alan | Tip | Kural |
|---|---|---|
| `poll` | FK → Poll (`CASCADE`, `related_name="options"`) | |
| `text` | CharField(100) | 1–100 karakter |
| `order` | PositiveSmallIntegerField | Seçenek sırası (0–4) |

- Bir ankette 2–5 seçenek olmalı (form seviyesinde doğrulanır).
- Aynı ankette **aynı metne sahip iki seçenek olamaz** (büyük/küçük harf duyarsız).
- `UniqueConstraint(fields=["poll", "order"])`.
- Oy formunda radio butonlarının `value` değeri **seçeneğin sayısal id'si değil, `order` değeridir** (0–4). Sunucu, seçeneği `poll` + `order` ile bulur. Böylece seçenek id'leri de dışarı sızmaz.

### 5.4 `polls.Vote`
| Alan | Tip | Kural |
|---|---|---|
| `poll` | FK → Poll (`CASCADE`, `related_name="votes"`) | Hızlı sayım ve benzersizlik için tekrar tutulur |
| `option` | FK → Option (`CASCADE`, `related_name="votes"`) | |
| `user` | FK → User, `null=True` | Üye oy verdiyse dolu |
| `voter_token` | UUIDField, `null=True` | Misafir oy verdiyse dolu |
| `created_at` | DateTimeField(auto_now_add) | |

**Kısıtlar (DB seviyesinde):**
- `UniqueConstraint(fields=["poll", "user"], condition=Q(user__isnull=False))`
- `UniqueConstraint(fields=["poll", "voter_token"], condition=Q(voter_token__isnull=False))`
- `CheckConstraint`: `user` ve `voter_token`'dan **tam olarak biri** dolu olmalı.
- Kayıt sırasında `option.poll_id == poll_id` doğrulanmalı.

### 5.5 Misafir oy mekanizması
- `polls/middleware.py` içinde her ziyaretçiye `kararsizim_voter` adında bir **imzalı çerez** (`set_signed_cookie`) ile UUID atanır (1 yıl ömürlü, `HttpOnly`, `SameSite=Lax`, prod'da `Secure`).
- Misafir oy verdiğinde bu UUID `voter_token` olarak kaydedilir.
- Üye kullanıcı oy verdiğinde `user` alanı kullanılır.
- Not: Bu yöntem prototip için yeterlidir; çerezi silen biri tekrar oy verebilir. Bu bilinçli bir kabuldür (ileride rate limiting / IP kontrolü eklenebilir).

### 5.6 Oylama kuralları (prototip kararları)
- Her ziyaretçi/üye bir ankete **bir kez** oy verir. Oy **değiştirilemez** (ileri fazda eklenebilir).
- Anket sahibi kendi anketine oy verebilir.
- **Sonuçlar** (yüzde + oy sayısı) şu durumlarda görünür: kullanıcı oy verdiyse **veya** anketin sahibiyse. Oy vermemiş kişiler sadece seçenekleri ve toplam oy sayısını görür. (Böylece sonuçlar oyları etkilemez.)

---

## 6. Sayfalar ve URL'ler

| URL | View | Erişim | Açıklama |
|---|---|---|---|
| `/` | `poll_list` | Herkes | Tüm anketler, en yeni üstte, sayfa başı 10 anket (Django `Paginator`) |
| `/anket/<public_id>/` | `poll_detail` | Herkes | Soru, yazar kullanıcı adı, tarih, seçenekler, oy formu veya sonuçlar |
| `/anket/<public_id>/oy/` | `vote` | Herkes (sadece POST) | Oyu kaydeder, detay sayfasına yönlendirir (PRG deseni) |
| `/anket/yeni/` | `poll_create` | `login_required` | Anket oluşturma formu |
| `/kayit/` | `register` | Sadece misafir | Kullanıcı adı, e-posta, şifre, şifre tekrar |
| `/giris/` | `login` | Sadece misafir | E-posta + şifre |
| `/cikis/` | `logout` | Üye (sadece POST) | Çıkış |
| `/admin/` | Django admin | Superuser | Moderasyon için |

- `<public_id>` için özel bir path converter (`polls/converters.py`) yazılır: sadece `[23456789a-hjkmnp-z]{10}` desenine uyan değerler kabul edilir, diğerleri doğrudan 404 olur. View'larda `get_object_or_404(Poll, public_id=public_id)` kullanılır.
- `/anket/yeni/` adresi converter'la çakışmaz ("yeni" 4 karakter); yine de `urls.py`'de `yeni/` yolu `<public_id>/`'den **önce** tanımlanır.
- Giriş yapmamış biri "Anket Oluştur"a tıklarsa: `/giris/?next=/anket/yeni/` sayfasına yönlendirilir ve *"Anket oluşturmak için giriş yapmalısın"* mesajı gösterilir.
- Kayıt sonrası kullanıcı otomatik giriş yapar ve ana sayfaya (veya `next`'e) yönlendirilir.
- Tüm kullanıcı geri bildirimleri Django `messages` framework'ü ile gösterilir ("Oyun kaydedildi! 🎉", "Bu ankete zaten oy verdin." vb.).
- 404 ve 500 için basit, tasarıma uygun özel şablonlar.

### Anket oluşturma formu
- Soru alanı + varsayılan **2 seçenek alanı**.
- "➕ Seçenek ekle" butonu (JS) ile en fazla 5'e kadar alan eklenir; eklenen alanlar "✕" ile silinebilir (en az 2 kalır).
- JS kapalıysa: 5 alan gösterilir, ilk 2'si zorunlu, boş bırakılanlar yok sayılır.
- Sunucu tarafında doğrulama: boş olmayan seçenek sayısı 2–5 arası, tekrar eden seçenek yok, karakter limitleri.
- Anket + seçenekler `transaction.atomic()` içinde kaydedilir.

---

## 7. Arayüz ve Tasarım

### 7.1 Genel his
Gençlere hitap eden, **açık renkli, dost canlısı, ferah** bir arayüz. Yuvarlak köşeler, yumuşak gölgeler, bol boşluk, küçük emoji dokunuşları. Temiz ve sade; kalabalık değil.

### 7.2 Renk paleti (CSS değişkenleri)
```css
:root {
  --bg:            #FFF9F2;  /* krem arka plan */
  --surface:       #FFFFFF;  /* kartlar */
  --text:          #1F2340;  /* ana metin — koyu lacivert */
  --text-muted:    #545A75;  /* ikincil metin */
  --border:        #ECE4F7;

  --primary:       #5B3FD9;  /* mor — ana buton (üzerinde beyaz metin) */
  --primary-hover: #4A30BF;
  --primary-soft:  #EDE8FF;  /* seçili durumlar, rozetler */

  --accent-coral:  #FF8A80;  /* dekoratif vurgular (metin rengi olarak kullanma) */
  --accent-yellow: #FFD66B;

  /* Seçenek kartları için pastel arka planlar (üzerinde --text kullanılır) */
  --opt-1: #D6E9FF;  /* gök mavisi */
  --opt-2: #C9F2E3;  /* nane */
  --opt-3: #FFE0CC;  /* şeftali */
  --opt-4: #FFF3B8;  /* limon */
  --opt-5: #EADCFF;  /* lila */

  --success: #1E7F4F;
  --error:   #B42318;
  --radius:  16px;
  --shadow:  0 4px 16px rgba(31, 35, 64, 0.08);
}
```

### 7.3 Kontrast ve erişilebilirlik (zorunlu)
- Tüm metin/arka plan çiftleri **WCAG AA**'yı sağlamalı: normal metin ≥ **4.5:1**, büyük metin ve UI öğeleri ≥ **3:1**. Uygulama sırasında palet kontrast açısından kontrol edilmeli; tutmayan renk koyulaştırılmalı.
- Dekoratif renkler (`--accent-coral`, `--accent-yellow`) metin rengi olarak kullanılmaz.
- Renk tek başına bilgi taşımaz (sonuç çubuklarında yüzde ve oy sayısı yazıyla da gösterilir).
- Görünür `:focus-visible` halkası, tüm form elemanlarında `<label>`, semantik HTML (`<main>`, `<nav>`, `<button>`), `lang="tr"`.
- Oy seçenekleri gerçek `<input type="radio">` + `<label>` ile yapılır (kart görünümlü olabilir).
- `prefers-reduced-motion` desteklenir.

### 7.4 Tipografi
- Font: **Nunito** (Google Fonts, 400/600/800) → yedek: `system-ui, sans-serif`.
- Taban font boyutu 16px, satır yüksekliği 1.5.

### 7.5 Bileşenler
- **Navbar:** Solda logo/yazı "Kararsızım 🤔", sağda: misafir → "Giriş Yap", "Kayıt Ol"; üye → "@kullaniciadi", "Anket Oluştur" (birincil buton), "Çıkış".
- **Anket kartı (liste):** Soru (kalın), "@kullaniciadi · 2 saat önce" (`timesince`), seçenek sayısı, toplam oy, "Oy ver →" bağlantısı.
- **Detay sayfası:** Büyük soru başlığı; seçenekler pastel renkli büyük tıklanabilir kartlar; "Oyumu Ver" butonu.
- **Sonuç görünümü:** Her seçenek için yatay ilerleme çubuğu (pastel renk), yüzde + oy sayısı, kullanıcının seçtiği seçenekte "✓ Senin oyun" rozeti, en çok oy alanda "🏆" işareti.
- **Boş durum:** Hiç anket yoksa sevimli bir mesaj: *"Henüz kimse kararsız değil… İlk anketi sen aç!"*
- **Responsive:** Mobil öncelikli; maks. içerik genişliği ~720px, ortalanmış.

---

## 8. Ayarlar ve Ortam Değişkenleri

### `.env.example`
```
DJANGO_SECRET_KEY=degistir-beni
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,.vercel.app
CSRF_TRUSTED_ORIGINS=https://*.vercel.app
DATABASE_URL=
```

### `settings.py` önemli noktalar
- `DATABASE_URL` boşsa lokal geliştirmede **SQLite**'a düş (hızlı başlangıç için). Doluysa `dj_database_url.parse(..., conn_max_age=0, ssl_require=True)`.
- Supabase **transaction pooler** (port 6543) kullanılırken: `DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True` ve `CONN_MAX_AGE = 0` (serverless ortam için).
- `STATIC_URL = "/static/"`, `STATIC_ROOT = BASE_DIR / "staticfiles"`, `STATICFILES_DIRS = [BASE_DIR / "static"]`, WhiteNoise middleware (`SecurityMiddleware`'den hemen sonra).
- Prod (`DEBUG=False`) için: `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`.
- `LOGIN_URL = "accounts:login"`, `LOGIN_REDIRECT_URL = "polls:list"`, `LOGOUT_REDIRECT_URL = "polls:list"`.

---

## 9. Supabase Kurulumu

1. Supabase'de yeni proje oluştur, veritabanı şifresini kaydet.
2. **Connect** ekranından iki bağlantı dizesi al:
   - **Transaction pooler (port 6543)** → Vercel'deki `DATABASE_URL` için.
   - **Session pooler veya direct connection (port 5432)** → lokalden `migrate` çalıştırmak için.
3. Migration'lar **lokalden** Supabase'e karşı çalıştırılır (`DATABASE_URL=... python manage.py migrate`). Vercel build'inde migrate çalıştırılmaz.
4. **Güvenlik — önemli:** Django tabloları `public` şemasında oluşur ve Supabase bu şemayı varsayılan olarak Data API (anon key) ile dışa açabilir. Kullanıcı tablosunda şifre hash'leri olduğu için:
   - Supabase Data API'yi kapat (projede supabase-js kullanılmıyor), **veya**
   - Tüm Django tablolarında RLS'yi etkinleştir (policy eklemeden). Django tablo sahibi rolle bağlandığı için etkilenmez.
   - Sonrasında Supabase **Security Advisor** uyarılarını kontrol et.

---

## 10. GitHub Reposu ve Git Akışı

### 10.1 Repo kurulumu (Faz 1'in ilk adımı)
1. GitHub'da `kararsizim` adında **boş** bir repo oluştur (README, .gitignore, lisans ekleme; bunlar lokalde oluşturulacak). İlk aşamada **private** önerilir.
2. Lokalde: `git init`, varsayılan dal `main`.
3. `.gitignore` **ilk commit'ten önce** oluşturulmalı ve en az şunları içermeli:
   ```
   .env
   .venv/
   venv/
   __pycache__/
   *.pyc
   db.sqlite3
   staticfiles/
   .vercel/
   .DS_Store
   .idea/
   .vscode/
   ```
4. İlk commit'ten önce `git status` ile `.env` veya `db.sqlite3`'ün listede **olmadığı** kontrol edilir.
5. `git remote add origin <repo-url>` → `git push -u origin main`.
6. Repoya kısa bir `README.md` eklenir: proje açıklaması, lokal kurulum adımları (venv, `pip install -r requirements.txt`, `.env` oluşturma, `migrate`, `runserver`).

### 10.2 Commit ve dal kuralları
- Her faz ayrı bir dalda geliştirilir: `faz-1-iskelet`, `faz-2-kullanici`, `faz-3-anketler`, `faz-4-oylama`, `faz-5-arayuz`.
- Faz içinde küçük ve anlamlı commit'ler atılır. Mesajlar Türkçe ve açıklayıcı olur. Örnek: `Kullanıcı kayıt formu eklendi`, `Oylama için benzersizlik kısıtları eklendi`.
- Faz bitip testler geçince dal `main`'e birleştirilir (GitHub'da Pull Request ile ya da lokalde merge).
- **Claude Code, kullanıcı açıkça istemeden `git push` yapmaz.** Commit'ler atılabilir, push öncesi kullanıcıya sorulur.
- Gizli bilgi (SECRET_KEY, Supabase şifresi, DATABASE_URL) **asla** commit'lenmez. Yanlışlıkla commit'lenirse sadece silmek yetmez: ilgili şifre/anahtar Supabase ve Vercel'de **yenilenmelidir**.

### 10.3 GitHub ↔ Vercel bağlantısı
- Vercel projesi, GitHub reposu **import edilerek** oluşturulur (Vercel → Add New Project → GitHub repo seç).
- Bu sayede:
  - `main` dalına her push → **production** deploy.
  - Diğer dallara / Pull Request'lere push → otomatik **preview** deploy (her fazı canlıya almadan önce preview URL'de test edebilirsin).
- Preview deploy'ların da veritabanına erişebilmesi için Vercel ortam değişkenleri hem **Production** hem **Preview** ortamına eklenir. (İleri aşamada preview için ayrı bir Supabase projesi/şubesi düşünülebilir; prototipte aynı veritabanı yeterli.)

---

## 11. Vercel Deployment

- `vercel.json` ile Django WSGI uygulaması Python runtime'ında çalıştırılır; `config/wsgi.py` içinde `app = application` tanımlanır.
- Statik dosyalar için `collectstatic` çıktısı (`staticfiles/`) WhiteNoise ile servis edilir.
- **Vercel'in Django desteği zaman içinde değişebildiği için, Claude Code bu adımda Vercel'in güncel Python/Django dokümanını kontrol edip ona göre `vercel.json` ve build adımını yazmalıdır.**
- Vercel ortam değişkenleri: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `DATABASE_URL` (transaction pooler).
- Medya dosyası yükleme **yok** (Vercel dosya sistemi kalıcı değildir).

---

## 12. Test Stratejisi

Django'nun yerleşik `TestCase`'i yeterli (pytest gerekmez). Kapsanacak senaryolar:

- **Kayıt:** geçerli kayıt; aynı e-posta/kullanıcı adı (farklı harf büyüklüğünde) reddedilir; geçersiz kullanıcı adı reddedilir.
- **Giriş:** e-posta + şifre ile giriş; yanlış şifre.
- **Anket oluşturma:** misafir → giriş sayfasına yönlendirilir; 1 seçenek → hata; 6 seçenek → hata; tekrar eden seçenek → hata; 2 ve 5 seçenek → başarılı.
- **Oylama:** misafir oy verir; aynı misafir ikinci kez oy veremez; üye oy verir ve ikinci kez veremez; başka ankete ait seçenekle oy reddedilir; GET ile oy verilemez.
- **Anket URL kimliği:** oluşturulan anketin adresi `/anket/<10 karakterlik kod>/` biçiminde; ardışık iki anketin kodları sıralı değil; `/anket/1/` gibi sayısal adres 404 döner; desene uymayan kod 404 döner; `generate_public_id` çakışma döndürecek şekilde mock'lanınca `save()` yeni kodla tekrar dener ve başarılı olur; sayfa HTML'inde anketin veya seçeneklerin sayısal id'si geçmez.
- **Gizlilik:** liste ve detay sayfalarının HTML çıktısında yazarın e-postası **geçmez**.
- **Sonuç görünürlüğü:** oy vermeyen misafir yüzdeleri görmez; oy verince görür; anket sahibi her zaman görür.

---

## 13. Fazlar

### Faz 1 — İskelet, kurulum ve ilk deploy
**Hedef:** Boş ama çalışan bir Django projesi; lokalde ve Vercel'de "Merhaba" sayfası.
- Git reposu ve GitHub bağlantısı (Bölüm 10.1): `.gitignore` ilk iş, sonra `README.md`.
- Django projesi (`config`) ve `accounts`, `polls` uygulamaları.
- **Özel kullanıcı modeli** (sadece model; formlar Faz 2'de) + ilk migration.
- `settings.py`: ortam değişkenleri, SQLite/Postgres seçimi, WhiteNoise, Türkçe/İstanbul ayarları.
- `requirements.txt`, `.env.example`, `.gitignore`, kısa `CLAUDE.md`.
- `base.html` + `style.css` içinde renk değişkenleri ve temel tipografi, basit bir ana sayfa.
- Vercel yapılandırması (GitHub reposu import edilerek, Bölüm 10.3); Supabase bağlantısı ve migrate.
- **Kabul kriteri:** Kod GitHub'da, `.env` repoda yok; `main`'e push edince Vercel otomatik deploy ediyor; Vercel URL'sinde stilli ana sayfa açılıyor, `/admin/` giriş ekranı stilleriyle görünüyor, veritabanı Supabase.

### Faz 2 — Kullanıcı sistemi
**Hedef:** Kayıt, giriş, çıkış.
- Kayıt formu (kullanıcı adı, e-posta, şifre, şifre tekrar) ve doğrulamalar.
- E-posta ile giriş.
- POST ile çıkış.
- Navbar'ın giriş durumuna göre değişmesi; `messages` gösterimi.
- Admin'de kullanıcı modeli kaydı.
- Testler (Bölüm 12'deki kayıt/giriş maddeleri).
- **Kabul kriteri:** Yeni kullanıcı kayıt olup giriş/çıkış yapabiliyor; hatalı girişlerde anlaşılır Türkçe hata mesajları çıkıyor.

### Faz 3 — Anket oluşturma ve listeleme
**Hedef:** Üyeler anket açabilir, herkes anketleri görebilir.
- `Poll` ve `Option` modelleri + admin. `Poll` modeli **ilk migration'ından itibaren** `public_id` alanıyla oluşturulur (Bölüm 5.2.1).
- `public_id` path converter'ı ve `/anket/<public_id>/` URL'leri.
- Anket oluşturma formu (2–5 seçenek, JS ile dinamik alan ekleme/çıkarma, JS'siz çalışma).
- Ana sayfada sayfalanmış anket listesi (`select_related("author")`, toplam oy için `annotate`).
- Anket detay sayfası (şimdilik oy formu pasif / sadece seçenekler).
- Boş durum ekranı.
- Testler.
- **Kabul kriteri:** Anket adresleri `/anket/k7m2qx9fha/` gibi rastgele ve benzersiz, sayısal id hiçbir yerde görünmüyor; üye 2–5 seçenekli anket açabiliyor; misafir anket açmaya çalışınca giriş sayfasına yönleniyor; listede sadece kullanıcı adı görünüyor.

### Faz 4 — Oylama ve sonuçlar
**Hedef:** Herkes oy verebilir, sonuçlar görselleşir.
- `Vote` modeli + DB kısıtları.
- Misafir voter token middleware'i.
- Oy verme view'u (POST, PRG, tek oy kuralı, `IntegrityError` yakalama). Seçilen seçenek `order` değeriyle bulunur (Bölüm 5.3).
- Sonuç görünümü: yüzde çubukları, oy sayıları, "Senin oyun" ve 🏆 rozetleri.
- Sonuç görünürlük kuralı (Bölüm 5.6).
- Testler.
- **Kabul kriteri:** Misafir ve üye birer kez oy verebiliyor; ikinci denemede nazik bir uyarı alıyor; sonuçlar doğru hesaplanıyor.

### Faz 5 — Arayüz cilası ve erişilebilirlik
**Hedef:** Prototipi "gösterilebilir" hale getirmek.
- Tüm sayfalarda tutarlı tasarım, mobil uyum, hover/focus durumları.
- Kontrast kontrolü (Bölüm 7.3) ve düzeltmeler.
- Küçük JS iyileştirmeleri: oy butonuna tıklanınca çift gönderimi engelleme, sonuç çubuklarının yumuşak animasyonla dolması (reduced-motion'a saygılı).
- Özel 404/500 sayfaları, favicon, sayfa başlıkları (`<title>`), meta description.
- **Kabul kriteri:** Mobil ve masaüstünde temiz görünüm; klavye ile tüm akış kullanılabiliyor.

### Faz 6+ — Sonra düşünülecekler (şimdilik YAPMA)
- Anket sahibinin anketini silebilmesi / kapatabilmesi, süreli anketler
- Oy değiştirme
- Okunabilir URL: `/anket/sinemaya-mi-gitsem-k7m2qx9fha/` (Türkçe karakterleri dönüştüren slug + `public_id`; sayfa yine `public_id` ile bulunur)
- Kullanıcı profil sayfası (`/@kullaniciadi` — sadece o kişinin anketleri, takip yok)
- Arama, kategoriler, "Popüler" sekmesi
- Şifre sıfırlama, e-posta doğrulama
- Rate limiting / spam koruması, raporlama
- Paylaşım bağlantısı ve Open Graph görselleri
- Karanlık mod

---

## 14. Claude Code'a Verilecek Promptlar

Her fazı **ayrı bir oturumda veya ayrı mesajla** ver. Bir faz bitip test ettikten sonra bir sonrakine geç.
Faz 2–5 promptlarının başında Claude Code, Bölüm 10.2'ye göre yeni bir faz dalı açar ve faz sonunda commit'leri atar; push için sana sorar.

**Faz 1:**
```
PLAN.md dosyasını baştan sona oku. Sadece "Faz 1 — İskelet, kurulum ve ilk deploy" bölümünü uygula.
Bölüm 3'teki genel kurallara ve Bölüm 10'daki GitHub/Git kurallarına uy. GitHub repo adresim: <REPO_URL>
İlk commit'ten önce .gitignore'u oluştur ve .env'in repoya girmediğini kontrol et. Push etmeden önce bana sor. Vercel ve Supabase ayarları için güncel resmi dokümanlara bak.
Bitince: yaptıklarını özetle, lokalde nasıl çalıştıracağımı ve Vercel/Supabase'de benim yapmam
gereken manuel adımları madde madde yaz. Faz 2'ye geçme.
```

**Faz 2:**
```
PLAN.md'yi oku. Faz 1 tamamlandı. Bölüm 10.2'ye göre faz-2-kullanici dalını aç. Şimdi sadece "Faz 2 — Kullanıcı sistemi"ni uygula.
Bölüm 5.1'deki kullanıcı kurallarına ve Bölüm 12'deki ilgili testlere uy.
Bitince testleri çalıştır, sonucu ve nasıl elle deneyebileceğimi özetle. Faz 3'e geçme.
```

**Faz 3:**
```
PLAN.md'yi oku. Faz 1-2 tamamlandı. Bölüm 10.2'ye göre faz-3-anketler dalını aç. Şimdi sadece "Faz 3 — Anket oluşturma ve listeleme"yi uygula.
Bölüm 5.2-5.3 (özellikle 5.2.1 public_id kuralları), 6 ve 7'ye uy. Testleri yaz ve çalıştır. Bitince özetle, Faz 4'e geçme.
```

**Faz 4:**
```
PLAN.md'yi oku. Faz 1-3 tamamlandı. Bölüm 10.2'ye göre faz-4-oylama dalını aç. Şimdi sadece "Faz 4 — Oylama ve sonuçlar"ı uygula.
Bölüm 5.4-5.6'daki kısıtları ve kuralları birebir uygula. Testleri yaz ve çalıştır.
Yeni migration'ı Supabase'e nasıl uygulayacağımı da yaz. Faz 5'e geçme.
```

**Faz 5:**
```
PLAN.md'yi oku. Faz 1-4 tamamlandı. Bölüm 10.2'ye göre faz-5-arayuz dalını aç. Şimdi sadece "Faz 5 — Arayüz cilası ve erişilebilirlik"i uygula.
Bölüm 7'deki tasarım ve kontrast kurallarını tüm sayfalarda kontrol et; AA'yı sağlamayan
renk çiftlerini listele ve düzelt. Yeni bağımlılık ekleme. Bitince değişiklikleri özetle.
```
