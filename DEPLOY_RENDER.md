# Render Deploy — Portfolio Site

## Önerilen Ayarlar

### Build Command
```
pip install -r requirements.txt && python manage.py migrate --noinput && python manage.py collectstatic --noinput
```
veya `./build.sh` (build.sh varsa)

### Start Command
```
gunicorn core.wsgi:application --bind 0.0.0.0:$PORT
```
**Önemli:** Sadece gunicorn. `start.sh` veya migrate kullanma.

### Neden?
- **migrate** Build sırasında çalışır; tablolar oluşturulur
- **Start** sadece gunicorn başlatır; site hemen açılır
- `start.sh` ile migrate, hata alırsa gunicorn hiç başlamaz → beyaz ekran

---

## Environment Variables

| Key | Value |
|-----|-------|
| `SECRET_KEY` | Rastgele 50 karakter |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `elvin-babanli.com,www.elvin-babanli.com,.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://elvin-babanli.com,https://www.elvin-babanli.com` |

### PostgreSQL (kalıcı veri için)
- New → PostgreSQL
- Web service’e bağla → `DATABASE_URL` otomatik gelir

---

### Email (Forgot Password)
Gmail: `EMAIL_HOST=smtp.gmail.com`, `EMAIL_HOST_USER=elvinbabanli0@gmail.com`, `GMAIL_APP_PASSWORD=...` — Detay: `EMAIL_SETUP.md`

---

## Sorun Giderme

| Sorun | Çözüm |
|-------|--------|
| Beyaz ekran / site açılmıyor | Start Command’da sadece gunicorn olmalı; migrate Build’de |
| auth_user yok | Build Command’a `python manage.py migrate --noinput` ekle |
| robots.txt / favicon 404 | Son commit deploy edildi mi kontrol et |
| Doğrulama kodu gelmiyor | EMAIL_HOST, EMAIL_HOST_USER, GMAIL_APP_PASSWORD ayarla; `EMAIL_SETUP.md` |
