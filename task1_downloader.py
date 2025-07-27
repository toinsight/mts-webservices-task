# -*- coding: utf-8 -*-

# --- Импорт необходимых библиотек ---

# `requests` - для отправки HTTP-запросов (скачивания веб-страниц).
import requests
# `os` - для работы с операционной системой (например, для создания папок и путей к файлам).
import os
# `re` - для работы с регулярными выражениями (для сложного поиска в тексте).
import re
# `json` - для работы с форматом данных JSON (для сохранения результатов).
import json
# `pandas` - мощная библиотека для анализа данных, используется для создания и сохранения Excel-файла.
import pandas as pd
# `BeautifulSoup` - главный инструмент для парсинга HTML-кода (извлечения данных из веб-страниц).
# `Tag` - используется для безопасной проверки типов HTML-тегов.
from bs4 import BeautifulSoup, Tag
# `urljoin`, `urlparse` - для удобной и корректной работы с URL-адресами.
from urllib.parse import urljoin, urlparse
# `Counter` - удобный класс для подсчета одинаковых элементов (например, языков программирования).
from collections import Counter
# `sys`, `io` - для настройки стандартного вывода, чтобы избежать проблем с кодировкой в некоторых терминалах (особенно в Windows).
import sys
import io
# `concurrent.futures` - библиотека для параллельного выполнения задач.
# `ThreadPoolExecutor` идеально подходит для ускорения I/O-bound операций, таких как сетевые запросы.
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Настройка кодировки для вывода в терминал ---
# Эта секция гарантирует, что русские символы будут корректно отображаться в консоли.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# --- 1. ГЛОБАЛЬНЫЕ НАСТРОЙКИ СКРИПТА ---

# Список URL-адресов, которые мы будем анализировать.
URLS_TO_ANALYZE = [
    "https://docs.selectel.ru/cloud-servers/create/create-server/",
    "https://docs.selectel.ru/managed-kubernetes/clusters/logs/",
    "https://docs.selectel.ru/object-storage/quickstart/"
]
# Название папки, куда будут сохраняться скачанные HTML-страницы (для архива).
OUTPUT_DIR = "downloaded_pages"
# Название папки, куда будут сохраняться итоговые файлы с результатами анализа.
ANALYSIS_RESULTS_DIR = "analysis_results"
# *** ИЗМЕНЕНИЕ: Скорректированы имена файлов ***
# Полный путь к JSON-файлу. os.path.join используется для создания корректного пути независимо от ОС (Windows/Linux/macOS).
JSON_RESULTS_FILE = os.path.join(ANALYSIS_RESULTS_DIR, "task1_analysis_results.json")
# Полный путь к Excel-файлу.
EXCEL_RESULTS_FILE = os.path.join(ANALYSIS_RESULTS_DIR, "task1_analysis_results.xlsx")
# Список ключевых технологий и инструментов, которые мы будем искать на страницах.
TOOLS_KEYWORDS = ['API', 'Terraform', 'CLI', 'Ansible', 'Kubernetes', 'Docker', 'SDK']
# Заголовки HTTP-запроса. `User-Agent` имитирует запрос из браузера, что повышает шансы на успешное скачивание.
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}
# Максимальное количество потоков для параллельной проверки ссылок.
MAX_WORKERS_FOR_LINKS = 10


def print_report(result: dict):
    """
    Функция для красивой печати результатов анализа в терминал.
    Принимает на вход словарь с результатами для одной страницы.
    """
    # Проверяем, был ли анализ успешным.
    if result["status"] == "Success":
        # Печатаем основную информацию о странице.
        print(f"ℹ️ Title: {result['title']}")
        print(f"ℹ️ Description: {result['description']}")
        print(f"✅ Дата последнего обновления: {result['last_update_date']}")
        print(f"✅ Найдено таблиц с параметрами: {result['tables_count']}")

        # Печатаем информацию о блоках кода.
        code_blocks_count = result['code_blocks_count']
        if code_blocks_count > 0:
            # Формируем красивую строку со списком языков и их количеством.
            lang_summary = ", ".join([f"{lang}: {count}" for lang, count in result['code_languages'].items()])
            print(f"✅ Найдено блоков с кодом: {code_blocks_count} ({lang_summary})")
        else:
            print(f"✅ Найдено блоков с кодом: 0")

        # Печатаем информацию о найденных инструментах.
        found_tools = result['found_tools']
        if found_tools:
            # Формируем строку со списком инструментов и количеством их упоминаний.
            tools_summary = ", ".join([f"{tool}: {count}" for tool, count in found_tools.items()])
            print(f"✅ Упомянутые инструменты: {tools_summary}")
        else:
            print("✅ Ключевые инструменты не найдены.")

        # Печатаем сводку по ссылкам.
        links = result['links_summary']
        print(f"✅ Количество ссылок: {links['total_links']} (Внутренние: {links['internal_links']}, Внешние: {links['external_links']})")

        # Если есть битые ссылки, выводим предупреждение.
        if links['broken_links'] > 0:
            print(f"⚠️ Найдено битых ссылок: {links['broken_links']}")
        else:
            print(f"✅ Битые ссылки не обнаружены.")
    else:
        # Если анализ провалился, печатаем сообщение об ошибке.
        print(f"❌ ОШИБКА: Анализ не удался. Причина: {result.get('error_message', 'Неизвестная ошибка')}")


def check_link(url: str) -> tuple[str, bool]:
    """
    Изолированная функция для проверки ОДНОЙ ссылки.
    Отправляет HEAD-запрос, чтобы получить только заголовки, что быстрее, чем скачивать всё тело ответа.
    Возвращает кортеж (URL, is_broken), где is_broken - True, если ссылка не работает.
    """
    try:
        # HEAD-запрос эффективнее для проверки доступности, так как не загружает тело страницы.
        # allow_redirects=True позволяет корректно обрабатывать редиректы.
        response = requests.head(url, headers=HEADERS, allow_redirects=True, timeout=5)
        # Считаем ссылку "битой", если код ответа 400 или выше (ошибки клиента или сервера).
        if response.status_code >= 400:
            return url, True
        return url, False
    except requests.RequestException:
        # Если произошла любая сетевая ошибка (тайм-аут, нет DNS), считаем ссылку "битой".
        return url, True


def analyze_documentation_page(url: str, link_status_cache: dict) -> dict:
    """
    Основная функция, которая выполняет полный анализ одной страницы
    и ВОЗВРАЩАЕТ результат в виде СЛОВАРЯ.

    :param url: URL-адрес страницы для анализа.
    :param link_status_cache: Словарь для кэширования статусов ссылок (url -> is_broken),
                              чтобы не проверять одну и ту же ссылку много раз.
    """
    # Выводим заголовок, чтобы отделить анализ разных страниц в консоли.
    print(f"\n{'='*20} Анализ страницы: {url} {'='*20}")
    # Создаем словарь для хранения результатов. Изначально статус "Failed".
    page_result = {"url": url, "status": "Failed"}

    # Блок try...except для обработки возможных ошибок (например, сайт недоступен).
    try:
        # Отправляем GET-запрос на URL и скачиваем страницу.
        response = requests.get(url, headers=HEADERS, timeout=15)
        # Явно указываем кодировку ответа, чтобы избежать проблем с русскими буквами.
        response.encoding = 'utf-8'
        # Если сервер вернул код ошибки (4xx или 5xx), эта строка вызовет исключение.
        response.raise_for_status()

        # Сохраняем "сырой" HTML-код страницы в текстовый файл.
        filename = re.sub(r'[^a-zA-Z0-9]', '_', url) + ".txt"
        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(response.text)

        # Создаем объект BeautifulSoup из HTML-кода для удобного парсинга.
        soup = BeautifulSoup(response.text, 'html.parser')
        # Извлекаем весь текст со страницы и приводим его к нижнему регистру для удобства поиска.
        page_text_content = soup.get_text().lower()

        # --- АНАЛИЗ (сохраняем все в словарь `page_result`) ---
        page_result["status"] = "Success"  # Меняем статус на "успешно".
        page_result["title"] = soup.title.string.strip() if soup.title else "N/A"

        # Безопасно извлекаем мета-описание, проверяя, что тег найден и у него есть нужный атрибут.
        description_tag = soup.find('meta', attrs={'name': 'description'})
        if isinstance(description_tag, Tag) and description_tag.has_attr('content'):
            page_result["description"] = description_tag['content'].strip()
        else:
            page_result["description"] = "N/A"

        # ***РЕКОМЕНДАЦИЯ №2: Добавлен комментарий о "хрупкости" селектора.***
        # Ищем дату обновления по специфическому CSS-классу.
        # ВАЖНО: Этот селектор зависит от текущей верстки сайта Selectel.
        # Если верстка изменится, этот код может перестать работать и потребует обновления.
        update_date_tag = soup.find('div', class_='doc-body__last-update')
        page_result["last_update_date"] = update_date_tag.get_text(strip=True) if update_date_tag else "N/A"

        # Считаем количество тегов <table> на странице.
        page_result["tables_count"] = len(soup.find_all('table'))

        # Анализируем блоки с кодом.
        code_blocks = soup.find_all('pre')
        language_counter = Counter()
        for block in code_blocks:
            code_tag = block.find('code')
            lang = "unknown"
            if code_tag and code_tag.get('class'):
                for css_class in code_tag['class']:
                    if css_class.startswith('language-'):
                        lang = css_class.replace('language-', '')
                        break
            language_counter[lang] += 1
        page_result["code_blocks_count"] = len(code_blocks)
        page_result["code_languages"] = dict(language_counter)

        # Ищем ключевые инструменты и считаем их упоминания.
        found_tools_with_counts = {}
        for tool in TOOLS_KEYWORDS:
            # `\b` - граница слова, чтобы найти точное совпадение (например, "api", а не "terapi").
            matches = re.findall(r'\b' + re.escape(tool.lower()) + r'\b', page_text_content)
            if matches:
                found_tools_with_counts[tool] = len(matches)
        page_result["found_tools"] = found_tools_with_counts

        # *** РЕКОМЕНДАЦИЯ №1 и №3: Многопоточная проверка ссылок с кэшированием ***
        # 1. Сбор и подготовка всех ссылок
        all_links_on_page = soup.find_all('a', href=True)
        internal_links, external_links = 0, 0
        base_url = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

        # Собираем в `set`, чтобы сразу отсеять дубликаты ссылок на этой странице.
        unique_urls_to_check = set()
        for link in all_links_on_page:
            href = link['href']
            # Пропускаем "якорные" ссылки (ведущие на эту же страницу).
            if href.startswith('#') or not href.strip():
                continue

            # Превращаем относительные ссылки (например, "/page.html") в абсолютные.
            absolute_url = urljoin(base_url, href)
            unique_urls_to_check.add(absolute_url)

            # Классифицируем ссылку как внутреннюю или внешнюю.
            if urlparse(absolute_url).netloc == urlparse(base_url).netloc:
                internal_links += 1
            else:
                external_links += 1

        # 2. Фильтрация ссылок, которые уже были проверены ранее (использование кэша)
        # Оставляем только те ссылки, статуса которых еще нет в нашем глобальном кэше.
        new_urls_to_check = [u for u in unique_urls_to_check if u not in link_status_cache]

        # 3. Параллельная проверка новых ссылок
        # Создаем пул потоков для отправки запросов. `with` гарантирует, что потоки будут корректно завершены.
        if new_urls_to_check:
            print(f"  -> Начинаю проверку {len(new_urls_to_check)} новых уникальных ссылок в {MAX_WORKERS_FOR_LINKS} потоков...")
            with ThreadPoolExecutor(max_workers=MAX_WORKERS_FOR_LINKS) as executor:
                # `executor.map` асинхронно применяет функцию `check_link` к каждому элементу `new_urls_to_check`.
                # Это неблокирующая операция, результаты будут появляться по мере их готовности.
                future_to_url = {executor.submit(check_link, u): u for u in new_urls_to_check}
                for future in as_completed(future_to_url):
                    u, is_broken = future.result()
                    # Обновляем наш кэш результатами, чтобы не проверять эту ссылку в будущем.
                    link_status_cache[u] = is_broken
            print("  -> Проверка ссылок завершена.")

        # 4. Подсчет битых ссылок на ТЕКУЩЕЙ странице, используя обновленный кэш
        broken_links_count = 0
        for u in unique_urls_to_check:
            if link_status_cache.get(u, False): # Если ссылка в кэше и она 'битая'
                broken_links_count += 1

        # Сохраняем итоговую сводку по ссылкам в наш словарь результатов.
        page_result["links_summary"] = {
            "total_links": len(all_links_on_page),
            "internal_links": internal_links,
            "external_links": external_links,
            "broken_links": broken_links_count
        }

    # Если во время выполнения блока try произошла ошибка, мы "ловим" ее здесь.
    except requests.exceptions.RequestException as e:
        page_result["error_message"] = str(e)
    except Exception as e:
        page_result["error_message"] = str(e)

    # --- ВЫВОД РЕЗУЛЬТАТОВ В ТЕРМИНАЛ ---
    print_report(page_result)
    print(f"{'='*25} Конец анализа {'='*25}")

    # Возвращаем словарь с результатами для последующей обработки.
    return page_result


# --- ОСНОВНОЙ БЛОК ИСПОЛНЕНИЯ СКРИПТА ---
# `if __name__ == "__main__":` означает, что этот код выполнится только тогда,
# когда мы запускаем этот файл напрямую, а не импортируем его в другой скрипт.
if __name__ == "__main__":
    print("🚀 Запускаю скрипт для анализа документации...")

    # Создаем папки для скачанных страниц и результатов, если их не существует.
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
    if not os.path.exists(ANALYSIS_RESULTS_DIR):
        os.makedirs(ANALYSIS_RESULTS_DIR)

    # *** РЕКОМЕНДАЦИЯ №3: Создаем кэш для статусов ссылок ***
    # Этот словарь будет передаваться в функцию анализа и наполняться на каждой итерации.
    # Ключ - URL, значение - True (битая) или False (рабочая).
    # Это предотвратит повторные сетевые запросы к одной и той же ссылке, если она встретится на разных страницах.
    master_link_cache = {}

    # Создаем пустой список, в который будем собирать результаты по каждой странице.
    all_results = []
    # Запускаем анализ для каждой ссылки из нашего списка.
    for url in URLS_TO_ANALYZE:
        # Передаем кэш в функцию анализа.
        result = analyze_documentation_page(url, master_link_cache)
        all_results.append(result)

    print(f"\n📊 Всего проверено и закэшировано {len(master_link_cache)} уникальных ссылок.")

    # --- СОХРАНЕНИЕ РЕЗУЛЬТАТОВ В ФАЙЛЫ ---
    # Сохраняем итоговый список в JSON-файл.
    with open(JSON_RESULTS_FILE, 'w', encoding='utf-8') as f:
        # `indent=2` делает файл красиво отформатированным и читаемым.
        # `ensure_ascii=False` позволяет корректно сохранять русские буквы.
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Результаты анализа сохранены в JSON файл: {JSON_RESULTS_FILE}")

    # Создаем таблицу DataFrame из списка результатов. `json_normalize` отлично "расплющивает" вложенные словари.
    df = pd.json_normalize(all_results, sep='_')
    # Переименовываем некоторые столбцы для большей наглядности в Excel.
    df.rename(columns={
        'links_summary_total_links': 'Total Links',
        'links_summary_internal_links': 'Internal Links',
        'links_summary_external_links': 'External Links',
        'links_summary_broken_links': 'Broken Links'
    }, inplace=True)
    # Сохраняем таблицу в Excel-файл. `index=False` убирает лишний столбец с индексами.
    df.to_excel(EXCEL_RESULTS_FILE, index=False, engine='openpyxl')
    print(f"✅ Результаты анализа сохранены в Excel файл: {EXCEL_RESULTS_FILE}")

    print("\n🎉 Все задачи выполнены.")