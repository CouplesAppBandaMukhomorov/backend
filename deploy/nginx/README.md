# nginx для coupled.ru

| Домен | Куда |
| --- | --- |
| `coupled.ru` | сборка React из `/var/www/coupled` |
| `www.coupled.ru` | редирект на `coupled.ru` |
| `api.coupled.ru` | бэкенд на `127.0.0.1:8000`, `/docs`, `/redoc`, `/openapi.json` под паролем |

Каталог повторяет структуру `/etc/nginx`. Сертификаты Let's Encrypt выпускает certbot,
пароль для документации создаётся на сервере и в репозиторий не попадает.

## Установка

Команды выполняются на сервере из клона репозитория (`DEPLOY_PATH`).

1. A-записи `@`, `www`, `api` указывают на IP сервера, порты 80 и 443 открыты у хостера.
   Проверка: `dig +short api.coupled.ru`.

2. Пакеты и каталоги:

   ```bash
   sudo apt update
   sudo apt install -y nginx certbot apache2-utils
   sudo mkdir -p /var/www/certbot /var/www/coupled
   sudo rm -f /etc/nginx/sites-enabled/default
   sudo cp deploy/nginx/snippets/*.conf /etc/nginx/snippets/
   ```

3. Первый запуск только с блоком на :80. Полный конфиг не пройдёт `nginx -t`,
   пока сертификата нет:

   ```bash
   awk '1; /^}/{exit}' deploy/nginx/sites-available/coupled.conf \
     | sudo tee /etc/nginx/sites-available/coupled.conf
   sudo ln -sf /etc/nginx/sites-available/coupled.conf /etc/nginx/sites-enabled/coupled.conf
   sudo nginx -t && sudo systemctl reload nginx
   ```

4. Сертификат на все три домена:

   ```bash
   sudo certbot certonly --webroot -w /var/www/certbot \
     -d coupled.ru -d www.coupled.ru -d api.coupled.ru \
     --email <email> --agree-tos --no-eff-email
   ```

5. Перезагрузка nginx после автопродления:

   ```bash
   printf '#!/bin/sh\nsystemctl reload nginx\n' \
     | sudo tee /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
   sudo chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-nginx.sh
   sudo certbot renew --dry-run
   ```

6. Пароль на документацию API:

   ```bash
   sudo htpasswd -cB /etc/nginx/.htpasswd-docs team
   ```

   Если nginx отвечает 500 и в логе ошибка `crypt`, пересоздайте файл без `-B`.

7. Полный конфиг:

   ```bash
   sudo cp deploy/nginx/sites-available/coupled.conf /etc/nginx/sites-available/
   sudo nginx -t && sudo systemctl reload nginx
   ```

## Фронтенд

Содержимое сборки React (`dist/` у Vite, `build/` у Create React App) копируется
в `/var/www/coupled`. Неизвестные пути отдают `index.html`, поэтому клиентский роутинг работает.

## Обновление конфига

После изменений в этом каталоге:

```bash
sudo cp deploy/nginx/snippets/*.conf /etc/nginx/snippets/
sudo cp deploy/nginx/sites-available/coupled.conf /etc/nginx/sites-available/
sudo nginx -t && sudo systemctl reload nginx
```

## Проверка

```bash
curl -I http://api.coupled.ru/health
curl https://api.coupled.ru/health
curl -I https://api.coupled.ru/docs
curl -I https://www.coupled.ru
curl -m 5 http://<IP>:8000/health
```

Ожидается: 301 на https, `{"status":"ok"}`, 401 без пароля, 301 на `coupled.ru`
и таймаут на прямой порт 8000.
