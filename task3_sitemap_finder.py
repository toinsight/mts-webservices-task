# -*- coding: utf-8 -*-

# --- БЛОК 1: ИМПОРТ НЕОБХОДИМЫХ БИБЛИОТЕК ---

# Стандартные библиотеки Python
import xml.etree.ElementTree as ET # Встроенная библиотека для разбора (парсинга) XML-файлов.
import gzip                      # Для распаковки .gz архивов, так как sitemap-файлы могут быть сжаты.
from typing import List, Set, Optional # Для указания типов данных (List, Set). Делает код более читаемым.
import sys                       # Для работы с системными параметрами.
import io                        # Для работы с потоками данных.
import os                        # Для работы с операционной системой, в нашем случае — для создания папки.
import json                      # Для работы с форматом JSON.

# Сторонние библиотеки (требуют установки через pip)
import requests                  # Для отправки обычных HTTP-запросов (как в браузере).
import pandas as pd              # Мощная библиотека для анализа данных. Мы используем её для удобного создания Excel-файла.
import undetected_chromedriver as uc # Специальная, модифицированная версия Selenium, которая умеет обходить продвинутые защиты от ботов.
from bs4 import BeautifulSoup    # Очень удобная библиотека для извлечения данных из "грязного" HTML-кода.

# --- БЛОК 2: НАСТРОЙКА ОКРУЖЕНИЯ ---

# Эта часть нужна, чтобы в консоли Windows и других систем корректно отображались русские буквы.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# --- БЛОК 3: ГЛОБАЛЬНЫЕ НАСТРОЙКИ И КОНСТАНТЫ ---

# Словарь с провайдерами и их основными URL. Удобно, чтобы не "зашивать" ссылки прямо в код.
PROVIDER_ROOT_URLS = {"Selectel": "https://docs.selectel.ru/", "Yandex Cloud": "https://cloud.yandex.ru/", "VK Cloud": "https://cloud.vk.com/"}
# Префиксы, по которым мы будем определять, относится ли ссылка к документации.
DOC_PREFIXES = {"Selectel": "https://docs.selectel.ru/", "Yandex Cloud": "https://yandex.cloud/ru/docs/", "VK Cloud": "https://cloud.vk.com/docs/"}
# Техническая настройка для правильного поиска тегов в XML-файлах стандарта sitemap.
XML_NAMESPACE = {'sitemap': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
# Заголовки, которые наш скрипт будет отправлять. `User-Agent` говорит сайту, что мы — обычный браузер Chrome, а не подозрительный скрипт.
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36'}
# Имя папки, куда будут сохраняться итоговые файлы.
OUTPUT_DIR = "analysis_results"


# --- БЛОК 4: ОСНОВНЫЕ ФУНКЦИИ ---

def get_all_urls_from_sitemap_requests(session, sitemap_url: str, visited: Set[str]) -> List[str]:
    """
    Эта функция — наша 'рабочая лошадка'. Она скачивает и парсит sitemap-файлы.
    Используется для "простых" сайтов (Selectel, VK Cloud) и для вложенных файлов Яндекса,
    когда у нас уже есть "ключи" (cookies) в сессии.
    Функция рекурсивная: если она находит sitemap, который ссылается на другие sitemap'ы,
    она вызывает саму себя для каждой новой ссылки.
    """
    # 1. Проверяем, не были ли мы уже на этой странице, чтобы избежать бесконечного цикла.
    if sitemap_url in visited: return []
    print(f"    - (Requests) Обрабатываю: {sitemap_url}"); visited.add(sitemap_url)

    # 2. Делаем GET-запрос с помощью сессии `requests`.
    try:
        r = session.get(sitemap_url, timeout=20); r.raise_for_status(); content = r.content
    except Exception as e:
        print(f"      ❌ Ошибка сети: {e}"); return []

    # 3. Если ответа нет, выходим.
    if not content:
        print(f"      ❌ Пустой ответ от сервера для {sitemap_url}"); return []
        
    # 4. Проверяем, не сжат ли файл (не начинается ли он с 'магических' байтов .gz), и если да — распаковываем.
    if content.startswith(b'\x1f\x8b'): content = gzip.decompress(content)

    # 5. Парсим XML и извлекаем ссылки.
    try:
        root = ET.fromstring(content); urls = []
        # Ищем теги `<sitemap>`, которые указывают на другие sitemap-файлы.
        if root.findall('sitemap:sitemap', XML_NAMESPACE):
            for node in root.findall('sitemap:sitemap', XML_NAMESPACE):
                if (loc := node.find('sitemap:loc', XML_NAMESPACE)) is not None:
                    # Если находим — вызываем себя же (рекурсия).
                    urls.extend(get_all_urls_from_sitemap_requests(session, loc.text, visited))
        # Если это конечный sitemap, ищем теги `<url>` и извлекаем из них ссылки.
        else:
            for node in root.findall('sitemap:url', XML_NAMESPACE):
                if (loc := node.find('sitemap:loc', XML_NAMESPACE)) is not None:
                    urls.append(loc.text)
        return urls
    except ET.ParseError as e:
        print(f"      ❌ Ошибка парсинга XML: {e}"); return []

def process_yandex_cloud_manual() -> List[str]:
    """
    Эта функция — наше финальное решение для Яндекса. Она реализует гибридный подход 'Кража сессии',
    когда человек помогает пройти самую сложную первоначальную защиту, а дальше скрипт работает автоматически.
    """
    print("  - Обнаружена защита высшего уровня. Использую 'Кражу сессии'...")
    driver: Optional[uc.Chrome] = None
    content: Optional[str] = None
    try:
        # --- ЭТАП 1: РУЧНОЙ ПРОРЫВ ---
        # Создаем опции для браузера. Важно, что мы НЕ включаем headless-режим.
        options = uc.ChromeOptions()
        # Запускаем видимый браузер.
        driver = uc.Chrome(options=options)
        driver.set_window_size(1200, 800)
        
        # Выводим подробную инструкцию для пользователя и ждем, пока он нажмет Enter.
        print("\n" + "="*50)
        print("--- ТРЕБУЕТСЯ ВАШЕ ДЕЙСТВИЕ ---")
        print("1. Сейчас откроется окно браузера Chrome.")
        print("2. Вручную откройте в нем страницу:")
        print("   https://yandex.cloud/sitemap_index.xml")
        print("3. Дождитесь, пока на экране появится содержимое XML-файла.")
        print("\n   ВАЖНО: НЕ ЗАКРЫВАЙТЕ ОКНО БРАУЗЕРА САМОСТОЯТЕЛЬНО!\n")
        input("4. После этого вернитесь в эту консоль и нажмите Enter...")
        print("="*50 + "\n")
        print("    - Отлично, продолжаю работу...")

        # --- ЭТАП 2: "КРАЖА СЕССИИ" И ИЗВЛЕЧЕНИЕ XML ---
        # После того как пользователь нажал Enter, мы "крадем" у браузера cookies.
        cookies = driver.get_cookies()
        print("    - Cookies успешно извлечены из браузера.")

        # *** РЕКОМЕНДАЦИЯ №3: Более надежное извлечение XML с обработкой ошибок. ***
        # Мы используем двухэтапный подход для максимальной надежности.
        print("    - Пытаюсь извлечь XML-содержимое со страницы...")

        # Метод 1: Самый надежный. Мы просим браузер выполнить JavaScript-код
        # и вернуть ВЕСЬ видимый текст со страницы. Для XML-файла это и есть сам XML.
        # Этот метод менее зависим от изменений верстки браузера.
        print("      -> Метод 1: Использование JavaScript для получения чистого текста.")
        content = driver.execute_script("return document.body.innerText")

        # Если Метод 1 не сработал (вернул пустую строку) или вернул не XML,
        # пробуем Метод 2 как запасной.
        if not content or not content.strip().startswith('<?xml'):
            print("      -> Метод 1 не дал результата или вернул не XML. Пробую Метод 2.")
            
            # Метод 2: Старый метод. Он ищет специальный тег <div>, в который Chrome "заворачивает" XML.
            # Этот метод более хрупкий, так как ID тега может измениться в будущих версиях Chrome.
            print("      -> Метод 2: Поиск специального контейнера в HTML-коде.")
            page_source = driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            xml_container = soup.find('div', {'id': 'webkit-xml-viewer-source-xml'})
            if xml_container:
                content = xml_container.decode_contents()

        # Финальная проверка: если после двух методов у нас все еще нет контента,
        # значит, произошла серьезная ошибка, и мы прерываем выполнение.
        if not content:
            # Мы специально генерируем исключение, чтобы его поймал наш блок `except` ниже,
            # который покажет пользователю красивое и понятное сообщение.
            raise ValueError("Не удалось извлечь XML-содержимое ни одним из доступных методов.")
        
        print("    - ✅ XML-содержимое успешно извлечено.")

    except Exception as e:
        # Этот блок ловит ЛЮБЫЕ ошибки, которые могли произойти на этапе Selenium,
        # включая нашу собственную ошибку `ValueError`.
        print("\n      ❌ КРИТИЧЕСКАЯ ОШИБКА: Не удалось извлечь XML из HTML-кода страницы.")
        print("      💡 Возможная причина: Версия браузера Chrome обновилась, и внутренний механизм отображения XML изменился.")
        print("      💡 Что проверить: Откройте XML-файл в Chrome вручную, нажмите 'Просмотреть код' и посмотрите, как устроен HTML.")
        print(f"      - Техническая деталь ошибки: {e}")
        return [] # Возвращаем пустой список, чтобы скрипт мог продолжить работу с другими провайдерами.
    finally:
        # Крайне важный блок! Он гарантирует, что браузер будет закрыт, даже если произошла ошибка.
        if driver:
            driver.quit()
            print("    - Браузер Selenium закрыт. Он нам больше не нужен.")

    # --- ЭТАП 3: АВТОМАТИЧЕСКАЯ ОБРАБОТКА (С ИСПОЛЬЗОВАНИЕМ ПОЛУЧЕННЫХ ДАННЫХ) ---
    # Создаем быструю и стабильную сессию `requests`.
    session = requests.Session()
    # "Вооружаем" ее стандартными заголовками.
    session.headers.update(HEADERS)
    # Передаем украденные cookies в нашу сессию. Теперь эта сессия для сайта Яндекса будет выглядеть как "своя".
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'], domain=cookie['domain'])
    print("    - Сессия Requests аутентифицирована. Начинаю быструю обработку.")
    
    # Парсим уже чистый XML и дальше используем нашу быструю функцию `get_all_urls_from_sitemap_requests`
    # с уже "заряженной" аутентифицированной сессией.
    root = ET.fromstring(content)
    total_urls = []
    visited_sitemaps = set()
    sitemap_nodes = root.findall('sitemap:sitemap', XML_NAMESPACE)
    for node in sitemap_nodes:
        if (loc := node.find('sitemap:loc', XML_NAMESPACE)) is not None:
            total_urls.extend(get_all_urls_from_sitemap_requests(session, loc.text, visited_sitemaps))
    return total_urls

# --- БЛОК 5: ОСНОВНОЙ КОД СКРИПТА ---

# Этот блок кода выполняется только тогда, когда скрипт запускается напрямую.
if __name__ == "__main__":
    # Выводим приветственное сообщение.
    print("🚀 Запускаю скрипт для поиска и парсинга sitemap-файлов...\n")

    # Создаем пустые структуры, в которые будем собирать все найденные ссылки для последующего экспорта.
    all_data_for_excel = [] # Список словарей для Excel.
    all_data_for_json = {}  # Словарь, где ключ - провайдер, значение - список ссылок.

    # Проходим по каждому провайдеру из наших настроек.
    for provider, root_url in PROVIDER_ROOT_URLS.items():
        print(f"--- Обрабатываю провайдера: {provider} ---")
        
        # Если это Яндекс, вызываем нашу специальную 'гибридную' функцию.
        if provider == "Yandex Cloud":
            total_urls = process_yandex_cloud_manual()
        # Для всех остальных — используем стандартный, простой метод.
        else:
            print("  - Использую стандартный режим Requests.")
            session = requests.Session(); session.headers.update(HEADERS)
            try:
                # Пытаемся найти sitemap в файле robots.txt - это правильный способ.
                r = requests.get(f"{root_url.rstrip('/')}/robots.txt", timeout=10)
                sitemap_entries = [line.split(': ')[1] for line in r.text.splitlines() if line.lower().startswith('sitemap:')]
                # Если в robots.txt ничего нет, пробуем стандартный sitemap.xml.
                if not sitemap_entries: sitemap_entries.append(f"{root_url.rstrip('/')}/sitemap.xml")
            except Exception:
                # Если и это не сработало, просто используем стандартное имя.
                sitemap_entries = [f"{root_url.rstrip('/')}/sitemap.xml"]
                
            total_urls = []
            visited_sitemaps = set()
            for entry in sitemap_entries:
                total_urls.extend(get_all_urls_from_sitemap_requests(session, entry, visited_sitemaps))
        
        # Фильтруем все найденные ссылки, оставляя только те, что относятся к документации.
        doc_prefix = DOC_PREFIXES[provider]
        doc_urls = sorted(list(set([url for url in total_urls if url.startswith(doc_prefix)])))
        
        # Наполняем наши структуры данных для будущего экспорта.
        all_data_for_json[provider] = doc_urls
        for url in doc_urls:
            all_data_for_excel.append({'provider': provider, 'url': url})

        # Выводим итоговую статистику по каждому провайдеру.
        print(f"\n✅ Найдено всего {len(doc_urls)} уникальных страниц в разделе документации '{doc_prefix}'.")
        if doc_urls:
            print("  Примеры ссылок:"); [print(f"    - {url}") for url in doc_urls[:3]]
        print("-" * 25)

    # --- БЛОК 6: ЭКСПОРТ РЕЗУЛЬТАТОВ ---
    
    # Проверяем, есть ли что сохранять.
    if all_data_for_excel:
        print("\n💾 Сохраняю результаты в файлы...")
        
        # Создаем папку для результатов, если она еще не существует.
        # `exist_ok=True` предотвращает ошибку, если папка уже есть.
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # 1. Сохраняем в JSON.
        json_path = os.path.join(OUTPUT_DIR, 'task3_documentation_urls.json')
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                # `indent=4` делает файл красивым и читаемым.
                # `ensure_ascii=False` позволяет корректно сохранять русские буквы.
                json.dump(all_data_for_json, f, indent=4, ensure_ascii=False)
            print(f"  - ✅ JSON-файл успешно сохранен: {json_path}")
        except Exception as e:
            print(f"  - ❌ Не удалось сохранить JSON-файл: {e}")

        # 2. Сохраняем в Excel.
        excel_path = os.path.join(OUTPUT_DIR, 'task3_documentation_urls.xlsx')
        try:
            # Создаем из нашего списка словарей DataFrame (таблицу pandas).
            df = pd.DataFrame(all_data_for_excel)
            # Одной командой `to_excel` сохраняем его в файл.
            # `index=False` убирает ненужную колонку с индексами строк.
            df.to_excel(excel_path, index=False)
            print(f"  - ✅ Excel-файл успешно сохранен: {excel_path}")
        except Exception as e:
            print(f"  - ❌ Не удалось сохранить Excel-файл: {e}")

    # Финальное сообщение.
    print("\n🎉 Все задачи выполнены.")