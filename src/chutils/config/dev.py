from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from chutils.typing import JSONDict
from .core import get_config
from .manager import _cm
from .utils import load_pyproject_toml, find_project_root

DEFAULT_AI_LINT_CONFIG: JSONDict = {
    "strict": False,
    "ignore": [".git", ".venv", "__pycache__", "build", "dist"],
    "rules": [],
    "custom_rules_path": None,
    "soft_mode": False
}


def parse_chutils_ignore(base_dir: str) -> list[str]:
    """
    Парсит файл .chutilsignore и возвращает список шаблонов для игнорирования.
    """
    ignore_path = Path(base_dir) / ".chutilsignore"
    if not ignore_path.exists():
        return []

    patterns: list[str] = []
    try:
        with open(ignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    patterns.append(line)
    except Exception:
        pass
    return patterns


def _get_env_config() -> JSONDict:
    """
    Извлекает настройки ai-lint из переменных окружения (CH_DEV_AILINT_...).
    """
    env_config: JSONDict = {}
    for key, val in os.environ.items():
        if key.startswith("CH_DEV_AILINT_"):
            config_key = key[14:].lower()
            if val.lower() == "true":
                env_config[config_key] = True
            elif val.lower() == "false":
                env_config[config_key] = False
            elif val.startswith("[") and val.endswith("]"):
                env_config[config_key] = [item.strip(" '\"") for item in val[1:-1].split(",") if item.strip()]
            else:
                try:
                    if "." in val:
                        env_config[config_key] = float(val)
                    else:
                        env_config[config_key] = int(val)
                except ValueError:
                    env_config[config_key] = val
    return env_config


def load_ai_lint_config(cli_args: Optional[JSONDict] = None) -> JSONDict:
    """
    Загружает и объединяет конфигурацию для ai-lint из всех источников.

    Приоритет источников (от наивысшего к низшему):
    1. CLI флаги (cli_args)
    2. Переменные окружения (CH_DEV_AILINT_...)
    3. Локальные yml файлы (секция Dev.AI-Lint)
    4. pyproject.toml (секция [tool.chutils.ai-lint])
    5. Значения по умолчанию
    """
    if not _cm.paths_initialized:
        _cm.initialize_paths(find_project_root)
    base_dir = _cm.base_dir or os.getcwd()

    # 5. Defaults
    merged_config: JSONDict = DEFAULT_AI_LINT_CONFIG.copy()

    # 4. pyproject.toml
    pyproject_path = Path(base_dir) / "pyproject.toml"
    if pyproject_path.exists():
        pyproject_config = load_pyproject_toml(str(pyproject_path))
        for k, v in pyproject_config.items():
            merged_config[k] = v

    # 3. config.yml (Dev.AI-Lint)
    try:
        main_config = get_config()
        if isinstance(main_config, dict):
            dev_section = main_config.get("Dev", {})
            if isinstance(dev_section, dict):
                ai_lint_config = dev_section.get("AI-Lint", {})
                if isinstance(ai_lint_config, dict):
                    for k, v in ai_lint_config.items():
                        merged_config[k] = v
    except Exception:
        pass

    # 2. Env
    env_config = _get_env_config()
    for k, v in env_config.items():
        merged_config[k] = v

    # 1. CLI
    if cli_args:
        cli_ignore = cli_args.get("ignore")
        if cli_ignore is not None:
            cli_ignore_list = cli_ignore if isinstance(cli_ignore, list) else [cli_ignore]
            current_ignore = merged_config.get("ignore", [])
            current_list = current_ignore if isinstance(current_ignore, list) else [current_ignore]

            result = list(current_list)
            for item in cli_ignore_list:
                if str(item) not in result:
                    result.append(str(item))
            merged_config["ignore"] = result

        for k, v in cli_args.items():
            if v is not None and k != "ignore":
                merged_config[k] = v

    # Интегрируем .chutilsignore в список ignore
    ignore_patterns = parse_chutils_ignore(base_dir)
    if ignore_patterns:
        # Объединяем, убирая дубликаты
        current_ignore = merged_config.get("ignore", [])
        if isinstance(current_ignore, list):
            # Делаем список строк
            str_ignore = [str(item) for item in current_ignore]
            for pat in ignore_patterns:
                if pat not in str_ignore:
                    str_ignore.append(pat)
            merged_config["ignore"] = str_ignore
        else:
            merged_config["ignore"] = ignore_patterns

    return merged_config
