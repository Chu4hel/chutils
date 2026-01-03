[Русская версия](docs/CONTRIBUTING_RU.md)

# How to Contribute to chutils

We're excited that you want to help improve the project! Every contribution is highly valued.

This document provides a set of guidelines for contributing to `chutils`.

## Code of Conduct

First and foremost, please review our [Code of Conduct](./CODE_OF_CONDUCT.md). We expect all participants to adhere to it.

## How Can You Help?

### Reporting Bugs

- Ensure the bug hasn't already been reported by checking the [Issues](https://github.com/Chu4hel/chutils/issues) section.
- If you don't find a similar issue, create a new one. Be sure to include a clear title, a detailed description, and, if possible, a small code sample to reproduce the error.

### Suggesting Enhancements

- Create a new issue with your suggestion. Describe in detail the problem your enhancement solves and how it should work.

### Pull Requests

We welcome your pull requests! Here’s how to do it right:

1.  Fork the repository.
2.  Create a new branch for your changes (`git checkout -b feature/amazing-feature`).
3.  Make your changes and write tests for them if necessary.
4.  Ensure all tests pass.
5.  Submit a pull request to the `main` branch of our repository.

## Development Environment Setup

1.  Clone your forked repository:
    ```bash
    git clone https://github.com/YOUR_USERNAME/chutils.git
    ```

2.  Navigate to the project directory:
    ```bash
    cd chutils
    ```

3.  Install dependencies using Poetry:
    ```bash
    poetry install
    ```

## Testing and Documentation

- **Run tests**:
  ```bash
  poetry run pytest
  ```

- **View documentation locally**:
  ```bash
  poetry run mkdocs serve
  ```

## Code and Commit Style

- **Code Style**: We adhere to the PEP 8 standard. Please ensure your code complies with it.
- **Docstrings**: All docstrings are written in **Google style**. Please follow this convention.
- **Commits**: We use [Conventional Commits](https://www.conventionalcommits.org/). This helps us maintain a clean and understandable change history.
  *Example: `feat(config): add support for .toml format` or `fix(logger): correct log rotation error`*

Thank you for your contribution!
