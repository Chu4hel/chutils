from __future__ import annotations


def generate_workflow_yaml(
        python_versions: list[str],
        with_pytest: bool,
        with_mypy: bool,
        with_ruff: bool,
        with_ai_lint: bool,
) -> str:
    """Генерирует валидный YAML-конфиг для GitHub Actions на основе setup-uv.

    Args:
        python_versions: Список версий Python для матрицы тестирования.
        with_pytest: Запускать ли тесты с pytest.
        with_mypy: Запускать ли статический анализ типов с mypy.
        with_ruff: Запускать ли линтинг кода с ruff.
        with_ai_lint: Запускать ли аудит готовности к AI с chutils dev ai-lint.

    Returns:
        Строка с содержимым YAML-файла.
    """
    versions_str = ", ".join(f'"{v}"' for v in python_versions)

    yaml_lines = [
        "name: CI",
        "",
        "on:",
        "  push:",
        "    branches: [ main, master ]",
        "  pull_request:",
        "    branches: [ main, master ]",
        "",
        "jobs:",
    ]

    yaml_lines.extend([
        "  ci:",
        "    runs-on: ubuntu-latest",
        "    strategy:",
        "      matrix:",
        f"        python-version: [{versions_str}]",
        "    steps:",
        "      - name: Checkout code",
        "        uses: actions/checkout@v4",
        "",
        "      - name: Install uv",
        "        uses: astral-sh/setup-uv@v3",
        "        with:",
        "          enable-cache: true",
        "          cache-dependency-glob: \"uv.lock\"",
        "",
        "      - name: Set up Python ${{ matrix.python-version }}",
        "        run: uv python install ${{ matrix.python-version }}",
        "",
        "      - name: Install dependencies",
        "        run: uv sync",
    ])

    if with_ruff:
        yaml_lines.extend([
            "",
            "      - name: Run Ruff check",
            "        run: uv run ruff check .",
            "",
            "      - name: Run Ruff format check",
            "        run: uv run ruff format --check .",
        ])

    if with_mypy:
        yaml_lines.extend([
            "",
            "      - name: Run Mypy",
            "        run: uv run mypy .",
        ])

    if with_ai_lint:
        yaml_lines.extend([
            "",
            "      - name: Run chutils dev ai-lint",
            "        run: uv run chutils dev ai-lint",
        ])

    if with_pytest:
        yaml_lines.extend([
            "",
            "      - name: Run tests with pytest",
            "        run: uv run pytest",
        ])

    return "\n".join(yaml_lines) + "\n"
