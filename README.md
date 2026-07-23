# Еко Котедж

Flask-сайт для оренди однієї хатинки в Карпатах: головна сторінка, календар доступності, форма бронювання, адмін-панель, ручне блокування дат і завантаження фотографій.

## Стек

- Python 3
- Flask
- SQLAlchemy ORM
- MySQL
- HTML5, CSS3
- Vanilla JavaScript

## Встановлення

1. Створіть віртуальне середовище:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Встановіть залежності:

```powershell
pip install -r requirements.txt
```

3. Створіть файл `.env` у корені проєкту:

```env
SECRET_KEY=replace-with-long-random-value
DATABASE_URL=mysql+pymysql://root:password@localhost/eko_kotedj?charset=utf8mb4
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

## Створення бази даних

У MySQL виконайте:

```sql
CREATE DATABASE IF NOT EXISTS eko_kotedj
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;
```

Після цього застосуйте схему:

```powershell
mysql -u root -p eko_kotedj < database/schema.sql
```

Або відкрийте `database/create_database.sql` у MySQL-клієнті. Якщо команда `SOURCE database/schema.sql` не знаходить файл, вкажіть абсолютний шлях до `schema.sql`.

Також можна створити таблиці через Flask:

```powershell
$env:FLASK_APP="app.py"
flask init-db
```

Команда створить таблиці й додасть адміністратора з даними з `.env`, якщо його ще немає.

## Запуск Flask

```powershell
$env:FLASK_APP="app.py"
flask run
```

Сайт буде доступний за адресою `http://127.0.0.1:5000`.

## Адмін-панель

Адреса входу: `http://127.0.0.1:5000/admin/login`

За замовчуванням:

- логін: `admin`
- пароль: `admin123`

Змініть ці значення у `.env` перед реальним використанням.

## Як працює бронювання

- Гість обирає дати та надсилає заявку.
- Заявка зберігається в MySQL зі статусом `pending`.
- Адміністратор може підтвердити або скасувати заявку.
- Підтверджені бронювання та ручні блокування автоматично стають недоступними в календарі.

## Фото

Адмін може завантажувати:

- Hero Image
- фото блоку "Про хатинку"
- фото галереї

Файли зберігаються у `static/uploads/`, а в базі даних зберігається лише шлях до файлу.
