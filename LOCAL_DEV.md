# Локальная разработка (без деплоя на каждый чих)

## Логика

| Этап | Где | Когда |
|------|-----|--------|
| Unit-тесты | ПК, без сети | После каждой правки логики |
| Полный бот в Telegram | ПК, **dev-бот** | Кнопки, фото, заказ |
| Продакшен | Railway | Когда dev-бот ок или прокси на ПК не работает |

**Один токен = один polling.** Прод на Railway и локальный `main.py` с тем же токеном конфликтуют.

---

## 1. Создать dev-бота (один раз)

1. [@BotFather](https://t.me/BotFather) → `/newbot` → имя вроде `flower-bot-dev`
2. Скопировать токен в локальный `.env` как `BOT_TOKEN_DEV`
3. Прод-токен на Railway **не трогать**

---

## 2. Настроить `.env` на ПК

Файл: `bot/.env` (не коммитить в GitHub)

```env
DEV=1
BOT_TOKEN_DEV=123456:ABC...dev...
TELEGRAM_PROXY=socks5://127.0.0.1:10808
FLORIST_CHAT_ID=500975404
ADMIN_CHAT_ID=500975404
USE_TEST_PAYMENTS=1
```

`TELEGRAM_PROXY` — если Bot API с ПК не ходит (РФ). VPN Happ: включить **Системный прокси** (+ TUN при необходимости).

База локально: `data/bot_dev.db` (отдельно от продакшена).

---

## 3. Запуск

```powershell
cd "C:\Oleg\Cursor\Цветочный бизнес\bot"
pip install -r requirements.txt
```

**Только логика (без Telegram):**

```powershell
python test_validation.py
python test_reminder_flow.py
```

**Полный бот:**

```powershell
.\run_local.ps1
```

Или вручную:

```powershell
python test_connection.py
python main.py
```

Тестируй в Telegram у **dev-бота**. Railway можно не останавливать — токены разные.

---

## 4. Деплой на Railway

Когда dev-бот работает:

1. Правки в коде
2. `git push` в [flower-bot](https://github.com/olegkuzmin79-dotcom/flower-bot)
3. Railway пересоберёт сам

На Railway в Variables: **нет** `DEV`, **нет** `BOT_TOKEN_DEV` — только прод `BOT_TOKEN`.

---

## Если `test_connection.py` падает

Прокси на ПК не достаёт до `api.telegram.org`:

- сменить сервер VPN;
- проверить Happ: системный прокси + TUN;
- тогда тестировать через Railway (деплой), unit-тесты — всё равно на ПК.
