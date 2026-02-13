# Greek Learning Telegram Bot 🇬🇷

Telegram-бот для изучения греческого языка с AI-генерацией предложений, озвучиванием через TTS и системой интервального повторения слов.

## 🚀 Возможности

- **AI-генерация предложений** - используется Groq API (LLaMA 3.1 70B) для создания естественных греческих предложений
- **Озвучивание** - Google Cloud Text-to-Speech для правильного произношения
- **Интервальное повторение** - система spaced repetition для эффективного запоминания слов
- **Выбор нескольких уроков** - практикуйте слова из разных уроков одновременно
- **Настройка сложности** - 3 уровня сложности предложений (легко, средне, сложно)
- **Статистика обучения** - отслеживание прогресса

## 📋 Требования

- Docker и Docker Compose
- API ключи:
  - Telegram Bot Token (бесплатно через @BotFather)
  - Groq API Key (бесплатно, 30 req/min)
  - Google Cloud TTS credentials (4M символов/месяц бесплатно)

## 🔧 Установка и запуск

### 1. Получение API ключей

#### Telegram Bot Token
1. Открой [@BotFather](https://t.me/BotFather) в Telegram
2. Отправь команду `/newbot`
3. Следуй инструкциям и получи токен

#### Groq API Key
1. Зарегистрируйся на [console.groq.com](https://console.groq.com)
2. Перейди в раздел API Keys
3. Создай новый ключ

#### Google Cloud TTS
1. Создай проект на [console.cloud.google.com](https://console.cloud.google.com)
2. Включи Text-to-Speech API
3. Создай Service Account
4. Скачай JSON файл с credentials

### 2. Настройка проекта

```bash
# Клонируй или скачай проект
cd C:\Dev\greek-bot

# Создай .env файл из примера
cp .env.example .env

# Отредактируй .env файл и добавь свои API ключи
# TELEGRAM_BOT_TOKEN=your_token_here
# GROQ_API_KEY=your_key_here
# DB_PASSWORD=your_secure_password

# Скопируй Google credentials
# Положи файл google-credentials.json в корень проекта
```

### 3. Запуск

```bash
# Запусти Docker Compose
docker-compose up -d

# Проверь логи
docker-compose logs -f bot

# Проверь статус
docker-compose ps
```

### 4. Остановка

```bash
# Остановить бота
docker-compose down

# Остановить и удалить данные
docker-compose down -v
```

## 📁 Структура проекта

```
greek-bot/
├── bot/
│   ├── database/          # Модели и репозитории БД
│   ├── handlers/          # Обработчики команд
│   ├── services/          # AI, TTS, бизнес-логика
│   ├── keyboards/         # Клавиатуры бота
│   ├── middlewares/       # Middleware
│   ├── utils/             # Утилиты
│   ├── config.py          # Конфигурация
│   └── main.py            # Точка входа
├── audio_cache/           # Кеш аудио файлов
├── logs/                  # Логи
├── docker-compose.yml     # Docker конфигурация
├── Dockerfile             # Docker образ
├── init.sql               # Схема БД
├── seed_data.sql          # Начальные данные
└── requirements.txt       # Python зависимости
```

## 💾 База данных

PostgreSQL с 6 таблицами:
- `lessons` - уроки
- `words` - слова с переводами
- `users` - пользователи (с поддержкой multi-lesson selection)
- `review_words` - слова для повторения
- `sentence_history` - история практики
- `user_statistics` - статистика пользователей

## 🎯 Использование

1. Запусти бота в Telegram
2. Отправь `/start`
3. Выбери уроки для практики (можно несколько)
4. Настрой сложность
5. Начни практику
6. Слушай предложения, добавляй забытые слова в повторение
7. Отслеживай прогресс в статистике

## 🔍 Команды

- `/start` - Главное меню
- `/help` - Справка
- `/stats` - Статистика

## 🐛 Troubleshooting

### Бот не запускается
```bash
# Проверь логи
docker-compose logs bot

# Проверь подключение к БД
docker exec -it greek_bot_db psql -U greekbot -d greek_learning
```

### Ошибка API ключей
- Проверь правильность ключей в `.env`
- Убедись, что файл `google-credentials.json` существует

### Проблемы с аудио
- Проверь квоту Google Cloud TTS
- Проверь права на директорию `audio_cache/`

## 📊 Лимиты API

- **Groq**: 30 запросов/минуту, 14,400 запросов/день (бесплатно)
- **Google TTS**: 4 млн символов/месяц (бесплатно)

## 🔄 Обновление данных

Для добавления новых уроков и слов:

```bash
# Подключись к БД
docker exec -it greek_bot_db psql -U greekbot -d greek_learning

# Добавь урок
INSERT INTO lessons (name, order_number, description) VALUES ('Новый урок', 4, 'Описание');

# Добавь слова
INSERT INTO words (greek_word, russian_translation, word_type, lesson_id) 
VALUES ('νέα λέξη', 'новое слово', 'существительное', 4);
```

## 📝 Лицензия

MIT

## 🤝 Поддержка

При возникновении проблем создай issue в репозитории.

---

**Удачи в изучении греческого языка! 🎓🇬🇷**