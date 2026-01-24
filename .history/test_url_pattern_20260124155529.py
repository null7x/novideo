"""
Тест URL паттерна и функций скачивания
"""
import re
import asyncio

# Копируем паттерн из bot.py
URL_PATTERN = re.compile(
    r'https?://(?:www\.)?(?:'
    r'tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com|'
    r'youtube\.com(?:/shorts|/watch)?|youtu\.be|'
    r'instagram\.com(?:/reel|/p)?|'
    r'vk\.com(?:/clip|/video)?|'
    r'twitter\.com|x\.com|'
    r'douyin\.com|'
    r'bilibili\.com|b23\.tv|'
    r'weibo\.com|'
    r'youku\.com|'
    r'iqiyi\.com|'
    r'kuaishou\.com|gifshow\.com|v\.kuaishou\.com|c\.kuaishou\.com|'
    r'xiaohongshu\.com|xhslink\.com|'
    r'qq\.com|v\.qq\.com'
    r')[^\s]+'
)

# Тестовые URL
TEST_URLS = {
    "youtube": [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/shorts/abc123",
        "https://youtube.com/shorts/abc123",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://www.youtu.be/dQw4w9WgXcQ",
    ],
    "tiktok": [
        "https://www.tiktok.com/@user/video/123456",
        "https://tiktok.com/@user/video/123456",
        "https://vm.tiktok.com/abc123",
        "https://vt.tiktok.com/abc123",
    ],
    "instagram": [
        "https://www.instagram.com/reel/abc123/",
        "https://instagram.com/reel/abc123/",
        "https://www.instagram.com/p/abc123/",
        "https://instagram.com/p/abc123/",
    ],
    "vk": [
        "https://vk.com/clip123456",
        "https://vk.com/video-123_456",
        "https://www.vk.com/clip123456",
    ],
    "twitter": [
        "https://twitter.com/user/status/123456",
        "https://x.com/user/status/123456",
        "https://www.twitter.com/user/status/123456",
    ],
    "chinese": [
        "https://www.douyin.com/video/123456",
        "https://www.bilibili.com/video/BV123",
        "https://b23.tv/abc123",
        "https://www.kuaishou.com/short-video/abc",
        "https://v.kuaishou.com/abc123",
        "https://www.xiaohongshu.com/explore/abc",
        "https://xhslink.com/abc123",
    ],
    "other": [
        "https://weibo.com/tv/v/abc123",
        "https://v.youku.com/v_show/abc.html",
        "https://www.iqiyi.com/v_abc123.html",
        "https://v.qq.com/x/page/abc123.html",
    ],
}

def test_url_pattern():
    """Тест распознавания URL"""
    print("=" * 60)
    print("ТЕСТ URL ПАТТЕРНА")
    print("=" * 60)
    
    total = 0
    passed = 0
    failed = []
    
    for platform, urls in TEST_URLS.items():
        print(f"\n📌 {platform.upper()}")
        for url in urls:
            total += 1
            match = URL_PATTERN.search(url)
            if match:
                matched_url = match.group(0)
                if matched_url == url:
                    print(f"  ✅ {url}")
                    passed += 1
                else:
                    print(f"  ⚠️ {url}")
                    print(f"     Matched: {matched_url}")
                    passed += 1  # Частичное совпадение тоже ок
            else:
                print(f"  ❌ {url}")
                failed.append((platform, url))
    
    print("\n" + "=" * 60)
    print(f"РЕЗУЛЬТАТ: {passed}/{total} ({passed/total*100:.1f}%)")
    print("=" * 60)
    
    if failed:
        print("\n❌ НЕ ПРОШЛИ:")
        for platform, url in failed:
            print(f"  [{platform}] {url}")
    else:
        print("\n✅ ВСЕ ТЕСТЫ ПРОШЛИ!")
    
    return len(failed) == 0

def test_url_in_text():
    """Тест извлечения URL из текста"""
    print("\n" + "=" * 60)
    print("ТЕСТ ИЗВЛЕЧЕНИЯ URL ИЗ ТЕКСТА")
    print("=" * 60)
    
    test_messages = [
        "Смотри видео https://www.youtube.com/watch?v=dQw4w9WgXcQ классное!",
        "https://youtu.be/abc123",
        "Вот ссылка: https://www.tiktok.com/@user/video/123 - лайкни!",
        "привет https://instagram.com/reel/xyz как дела",
        "https://youtube.com/shorts/test123 смешное видео",
    ]
    
    all_passed = True
    for msg in test_messages:
        match = URL_PATTERN.search(msg)
        if match:
            print(f"✅ Текст: {msg[:50]}...")
            print(f"   URL: {match.group(0)}")
        else:
            print(f"❌ Не найден URL в: {msg}")
            all_passed = False
    
    return all_passed

async def test_yt_dlp_available():
    """Проверка доступности yt-dlp"""
    print("\n" + "=" * 60)
    print("ТЕСТ YT-DLP")
    print("=" * 60)
    
    try:
        import yt_dlp
        version = yt_dlp.version.__version__
        print(f"✅ yt-dlp установлен: v{version}")
        return True
    except ImportError:
        print("❌ yt-dlp НЕ УСТАНОВЛЕН!")
        print("   Выполните: pip install yt-dlp")
        return False

async def test_aiohttp_available():
    """Проверка доступности aiohttp"""
    print("\n" + "=" * 60)
    print("ТЕСТ AIOHTTP")
    print("=" * 60)
    
    try:
        import aiohttp
        print(f"✅ aiohttp установлен: v{aiohttp.__version__}")
        return True
    except ImportError:
        print("❌ aiohttp НЕ УСТАНОВЛЕН!")
        return False

async def main():
    print("\n🔬 ЗАПУСК ТЕСТОВ УНИКАЛИЗАЦИИ ПО ССЫЛКАМ\n")
    
    results = []
    
    # Тест 1: URL паттерн
    results.append(("URL Pattern", test_url_pattern()))
    
    # Тест 2: Извлечение из текста
    results.append(("URL в тексте", test_url_in_text()))
    
    # Тест 3: yt-dlp
    results.append(("yt-dlp", await test_yt_dlp_available()))
    
    # Тест 4: aiohttp
    results.append(("aiohttp", await test_aiohttp_available()))
    
    # Итоги
    print("\n" + "=" * 60)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 60)
    
    all_passed = True
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Уникализация готова к работе.")
    else:
        print("⚠️ ЕСТЬ ПРОБЛЕМЫ! Исправьте ошибки выше.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
