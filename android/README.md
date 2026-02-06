# VIREX PRO Android App

Минимальное Android приложение для обработки видео без ограничений по памяти.

## Функции

- 🔐 **Авторизация через Telegram** - безопасный вход через бота
- 📱 **Все шаблоны обработки** - TikTok, Reels, YouTube, Gaming и др.
- 💾 **Без ограничений памяти** - видео до 500MB
- ⭐ **Premium через Telegram** - подписка и оплата через бота
- 🔒 **Watermark-Trap** - защита видео для Premium

## Сборка APK

### Требования
- Android Studio Arctic Fox или новее
- JDK 17
- Gradle 8.2

### Шаги

1. Откройте папку `android` в Android Studio
2. Дождитесь синхронизации Gradle
3. Build → Build Bundle(s) / APK(s) → Build APK(s)
4. APK будет в `app/build/outputs/apk/release/`

### Настройка сервера

1. Измените URL сервера в `PreferencesManager.kt`:
```kotlin
const val DEFAULT_SERVER_URL = "https://your-server.railway.app"
```

2. Убедитесь что `api_server.py` запущен на сервере

## Авторизация

1. Пользователь нажимает "Войти через Telegram"
2. Открывается бот с командой `/start app_auth`
3. Бот генерирует одноразовый код и показывает кнопку
4. Кнопка открывает приложение через deep link `virexpro://auth?user_id=XXX&code=XXX`
5. Приложение авторизуется через API

## API Endpoints

- `GET /api/health` - проверка работоспособности
- `POST /api/auth/deeplink` - авторизация через deep link
- `GET /api/user/subscription` - информация о подписке
- `GET /api/templates` - список шаблонов
- `POST /api/video/process` - обработка видео

## Архитектура

```
app/
├── data/
│   ├── Models.kt           # Data классы
│   └── PreferencesManager.kt  # Хранение настроек
├── network/
│   └── ApiClient.kt        # Retrofit API
├── service/
│   └── VideoProcessService.kt  # Фоновая обработка
├── ui/
│   ├── MainActivity.kt     # Главный экран
│   ├── ProcessActivity.kt  # Обработка видео
│   ├── SubscriptionActivity.kt  # Подписка
│   └── TemplateAdapter.kt  # Адаптер шаблонов
└── VirexApp.kt             # Application класс
```

## Подписание APK

Для релизной сборки создайте keystore:

```bash
keytool -genkey -v -keystore virex-release.jks -keyalg RSA -keysize 2048 -validity 10000 -alias virex
```

Добавьте в `app/build.gradle.kts`:

```kotlin
signingConfigs {
    create("release") {
        storeFile = file("virex-release.jks")
        storePassword = "your_password"
        keyAlias = "virex"
        keyPassword = "your_password"
    }
}
```

## Лицензия

Proprietary - все права защищены.
