[Русская версия](docs/README_RU.md)

# chutils: Stop the Routine!

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI version](https://badge.fury.io/py/chutils.svg)](https://badge.fury.io/py/chutils)
[![Documentation](https://img.shields.io/badge/documentation-read-brightgreen)](https://Chu4hel.github.io/chutils/)

**chutils** is a set of simple utilities for Python designed to eliminate the repetitive setup of configuration,
logging, and secrets in your projects.

Start a new project and focus on what matters, not the routine.

Full documentation is available on [our website](https://Chu4hel.github.io/chutils/) (currently in Russian).

## The Problem

Every time you start a new project, you have to solve the same tasks:

- How to conveniently read settings from a configuration file?
- How to configure logging to write messages to both the console and a file with daily rotation?
- How to securely store API keys without hardcoding them in the code?
- How to make it all work "out of the box" without manually defining paths?

**chutils** offers ready-made solutions for all these problems.

## Key Features

- **✨ Zero Configuration:** The library **automatically** finds your project root and the `config.yml` or `config.ini`
  file. It uses **lazy initialization** — no heavy operations until you actually need them.
- **⚙️ Flexible Configuration:** Support for `YAML` and `INI` formats. Simple functions for retrieving typed data.
- **✍️ Advanced Logger:** The `setup_logger()` function configures logging to the console and rotating files out of the
  box. It returns a custom logger with additional debug levels (`devdebug`, `mediumdebug`).
- **🔒 Secure Secret Storage:** The `secret_manager` module provides a simple interface for saving and retrieving secrets
  via the system `keyring`, with a fallback to `.env` files.
- **⚡ Async Ready:** Most core functions have asynchronous versions (prefixed with `a`) for non-blocking execution.
- **🚀 Ready to Use:** Just install and use.

## Installation

```bash
poetry add chutils
```

Or using pip:

```bash
pip install chutils
```

## Examples

In the [`/examples`](./examples/) folder, you will find ready-to-run scripts demonstrating the library's key features.
Each example focuses on a specific task.

## Quick Start

### 1. Working with Configuration

1. (Optional) Create a `config.yml` file in your project root:

   ```yaml
   # config.yml
   Database:
     host: localhost
     port: 5432
   ```

2. Get values in your code:

   ```python
   from chutils import get_config_value, get_config_int

   db_host = get_config_value("Database", "host", fallback="127.0.0.1")
   db_port = get_config_int("Database", "port", fallback=5432)
   ```

   #### Overriding Configuration with Local Files (`config.local.yml`)

   You can create a `config.local.yml` next to your main file. Values from the local file will **override**
   corresponding values from the main file. This is perfect for local development or storing sensitive data (ensure
   `*.local.*` is in your `.gitignore`).

### 2. Logging Setup

1. Configure and use the logger:

   ```python
   from chutils import setup_logger, ChutilsLogger

   # Automatically reads settings from [Logging] section in config.yml
   logger: ChutilsLogger = setup_logger()

   logger.info("Application started.")
   logger.devdebug("Deep debug message (level 9).")
   ```

   #### Controlling Logging via Environment Variables

    - `CH_LOG_NO_TIME=true`: Removes the date/time from the log format (for clean Docker logs).
    - `CH_LOG_NO_FILE=true`: Disables creating log files.

   These variables have **highest priority** and override any code or config settings.

### 3. Secret Management

`SecretManager` looks for secrets in the following order: **Keyring > .env File > Environment Variables**.

```python
from chutils import SecretManager

secrets = SecretManager("my_awesome_app")

# Save once
secrets.save_secret("API_KEY", "secret-value-123")

# Use everywhere
key = secrets.get_secret("API_KEY")
```

#### Disabling Keyring (Optional)

In environments like Docker or CI/CD where `keyring` is unavailable, you can suppress warnings and skip the check:

- Set `CH_DISABLE_KEYRING_WARNING=true` in environment.
- Or add `disable_keyring: true` under `secrets` section in `config.yml`.

## API Overview

### Configuration (`chutils.config`)

- `get_config_value(section, key, fallback)` / `aget_config()`
- `get_config_int`, `get_config_boolean`, `get_config_list`, `get_config_path`
- `save_config_value(section, key, value)` / `asave_config_value()`

### Logging (`chutils.logger`)

- `setup_logger(name, log_level, log_file_name, rotation_type, compress, ...)`
- Levels: `logger.devdebug` (9), `logger.mediumdebug` (15), and all standard ones.

### Secret Management (`chutils.secret_manager`)

- `SecretManager(service_name, prefix)`
- `save_secret` / `asave_secret`
- `get_secret` / `aget_secret`
- `delete_secret` / `adelete_secret`

### Decorators (`chutils.decorators`)

- `@log_function_details`: Logs arguments, execution time, and result (uses `DEVDEBUG` level).

## License

The project is distributed under the MIT License.
