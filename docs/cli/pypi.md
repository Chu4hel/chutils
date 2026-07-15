# Проверка доступа к PyPI и зеркалам (`chutils pypi`)

Команда `chutils pypi` (или `chutils pypi check`) позволяет разработчику проверить доступность и измерить
производительность (время отклика и скорость скачивания) официального репозитория PyPI, а также популярных публичных и
кастомных зеркал.

На основе результатов замеров команда выдает рекомендацию по настройке наиболее оптимального зеркала.

---

## Синтаксис

```bash
chutils pypi [check] [-h] [-m MIRRORS] [--json] [--package PACKAGE]
```

Если подкоманда не указана явно, по умолчанию запускается действие `check`.

### Опции команды

* `-m, --mirrors` — Список дополнительных кастомных зеркал для проверки, разделенных запятыми.
* `--json` — Выводить результаты проверки строго в формате JSON в поток `stdout` (информационные сообщения и логи при
  этом пишутся в `stderr`).
* `--package` — Имя пакета, используемого для теста скорости загрузки (по умолчанию: `six`).

---

## Проверяемые зеркала по умолчанию

По умолчанию утилита проверяет следующие репозитории:

1. **Официальный PyPI:** `https://pypi.org/simple/`
2. **Яндекс:** `https://mirror.yandex.ru/pypi/simple/`
3. **Aliyun (Alibaba Cloud):** `https://mirrors.aliyun.com/pypi/simple/`
4. **GitVerse:** `https://pypi-mirror.gitverse.ru/simple/`
5. **Depkit:** `https://pypi.depkit.ru/simple/`
6. **Tsinghua TUNA:** `https://pypi.tuna.tsinghua.edu.cn/simple/`

> [!NOTE]
> Утилита автоматически считывает текущий настроенный `index-url` в вашей системе (из переменной окружения
`PIP_INDEX_URL` или глобальных/пользовательских конфигураций `pip`) и добавляет его в список проверок для корректного
> сравнения производительности.

---

## Примеры использования

### 1. Быстрая интерактивная проверка с выводом таблицы

Запуск базовой проверки всех зеркал по умолчанию:

```bash
chutils pypi check
```

**Пример вывода:**

```
[INFO] Получение текущей конфигурации pip...
[INFO] Текущий index-url: https://pypi.org/simple/
[INFO] Начинаем проверку 6 зеркал (пакет: six)...
 Проверка https://pypi.org/simple/...
 Проверка https://mirror.yandex.ru/pypi/simple/...
 Проверка https://mirrors.aliyun.com/pypi/simple/...
 Проверка https://pypi-mirror.gitverse.ru/simple/...
 Проверка https://pypi.depkit.ru/simple/...
 Проверка https://pypi.tuna.tsinghua.edu.cn/simple/...

                      Результаты проверки зеркал PyPI
┌────────────────────────────┬───────────┬───────────┬─────────────────┐
│ Зеркало (URL)              │ Статус    │ Пинг (мс) │ Скорость (КБ/с) │
├────────────────────────────┼───────────┼───────────┼─────────────────┤
│ https://pypi.org/simple/   │ Доступен  │     846.2 │            12.0 │
│ https://mirror.yandex.ru/… │ Ошибка    │         - │               - │
│ https://mirrors.aliyun.co… │ Доступен  │     890.3 │            11.2 │
│ https://pypi-mirror.gitve… │ Доступен  │    1106.3 │             7.5 │
│ https://pypi.depkit.ru/si… │ Ошибка    │         - │               - │
│ https://pypi.tuna.tsinghu… │ Доступен  │    1677.9 │             5.3 │
└────────────────────────────┴───────────┴───────────┴─────────────────┘

Рекомендация:
Ваше текущее зеркало является оптимальным или разница в производительности незначительна.
```

### 2. Запуск проверки с кастомными зеркалами

Вы можете добавить собственные корпоративные или альтернативные зеркала для замера:

```bash
chutils pypi check -m "https://my-internal-nexus.local/repository/pypi-all/simple/"
```

### 3. Автоматизированный запуск с выводом в формате JSON

Для интеграции с CI/CD или скриптами автоматизации используйте флаг `--json`:

```bash
chutils pypi check --json
```

**Вывод (stdout):**

```json
{
  "current_index_url": "https://pypi.org/simple/",
  "recommended_index_url": "https://mirrors.aliyun.com/pypi/simple/",
  "results": [
    {
      "url": "https://pypi.org/simple/",
      "available": true,
      "latency_ms": 846.2,
      "download_speed_kbs": 12.0,
      "error": null,
      "checked_file_url": "https://files.pythonhosted.org/packages/.../six-1.5.0.whl"
    },
    ...
  ]
}
```
