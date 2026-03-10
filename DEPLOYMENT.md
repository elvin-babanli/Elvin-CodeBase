# Deployment Guide

## Database Persistence

**Mevcut verilerin korunması için:**

### Render.com
- `DATABASE_URL` env var'ı Render PostgreSQL'den gelmeli (`fromDatabase`).
- Veritabanı servisi ayrı bir kaynaktır; deploy sırasında **silinmez**.
- `migrate --noinput` sadece yeni migration'ları uygular; mevcut verileri **silmez**.
- **Asla** `migrate --run-syncdb`, `flush`, `reset_db` veya `drop` kullanmayın.

### Kontrol Listesi
1. Render Dashboard → Service → Environment → `DATABASE_URL` bağlı mı?
2. Database Service (`django-codebase-db`) aynı projede ve bağlı mı?
3. Build command'da sadece: `migrate --noinput` (destructive komut yok)

### Veri Kaybı Nedenleri
- **SQLite kullanımı:** Render'da dosya sistemi geçicidir; SQLite her deploy'da sıfırlanır. **PostgreSQL kullanın.**
- **DATABASE_URL boş:** Local SQLite'a düşer, deploy'da kaybolur.
- **Farklı DB instance:** Her deploy yeni DB oluşturuluyorsa veriler kalıcı olmaz.

### Build/Start Komutları (render.yaml)
```yaml
buildCommand: "pip install -r requirements.txt && python manage.py migrate --noinput && python create_admin_user.py && python manage.py collectstatic --noinput"
startCommand: "gunicorn core.wsgi:application --bind 0.0.0.0:$PORT"
```
- `migrate --noinput`: Sadece yeni migration'ları uygular (safe).
- `create_admin_user.py`: Sadece admin kullanıcı oluşturur/günceller; veri silmez.
