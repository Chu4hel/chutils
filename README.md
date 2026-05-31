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
  box. Includes **automatic secret masking** and **smart console width detection** for IDEs (PyCharm, etc.).
  It returns a custom logger with additional debug levels (`devdebug`, `mediumdebug`).
- **🔒 Secure Secret Storage:** The `secret_manager` module provides a simple interface for saving and retrieving secrets
  via the system `keyring`, with a fallback to `.env` files.
- **🚀 CLI Booster:** Turn any function into a CLI tool in seconds using the `@cli_command` decorator with automatic type
  mapping and docstring parsing.
- **⏰ Painless Datetime:** Always-aware UTC time utilities, smart parsing, and human-readable time intervals.
- **📡 Distributed Tracing:** Seamless OpenTelemetry integration with `@trace` decorator and automatic log correlation.
- **🔍 Config Diagnostics:** Interactive trace of configuration sources and priorities via `config debug` command.
- **🌐 Remote Configuration:** Load settings from HTTP/HTTPS endpoints with background polling and fallback support.
- **🔄 Hot-Reload:** Support for automatic configuration reloading on file changes without restart (requires
  `pip install chutils[watch]`).
- **⚡ Async Ready:** Most core functions have asynchronous versions (prefixed with `a`) for non-blocking execution.
- **🚀 Ready to Use:** Just install and use.

## Command Line Interface (CLI)

The library provides a `chutils` console command for convenient secret management without writing code.

### Secret Management

```bash
# Save a secret to the system storage (keyring)
chutils secrets set MY_API_KEY "super-secret-value"

# Delete a secret
chutils secrets delete MY_API_KEY

# Explicitly specify service name
chutils secrets set DB_PASSWORD "12345" --service my_custom_app
```

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

   #### Validation via Pydantic (Optional)

   For strict typing and validation, you can use Pydantic models (requires `pip install chutils[pydantic]`):

   ```python
   from pydantic import BaseModel
   from chutils import get_config

   class AppConfig(BaseModel):
       app_name: str
       version: str

   # Returns an instance of AppConfig
   cfg = get_config(model=AppConfig)
   print(cfg.app_name)
   ```

   You can also validate specific sections:
   ```python
   from chutils import get_config_section
   db_cfg = get_config_section("Database", model=MyDbModel)
   ```

   #### Overriding Configuration with Local Files (`config.local.yml`)

   You can create a `config.local.yml` next to your main file. Values from the local file will **override**
   corresponding values from the main file. This is perfect for local development or storing sensitive data (ensure
   `*.local.*` is in your `.gitignore`).

### 2. Hot-Reload

You can make your application react to configuration file changes in real-time.

```python
from chutils import start_config_watcher, on_config_change, get_config_value


def reload_logic():
    print("Configuration updated!")
    # Update app state here
    db_url = get_config_value("Database", "url")


# Register callback
on_config_change(reload_logic)

# Start watcher (requires watchdog package)
start_config_watcher()
```

To use this feature, install `watchdog`:
`pip install chutils[watch]`

### 3. Logging Setup

1. Configure and use the logger:

   ```python
   from chutils import setup_logger, ChutilsLogger

   # Automatically reads settings from [Logging] section in config.yml
   logger: ChutilsLogger = setup_logger()

   logger.info("Application started.")
   logger.devdebug("Deep debug message (level 9).")
   ```

   #### Structured Logging (JSON)

   If you need to output logs in JSON format for ELK, Splunk, or cloud logging (requires `pip install chutils[json]`):

   ```python
   # Via code
   logger = setup_logger(json_format=True)

   # Or via config in the [Logging] section
   # json_format: true
   ```

   #### Contextual Logging (ContextVar)

   You can bind metadata to the current execution context (thread or coroutine), and it will be automatically
   included in all log messages.

   ```python
   from chutils import setup_logger, bind_context

   logger = setup_logger()

   # Bind request ID and user to the current context
   bind_context(request_id="REQ-123", user="admin")

   logger.info("Action performed")
   # Text: ... [request_id=REQ-123 user=admin] Action performed
   # JSON: {..., "message": "Action performed", "context": {"request_id": "REQ-123", "user": "admin"}}
   ```

   #### Controlling Logging via Environment Variables

    - `CH_LOG_JSON=true`: Forces JSON format.
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
- `save_config_value(section, key, value, notify=True)` / `asave_config_value()`
- Use `notify=False` to update the file without triggering Hot-Reload callbacks.

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
- `@timeout(seconds, fallback)`: Limits function execution time. Supports sync/async and optional fallback.
- `@retry`: Automatically retries a function if it fails. Supports sync/async, backoff, jitter, and exception filtering.
- `@cli_command`: Turns any function into a standalone CLI script with automatic argument parsing.

### Time & Dates (`chutils.time`)

- `utc_now()`: Returns a timezone-aware UTC datetime.
- `parse_datetime(value)`: Smart parsing of strings and timestamps into UTC.
- `humanize_timedelta(dt)`: Returns human-readable strings like "5 minutes ago" or "tomorrow".

### Example of @retry usage:

```python
from chutils.decorators import retry


@retry(retries=3, delay=1.0, backoff=2.0)
def fetch_data():
    # Will be retried up to 3 times on any Exception
    ...
```

## Command Line Interface (CLI)

`chutils` includes a set of tools to speed up development and debugging.

### 1. Initialize Project

Quickly set up a new project with a default configuration and `.gitignore` rules:

```bash
# Interactive mode
chutils init

# Non-interactive mode (default values)
chutils init -y
```

### 2. Validate Configuration

Check if your configuration files match your Pydantic models:

```bash
# Automatically finds 'Settings' class in context.py or config.py
chutils validate

# Explicitly specify the model path
chutils validate --model src.settings:AppConfig
```

### 3. Debug Search Paths

See exactly where `chutils` is looking for configuration files:

```bash
# Human-readable output
chutils show-paths

# JSON output for automation
chutils show-paths --json
```

### 4. Manage Secrets

Manage your system keyring secrets directly from the terminal:

```bash
# Set a secret
chutils secrets set API_KEY "your-secret-value" --service my_app

# Delete a secret
chutils secrets delete API_KEY --service my_app
```

### 5. Debug Configuration

Trace exactly where each configuration value comes from:

```bash
chutils config debug
```

## License

The project is distributed under the MIT License.
