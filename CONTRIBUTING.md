# Contribution Guidelines (CONTRIBUTING.md)

Thank you for your interest in contributing to **Gastronome**!

Whether you aim to fix bugs, propose new features, enhance documentation, or optimize model performance, we warmly welcome your participation. To maintain code quality, consistency, and project maintainability, please carefully read these guidelines before submitting your contributions.

## 1  Setting Up the Development Environment

The project is based on **Python 3.13** and **Django 5**. We strongly recommend referring to [docs/setup.md](docs/setup.md) and completing the following steps:

- Install PostgreSQL, Redis, OpenSearch, and RabbitMQ.
- Configure your `.env` file with required environment variables.
- Set up a Python virtual environment (using `pyenv` is recommended).
- Install dependencies via `pip install -r requirements.txt`.
- Run data initialization scripts and model training scripts.
- Start the local development server.

If you encounter any issues during setup, consult existing documentation or open an [Issue](https://github.com/WilliamOdinson/Gastronome/issues) for assistance.

## 2  Branching and Development Workflow

We use a standard Fork-PR workflow. Follow these steps for a smooth contribution process:

1. Fork the main repository to your GitHub account.
2. Create a dedicated feature branch (avoid working directly on the `main` branch):

   ```bash
   git checkout -b feature/your-feature-name
   ```

3. Before coding, ensure your local branch is synchronized with the upstream repository.
4. Write your code along with necessary unit or functional tests.
5. Follow clear commit conventions (refer to [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)):

   ```text
   feat: implement user recommendation caching feature
   fix: resolve inconsistent API response status codes
   docs: improve model training documentation
   ```

6. Push your branch to your forked repository and submit a Pull Request to the `main` branch of the upstream repository.
7. Await review feedback and make necessary adjustments as required.

## 3  Code Style and Static Checks

All Python code must adhere to the **PEP8** standard. The project's coding conventions are defined explicitly in [pyproject.toml](https://github.com/WilliamOdinson/Gastronome/blob/main/pyproject.toml). Use the provided formatting tool for consistent code quality:

```bash
# Install autopep8
pip install autopep8
scripts/check_autopep8.sh
```

Additionally, each push automatically triggers the GitHub Actions workflow defined in `.github/workflows/format-check.yml`. Pay attention to the returned status code to promptly resolve any formatting issues.

## 4  Testing Requirements

When contributing functional code - especially recommendation algorithms, APIs, or database operations - ensure you provide corresponding test cases and validate them locally.

We recommend using Django's built-in testing framework:

```bash
python manage.py test [your_modified_module]
```

Each commit triggers a comprehensive validation process via GitHub Actions (`.github/workflows/django-ci.yml`). Monitor its results and correct issues promptly.

## 5  Bug Reports and Feature Requests

- For bugs or unexpected behaviors, please submit a detailed description using the provided [Issue template](https://github.com/WilliamOdinson/Gastronome/issues/new?template=request.yaml).
- Before suggesting new features, search existing issues to avoid duplication.
- Provide reproducible examples, error logs, data samples, and other relevant information whenever possible.

## 6  Reporting Security Vulnerabilities

If you discover a potential security vulnerability, **do not** report it via public issues. Instead, follow the guidelines outlined in our [Security Policy](https://github.com/WilliamOdinson/Gastronome/security/policy) to securely and responsibly communicate vulnerabilities.

## 7  Open Source License

All contributions to this project are subject to the [MIT License](LICENSE). By submitting your code, you agree to grant the project maintainers permission to use, copy, modify, and distribute your contributions accordingly.

Feel free to reach out with any questions. Thank you for supporting Gastronome!
