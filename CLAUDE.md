# Kararsızım — Claude için kısa kurallar

Tek doğru kaynak: [PLAN.md](PLAN.md). Her seferinde ilgili fazı oradan oku.

- Stack: Python 3.14, Django 6.1, Supabase PostgreSQL (yalnızca Django ORM), saf HTML/CSS/JS, WhiteNoise, Vercel.
- **Basit tut:** DRF, Celery, Redis, Docker, frontend/CSS framework'ü ekleme. Yeni paket eklemeden önce gerekliliğini sorgula.
- Arayüz Türkçe, kod İngilizce. `LANGUAGE_CODE="tr"`, `TIME_ZONE="Europe/Istanbul"`.
- Gizli bilgiler (SECRET_KEY, DATABASE_URL) asla koda/commit'e girmez; `.env` kullanılır.
- Anket için sayısal `id` hiçbir yerde dışarı çıkmaz; yalnızca `public_id` (PLAN.md 5.2.1). Kullanıcı e-postası hiçbir yerde gösterilmez.
- Formlar JavaScript kapalıyken de çalışmalı.
- Her fazın sonunda `python manage.py check` ve `python manage.py test` geçmeli.
- Her faz kendi dalında (`faz-N-...`) geliştirilir; commit mesajları Türkçe. **Kullanıcı istemeden `git push` yapma.**
- Bir fazı bitirince özetle ve dur; sonraki faza kendiliğinden geçme.
- Komutlar için venv: `.\.venv\Scripts\python.exe manage.py ...`
