"""
Модуль для управления фича-флагами (Feature Flags).

Позволяет переключать функциональность на лету через конфигурационные файлы.
Поддерживает булевы флаги, фильтры по окружению и процентное раскатывание.
"""

from __future__ import annotations

import functools
import hashlib
import inspect
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional, Callable, Union, cast

from .config.core import _PROVIDERS, get_config
from .config.manager import _cm
from .config.utils import find_project_root
from .typing import P, R

logger = logging.getLogger(__name__)


def get_features() -> Dict[str, Any]:
    """
    Загружает и кэширует фича-флаги.
    
    Приоритет источников:
    1. Файл `features.yml` (или `features.yaml`) в корне проекта.
    2. Секция `feature_flags` или `FeatureFlags` в основном `config.yml`.
    
    Returns:
        Словарь с конфигурацией фича-флагов.
    """

    def _do_load() -> Dict[str, Any]:
        if not _cm.paths_initialized:
            _cm.initialize_paths(find_project_root)

        features_data: Dict[str, Any] = {}

        # 1. Попытка загрузки из выделенного файла
        if _cm.features_file_path:
            path = _cm.features_file_path
            ext = Path(path).suffix.lower()
            provider = _PROVIDERS.get(ext)
            if provider:
                try:
                    features_data = provider.load(path)
                    logger.debug("Фича-флаги загружены из выделенного файла: %s", path)
                except Exception as e:
                    logger.warning("Ошибка при загрузке фича-флагов из %s: %s", path, e)

        # 2. Фолбэк на основную конфигурацию, если файл не найден или пуст
        if not features_data:
            config = get_config()
            if isinstance(config, dict):
                # Поддержка различных стилей именования секции
                data = config.get("feature_flags") or config.get("FeatureFlags")
                if data and isinstance(data, dict):
                    logger.debug("Фича-флаги загружены из основной конфигурации (секция feature_flags)")
                    features_data = cast(Dict[str, Any], data)
                else:
                    features_data = {}

        return features_data

    return _cm.load_features_safe(_do_load)


def is_feature_enabled(feature_name: str, context: Optional[Dict[str, Any]] = None) -> bool:
    """
    Проверяет, включена ли указанная фича.

    Args:
        feature_name: Уникальное имя фичи.
        context: Опциональный контекст для вычисления (например, {'user_id': 123}).

    Returns:
        True, если фича включена. False во всех остальных случаях (включая отсутствие фичи).
    """
    features = get_features()

    if feature_name not in features:
        logger.debug("Фича '%s' не найдена в конфигурации. По умолчанию: False", feature_name)
        return False

    config = features[feature_name]

    # 1. Простой булев флаг
    if isinstance(config, bool):
        return config

    # 2. Расширенная конфигурация (словарь)
    if isinstance(config, dict):
        return _evaluate_complex_feature(feature_name, config, context)

    logger.warning("Некорректный формат конфигурации для фичи '%s': %s", feature_name, type(config))
    return False


def _evaluate_complex_feature(feature_name: str, config: Dict[str, Any], context: Optional[Dict[str, Any]]) -> bool:
    """
    Вычисляет состояние фичи на основе сложной конфигурации.
    """
    # 1. Глобальный выключатель (enabled: true/false)
    if not config.get("enabled", True):
        return False

    # 2. Ограничение по окружению (environments: ['production', 'staging'])
    allowed_envs = config.get("environments")
    if allowed_envs:
        current_env = os.getenv("CH_ENV", "development")
        if current_env not in allowed_envs:
            return False

    # 3. Процентное раскатывание (rollout: 50)
    rollout = config.get("rollout")
    if rollout is not None:
        if not context:
            logger.debug("Фича '%s' требует контекст для rollout, но он не передан. Фича выключена.", feature_name)
            return False

        # Ищем ключ для хэширования в контексте
        rollout_key = config.get("rollout_key", "user_id")
        identifier = context.get(rollout_key)

        if identifier is None:
            logger.debug("В контексте не найден ключ '%s' для фичи '%s'. Фича выключена.", rollout_key, feature_name)
            return False

        # Хэшируем идентификатор для детерминированного распределения (0-99)
        hash_val = int(hashlib.md5(f"{feature_name}:{identifier}".encode()).hexdigest(), 16)
        if (hash_val % 100) >= rollout:
            return False

    return True


def require_feature(
        feature_name: str,
        fallback: Optional[Callable[P, R]] = None
) -> Callable[[Callable[P, R]], Callable[P, Union[R, None]]]:
    """
    Декоратор для ограничения доступа к функции на основе фича-флага.

    Если фича включена, вызывается оригинальная функция.
    Если выключена:
        - И задан `fallback`, вызывается он.
        - И `fallback` не задан, возвращается `None`.

    Контекст для вычисления флага может быть передан через именованный аргумент `context`.

    Args:
        feature_name: Имя фичи.
        fallback: Опциональная функция для вызова при выключенной фиче.

    Returns:
        Декоратор.
    """

    def decorator(func: Callable[P, R]) -> Callable[P, Union[R, None]]:
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> Union[R, None]:
                context = cast(Optional[Dict[str, Any]], kwargs.get("context"))
                if is_feature_enabled(feature_name, context):
                    return await func(*args, **kwargs)  # type: ignore[no-any-return]

                if fallback:
                    if inspect.iscoroutinefunction(fallback):
                        return await fallback(*args, **kwargs)  # type: ignore[no-any-return]
                    return fallback(*args, **kwargs)  # type: ignore[return-value]
                return None

            return async_wrapper  # type: ignore[return-value]
        else:
            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> Union[R, None]:
                context = cast(Optional[Dict[str, Any]], kwargs.get("context"))
                if is_feature_enabled(feature_name, context):
                    return func(*args, **kwargs)

                if fallback:
                    return fallback(*args, **kwargs)
                return None

            return sync_wrapper

    return decorator
