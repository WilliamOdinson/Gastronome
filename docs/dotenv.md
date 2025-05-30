# Environment Variables Configuration (`.env`)

This document describes the setup and purpose of environment variables in the **Gastronome** project. Environment variables defined in the `.env` file store sensitive information securely, preventing unauthorized access and ensuring data privacy. Only share this file with authorized team members and never commit it to version control.

## Prerequisites

Before proceeding, ensure you have:

- Created a `.env` file at the root directory of your Gastronome project.
- Restricted file permissions to avoid accidental exposure (e.g., using `chmod 600 .env` on Unix-based systems).

## 1  Django Configuration

These variables control Django's runtime behavior and security settings.

```bash
DJANGO_SECRET_KEY="<your-django-secret-key>"
LOAD_TEST="False"    # Set to "True" only in load test environments
DJANGO_DEBUG="True"  # Set to "False" in production environments
DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"  # Add your production domains as needed
```

- **`DJANGO_SECRET_KEY`**: Used for cryptographic signing and session management. Keep it secret.
- **`LOAD_TEST`**: Enables optimizations specific to automated load testing. For more information, refer to [load_tests/README.md](https://github.com/WilliamOdinson/Gastronome/blob/main/load_tests/README.md)
- **`DJANGO_DEBUG`**: Controls debug mode; disable (`False`) in production.
- **`DJANGO_ALLOWED_HOSTS`**: A comma-separated list of allowed domain names/IPs.

## 2  PostgreSQL Database Settings

These variables configure PostgreSQL database connections. Replace `<your_postgres_password>` with your actual database password.

```bash
POSTGRES_DB=gastronome
POSTGRES_USER=gastronome
POSTGRES_PASSWORD=<your_postgres_password>
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

## 3  Redis Configuration

These variables manage Redis caching and session storage.

```bash
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=<your_redis_password>
```

## 4  Default User Password

Used when importing Yelp dataset that didn't provide user-specific passwords.

```bash
DEFAULT_USER_PASSWORD="password888"
```

## 5  Google Maps Integration

API key for Google Maps service integration. Obtain your key from the [Google Cloud Platform Console](https://console.cloud.google.com/).

```bash
GOOGLE_MAPS_API_KEY="<your-google-maps-api-key>"
```

## 6  OpenSearch (Elasticsearch) Settings

Configurations required for connecting to OpenSearch.

```bash
OPENSEARCH_HOST="http://localhost:9200"
OPENSEARCH_USER="django"
OPENSEARCH_PASSWORD="<opensearch-password>"
```

## 7  Celery Configuration

Connection settings for Celery task queue. Replace default credentials (`guest:guest`) with secure ones in a production setup.

```bash
CELERY_BROKER_URL="pyamqp://guest:guest@localhost//"
CELERY_RESULT_BACKEND="rpc://"
```

## 8  Sentry Error Monitoring

Sentry is used for tracking and monitoring runtime errors, exceptions, and performance issues in your Gastronome project. Real-time alerts help you identify and resolve problems quickly in production and development environments. To enable Sentry integration, register an account and project on the [Sentry dashboard](https://sentry.io/). After creating your project (select Django as the platform), you will be provided with a DSN (Data Source Name).

```bash
SENTRY_DSN="https://<your_key>@o0.ingest.us.sentry.io/<project_id>"
SENTRY_ENVIRONMENT="production"
```

## Final Notes

Always maintain `.env` securely:

- Never commit it to Git.
- Regularly update passwords and API keys.
- Limit access to trusted developers and administrators only.
