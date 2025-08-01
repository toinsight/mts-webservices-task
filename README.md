# Анализ документации и парсинг сайтов облачных провайдеров

Этот проект представляет собой набор из трех Python-скриптов, выполненных в рамках тестового задания для MTS Web Services. Каждый скрипт решает одну из трех поставленных задач, демонстрируя различные подходы к сбору и анализу веб-данных: от детального анализа конкретных страниц до стратегических решений по работе с большими массивами информации и обходу сложных защит от ботов.

---

## Предварительные требования

Перед установкой убедитесь, что на вашем компьютере установлены:
- **Python 3.10+** (скрипты разрабатывались и тестировались на Python 3.12)
- **PIP** (стандартный менеджер пакетов Python, обычно идет в комплекте)
- **Google Chrome** (требуется для работы скрипта `task3_sitemap_finder.py` для обхода защиты сайта Yandex Cloud)

---

## Установка

1. **Клонируйте или скачайте репозиторий:**
    ```bash
    git clone <адрес_репозитория>
    cd <папка_репозитория>
    ```
2. **Создайте и активируйте виртуальное окружение (рекомендуется):**
    - На Windows:
        ```bash
        python -m venv venv
        .\venv\Scripts\activate
        ```
    - На macOS / Linux:
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
3. **Установите все необходимые зависимости одной командой:**
    ```bash
    pip install -r requirements.txt
    ```
    > Эта команда автоматически установит `requests`, `pandas`, `beautifulsoup4`, `pymorphy2`, `openpyxl` и `undetected-chromedriver`.

---

## Структура проекта

```
.
├── analysis_results/           # Папка для всех итоговых файлов (JSON, Excel)
├── downloaded_pages/           # Папка для сохранения HTML-страниц (создается task1)
├── task1_downloader.py         # Задача 1: Анализатор страниц документации
├── task2_search_simulation.py  # Задача 2: Симуляция быстрого поиска
├── task3_sitemap_finder.py     # Задача 3: Парсер Sitemap-файлов
├── requirements.txt            # Список зависимостей проекта
└── README.md                   # Этот файл
```

---

## Описание и запуск скриптов

### Задача 1: `task1_downloader.py` — Анализатор страниц документации

#### Назначение
Этот скрипт выполняет глубокий точечный анализ трех заданных страниц документации Selectel. Он не просто скачивает страницы, а извлекает из них набор полезных для технического эксперта метрик.

#### Ключевые особенности
- **Глубокий анализ:** Собирает заголовок, описание, дату последнего обновления, количество таблиц, а также анализирует блоки кода (подсчет, определение языка).
- **Поиск по ключевым словам:** Ищет упоминания ключевых технологий (`API`, `Terraform`, `Kubernetes` и т.д.) и подсчитывает их частоту.
- **Проверка ссылок:** Находит все ссылки на странице, классифицирует их на внутренние/внешние и, что самое важное, **проверяет каждую на работоспособность ("битые" ссылки)**.
- **Оптимизация производительности:** Проверка ссылок реализована в **многопоточном режиме** с использованием `ThreadPoolExecutor` для значительного ускорения процесса. Повторные проверки одного и того же URL кэшируются.
- **Двойной экспорт:** Сохраняет результаты в двух форматах: `JSON` для машинной обработки и `Excel` для удобного анализа человеком.

#### Запуск
```bash
python task1_downloader.py
```

**Результат:**
- Создаст папку `downloaded_pages/` с сохраненным HTML-кодом каждой страницы в отдельном .txt файле.
- Создаст папку `analysis_results/` и поместит в нее файлы `task1_analysis_results.json` и `task1_analysis_results.xlsx`.

---

### Задача 2: `task2_search_simulation.py` — Симуляция быстрого поиска

#### Назначение
Этот скрипт не решает прикладную задачу, а демонстрирует концептуально верный подход к проблеме быстрого поиска информации в большом массиве данных. Вместо неэффективного прямого перебора он симулирует создание и использование обратного поискового индекса — технологии, лежащей в основе всех современных поисковых систем.

#### Ключевые особенности
- **Обратный индекс:** Строит структуру данных, где ключом является слово (лемма), а значением — информация о документах, в которых оно встречается.
- **Лемматизация:** Использует библиотеку `pymorphy2` для приведения слов русского языка к их нормальной форме (например, "серверы", "сервером" -> "сервер"). Это кардинально повышает качество поиска.
- **Фильтрация стоп-слов:** Игнорирует бессмысленные для поиска слова ("и", "в", "на"), что уменьшает размер индекса и повышает релевантность.
- **Ранжирование результатов:** Реализован простейший алгоритм ранжирования на основе частоты встречаемости слов из запроса в документе.
- **Наглядная демонстрация:** Выводит в консоль время, затраченное на поиск (доли миллисекунды), доказывая эффективность подхода.

#### Запуск
```bash
python task2_search_simulation.py
```

**Результат:**
- Выведет в консоль этапы построения индекса и результаты тестовых поисковых запросов.
- Сохранит построенный индекс в файлы `analysis_results/task2_inverted_index.json` и `analysis_results/task2_inverted_index.xlsx`.

---

### Задача 3: `task3_sitemap_finder.py` — Парсер Sitemap-файлов

#### Назначение
Самый сложный скрипт, который находит и полностью парсит файлы sitemap.xml для трех облачных провайдеров (Selectel, Yandex Cloud, VK Cloud), чтобы собрать полный список URL-адресов их документации.

#### Ключевые особенности и стратегия
- **Стандартный подход:** Для Selectel и VK Cloud используется правильная последовательность: robots.txt -> sitemap.xml.
- **Обход продвинутой защиты:** Сайт Yandex Cloud использует сложные системы защиты от ботов. Для его обработки реализован специальный режим "Абсолютный контроль":
    - Скрипт запускает `undetected-chromedriver` — усиленную версию браузера, способную обходить защиты.
    - Пользователю предлагается один раз вручную открыть в этом браузере страницу sitemap, чтобы пройти первоначальную проверку на "человечность" и "прогреть" сессию.
    - После этого скрипт берет управление на себя и для всех последующих переходов по вложенным sitemap-файлам использует прямой доступ к исходному коду страницы (`driver.page_source`). Этот метод гарантированно получает сырой XML, минуя любые встроенные в браузер "просмотрщики", которые мешают парсингу.
- **Надежность:** Скрипт умеет работать с индексными sitemap-файлами (которые ссылаются на другие) и автоматически распаковывает сжатые (.gz) архивы.

#### Запуск
```bash
python task3_sitemap_finder.py
```

> **Внимание:** При обработке Yandex Cloud скрипт остановится и будет ждать вашего ручного действия в открывшемся окне браузера. Следуйте инструкциям в консоли.

**Результат:**
- Выведет в консоль статистику по найденным URL для каждого провайдера.
- Сохранит итоговые списки URL в файлы `analysis_results/task3_documentation_urls.json` и `analysis_results/task3_documentation_urls.xlsx`.

---

## Важные ограничения

- Из-за сложной защиты Yandex Cloud скрипт не является полностью автоматическим. Он требует ручного вмешательства на одном из этапов.
- Для работы скрипта необходимо наличие установленного браузера Google Chrome.
