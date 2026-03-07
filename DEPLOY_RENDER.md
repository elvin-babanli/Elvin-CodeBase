# Deploy to Render

## ÖNEMLİ: Render Dashboard Ayarları

### 1. Build Command
```
pip install -r requirements.txt && python manage.py collectstatic --noinput --clear
```

### 2. Start Command (KRİTİK – migrate burada çalışır)
```
bash start.sh
```
veya direkt:
```
python manage.py migrate --noinput && gunicorn core.wsgi:application --bind 0.0.0.0:$PORT
```

### 3. Environment Variables

| Key | Value |
|-----|-------|
| `SECRET_KEY` | Rastgele 50 karakter (örn. `python -c "import secrets; print(secrets.token_hex(25))"`) |
| `DEBUG` | `False` |
| `ALLOWED_HOSTS` | `elvin-babanli.com,www.elvin-babanli.com,.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://elvin-babanli.com,https://www.elvin-babanli.com` |

### 4. PostgreSQL (Önerilen – veri kalıcı olur)

1. Render → **New** → **PostgreSQL**
2. Database oluştur
3. Web Service → **Environment** → **Add**
4. `DATABASE_URL` = PostgreSQL **Internal Database URL** (Dashboard’dan kopyala)

PostgreSQL olmadan SQLite kullanılır; Render’da her deploy’da veri sıfırlanır.

## Sorun Giderme

- **auth_user tablosu yok**: Start Command’da `migrate` çalıştığından emin olun
- **robots.txt / favicon 404**: Son commit’in deploy edildiğini kontrol edin
- **500 error**: Logs’da traceback’e bakın; çoğunlukla DATABASE_URL veya migrate ile ilgilidir
