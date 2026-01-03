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
  file. If the file is not found, safe defaults are used.
- **⚙️ Flexible Configuration:** Support for `YAML` and `INI` formats. Simple functions for retrieving typed data.
- **✍️ Advanced Logger:** The `setup_logger()` function configures logging to the console and rotating files out of the
  box. It returns a custom logger with additional debug levels (`devdebug`, `mediumdebug`).
- **🔒 Secure Secret Storage:** The `secret_manager` module provides a simple interface for saving and retrieving secrets
  via the system `keyring`, with a fallback to `.env` files.
- **🚀 Ready to Use:** Just install and use.

## Installation

```bash
poetry add chutils
```

Or using pip:

```bash
pip install chutils
```

For development, clone the repository and install in editable mode:

```bash
git clone https://github.com/Chu4hel/chutils.git
cd chutils
pip install -e .
```

## Examples

In the [`/examples`](./examples/) folder, you will find ready-to-run scripts demonstrating the library's key features.
Each example focuses on a specific task.

## Quick Start

### 1. Working with Configuration

1. (Optional) Create a `config.yml` file in your project root. If you skip this, the library will use defaults:

   ```yaml
   # config.yml
   Database:
     host: localhost
     port: 5432
     user: my_user
   ```

2. Get values in your code:

   ```python
   # main.py
   from chutils import get_config_value, get_config_int

   db_host = get_config_value("Database", "host", fallback="127.0.0.1")
   db_port = get_config_int("Database", "port", fallback=5433)

   print(f"Connecting to DB at: {db_host}:{db_port}")
   # Output: Connecting to DB at: localhost:5432
   ```
   `chutils` will automatically find `config.yml` and read the data.

   #### Overriding Configuration with Local Files (`config.local.yml`)

   You can create a local configuration file (e.g., `config.local.yml` or `config.local.ini`) next to your main file (
   `config.yml` or `config.ini`). Values from the local file will **override** corresponding values from the main file.
   This is useful for:
    - Storing sensitive data that should not be committed to version control (add `config.local.yml` to `.gitignore`).
    - Overriding settings for local development without changing the main file.

   **Example:**
   If `config.yml` contains:
   ```yaml
   # config.yml
   Database:
     host: production_db.com
     port: 5432
   App:
     debug: false
   ```
   And `config.local.yml` contains:
   ```yaml
   # config.local.yml
   Database:
     host: localhost
   App:
     debug: true
     developer_mode: true
   ```
   Then `get_config()` will return:
   ```yaml
   Database:
     host: localhost # Overridden by local file
     port: 5432      # From main file
   App:
     debug: true         # Overridden by local file
     developer_mode: true # Added from local file
   ```
   **Important:** Ensure you add `config.local.yml` (or `config.local.ini`) to your `.gitignore`.

### 2. Logging Setup

1. Add a `Logging` section to your `config.yml` (optional):

   ```yaml
   # config.yml
   Logging:
     log_level: DEBUG
     log_file_name: my_app.log
   ```

2. Use the logger:

   ```python
   # main.py
   from chutils import setup_logger, ChutilsLogger

   # Configure logger. It automatically reads settings from config.
   logger: ChutilsLogger = setup_logger()

   logger.info("Application started.")
   logger.debug("This is a debug message.")
   # Output to console and writes to file logs/my_app.log
   ```
   The `logs` folder will be created automatically.

   You can also specify the log filename directly when calling `setup_logger`, overriding the config:
   ```python
   # main.py
   from chutils import setup_logger, ChutilsLogger

   # Logger will write to custom.log, ignoring log_file_name from config.yml
   logger: ChutilsLogger = setup_logger(log_file_name="custom.log")

   logger.info("Message in a custom file.")
   ```

   #### Creating Multiple Loggers

   You can create different loggers for different parts of your application by passing a unique name to `setup_logger`.
   This helps filter and separate logs.

   ```python
   # main.py
   from chutils import setup_logger

   # Main app logger will write to main_app.log
   main_logger = setup_logger("main_app", log_file_name="main_app.log")
   # Logger for the database module will write to database.log
   db_logger = setup_logger("database", log_file_name="database.log")

   main_logger.info("Application started.")
   db_logger.debug("Initializing DB connection...")
   ```
   See [`/examples/05_different_log_levels.py`](./examples/05_different_log_levels.py) for a detailed example.

   #### Configuring Multiple Loggers via File

   You can centrally manage settings for different loggers using the `config_section_name` parameter.

    1. **Add sections to `config.yml`**:
       The `[Logging]` section is used for defaults. Other sections can be used for specific loggers.
       ```yaml
       # config.yml
       Logging:
         log_level: INFO
         rotation_type: time
         compress: true
 
       AuditLogger:
         log_level: DEBUG
         log_file_name: "audit.log"
       ```

    2. **Use `config_section_name` in code**:
       ```python
       # main.py
       from chutils import setup_logger
 
       # This logger takes settings from [Logging]
       main_logger = setup_logger("main")
       main_logger.info("Message from main logger.")
 
       # This logger takes settings from [AuditLogger], overriding defaults
       audit_logger = setup_logger("audit", config_section_name="AuditLogger")
       audit_logger.debug("Detailed audit message.")
       ```

### 3. Secret Management

`SecretManager` looks for secrets in the following order:

1. **System Storage (`keyring`)**: The most secure method.
2. **`.env` File**: If the secret is not found in `keyring`, the manager looks in the `.env` file in the project root.
3. **Environment Variables**: If not found there either, it checks OS environment variables.

#### Method 1: Keyring (Recommended)

1. Initialize `SecretManager` and save your secret. **Do this once.**

   ```python
   # setup_secrets.py
   from chutils import SecretManager

   secrets = SecretManager("my_awesome_app")
   secrets.save_secret("DB_PASSWORD", "MySuperSecretDbPassword123!")
   print("DB password saved to system storage!")
   ```

2. Retrieve the secret in your main code without exposing it:

   ```python
   # main.py
   from chutils import SecretManager, get_config_value

   secrets = SecretManager("my_awesome_app")
   db_user = get_config_value("Database", "user")

   # Get password from secure storage
   db_password = secrets.get_secret("DB_PASSWORD")

   if db_password:
       print(f"Password retrieved for user {db_user}.")
   else:
       print("Password not found!")
   ```

#### Method 2: .env File (Useful for Docker and CI/CD)

1. Create a `.env` file in your project root:
   ```dotenv
   # .env
   DB_PASSWORD="AnotherSecretPassword"
   API_KEY="abcdef123456"
   ```

2. `SecretManager` automatically finds this file and reads variables if not found in `keyring`.

   ```python
   # main.py
   from chutils import SecretManager

   secrets = SecretManager("my_awesome_app")

   # This secret will be taken from .env if not in keyring
   api_key = secrets.get_secret("API_KEY")
   print(f"Found API key: {api_key}")
   ```

## Comprehensive Example

This example shows how all `chutils` components work together.

1. **`config.yml`:**
   ```yaml
   API:
     base_url: https://api.example.com

   Database:
     host: localhost
     port: 5432
     user: my_user

   Logging:
     log_level: INFO
   ```

2. **`main.py`:**
   ```python
   # main.py
   from chutils import get_config_value, setup_logger, SecretManager, ChutilsLogger

   # 1. Setup logger. It automatically reads settings from config.
   logger: ChutilsLogger = setup_logger()

   # 2. Initialize secret manager for our app.
   secrets = SecretManager("my_awesome_app")

   def setup_credentials():
       """Function to save password initially if missing."""
       db_user = get_config_value("Database", "user")
       password_key = f"{db_user}_password"

       if not secrets.get_secret(password_key):
           logger.info("DB password not found. Saving new one...")
           secrets.save_secret(password_key, "MySuperSecretDbPassword123!")
           logger.info("DB password saved to system storage.")

   def connect_to_db():
       """Example DB connection using config and secrets."""
       db_host = get_config_value("Database", "host")
       db_user = get_config_value("Database", "user")
       db_password = secrets.get_secret(f"{db_user}_password")

       if not db_password:
           logger.error("Failed to retrieve DB password!")
           return

       logger.info(f"Connecting to {db_host} as {db_user}...")
       # ... connection logic ...
       logger.info("Connected successfully!")

   def main():
       logger.info("App started.")
       setup_credentials()
       connect_to_db()
       logger.info("App finished.")

   if __name__ == "__main__":
       main()
   ```

## API

### Configuration (`chutils.config`)

- `get_config_value(section, key, fallback="")`: Get a value.
- `get_config_int(section, key, fallback=0)`: Get an integer.
- `get_config_boolean(section, key, fallback=False)`: Get a boolean.
- `get_config_list(section, key, fallback=[])`: Get a list.
- `get_config_section(section)`: Get the entire section as a dictionary.
- `save_config_value(section, key, value)`: Save a value. Works for `.yml` and `.ini`.
  **Note**: comments and formatting are lost when saving to `.yml`. They are preserved for `.ini`.

### Logging (`chutils.logger`)

- `setup_logger(name='app_logger', log_level_str='')`: Configures and returns a `ChutilsLogger` instance.
- `logger.mediumdebug("message")`: Log with level 15.
- `logger.devdebug("message")`: Log with level 9.

### Secret Management (`chutils.secret_manager`)

- `SecretManager(service_name, prefix="Chutils_")`: Creates a manager isolated by service name.
- `secrets.save_secret(key, value)`: Saves a secret.
- `secrets.get_secret(key)`: Retrieves a secret.
- `secrets.delete_secret(key)`: Deletes a secret.

### Decorators (`chutils.decorators`)

- `log_function_details`: Decorator for logging function call details (arguments, execution time, result).

### Manual Initialization (`chutils.init`)

In 99% of cases, you **will not need this**. But if automation fails, you can manually specify the project path once at
the very beginning:

```python
import chutils

chutils.init(base_dir="/path/to/my/project/root")
```

### Note on `secret_manager` (Keyring)

The `SecretManager` module uses the `keyring` library to securely store secrets in system storage.

- On **Windows** and **macOS**, this works "out of the box".
- **Linux Requirements**: Secure `keyring` operation on Linux requires an installed and configured backend (secret
  storage), such as `GNOME Keyring` (Seahorse) or `KWallet`. On servers or minimal builds, you may need to install this
  manually.
  See the [official `keyring` documentation](https://keyring.readthedocs.io/en/latest/) for details.
- **Mobile OS**: This module is **not intended** for use on mobile operating systems (Android, iOS). `keyring` will
  likely not find system storage and may use an **insecure** method to store your secrets.

## License

The project is distributed under the MIT License.