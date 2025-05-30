# Django 5 Recommendation System: Gastronome

**Gastronome** is a local business recommendation system built upon semantic sentiment scoring, utilizing [the Yelp dataset](https://business.yelp.com/data/resources/open-dataset/). Developed with the Django 5 framework. The core objective of the system is to enhance recommendation quality by **leveraging users' historical reviews combined with semantic analysis**.

Backend & Services: [![Python](https://img.shields.io/badge/Python-3.13.3-3776AB?logo=python&logoColor=white)](https://www.python.org/) [![Django](https://img.shields.io/badge/Django-5.2.1-092E20?logo=django&logoColor=white)](https://www.djangoproject.com/) [![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14.18-blue?logo=postgresql&logoColor=white)](https://www.postgresql.org/) [![Celery](https://img.shields.io/badge/Celery-5.5.2-37814A?logo=celery&logoColor=white)](https://docs.celeryq.dev/) [![RabbitMQ](https://img.shields.io/badge/RabbitMQ-4.1.0-FF6600?logo=rabbitmq&logoColor=white)](https://www.rabbitmq.com/) [![Redis](https://img.shields.io/badge/Redis-8.0.2-b01311?logo=redis&logoColor=white)](https://redis.io/)

Search & Recommendation: [![OpenSearch](https://img.shields.io/badge/OpenSearch-3.0.0-005EB8?logo=opensearch&logoColor=white)](https://opensearch.org/) [![PyTorch](https://img.shields.io/badge/PyTorch-2.7.0-EE4C2C?logo=pytorch&logoColor=white)](https://pytorch.org/) [![Transformers](https://img.shields.io/badge/Transformers-HF-FFBF00?logo=huggingface&logoColor=white)](https://huggingface.co/docs/transformers) [![pandas](https://img.shields.io/badge/pandas-2.2.3-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org/) [![NumPy](https://img.shields.io/badge/NumPy-2.2.5-013243?logo=numpy&logoColor=white)](https://numpy.org/)

Frontend & UI: [![HTML5](https://img.shields.io/badge/HTML5-E34F26?logo=html5&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/html) [![CSS3](https://img.shields.io/badge/CSS3-1572B6?logo=css3&logoColor=white)](https://developer.mozilla.org/en-US/docs/Web/CSS) [![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3.3-7952B3?logo=bootstrap&logoColor=white)](https://getbootstrap.com/) [![JavaScript](https://img.shields.io/badge/JavaScript-ES2023-F7DF1E?logo=javascript&logoColor=black)](https://developer.mozilla.org/en-US/docs/Web/JavaScript) [![Google Maps](https://img.shields.io/badge/Google%20Maps%20Static%20API-grey?logo=googlemaps&logoColor=white)](https://developers.google.com/maps/documentation/maps-static)

Load Test: [![Locust](https://img.shields.io/badge/Locust-2.37.6-brightgreen?logo=speedtest&logoColor=white)](https://locust.io/)

Deployment & Monitoring: [![Sentry](https://img.shields.io/badge/Sentry-2.29.1-362D59?logo=sentry&logoColor=white)](https://sentry.io/)

## Features

1. **Semantic Scoring**: When a user submits a review, the system asynchronously invokes a DistilBERT-based text classification model to assign a semantic score that reflects both the sentiment and the underlying meaning of the review content.

2. **Personalized Restaurant Recommendation**: The system uses a hybrid recommendation model (MSE = 2.09; see [notebook](https://github.com/WilliamOdinson/Gastronome/blob/main/notebooks/04_Recommendation%20Algorithm%20%28Philadelphia%29.ipynb)) based on matrix factorization to generate personalized restaurant recommendations for active users, as well as popular restaurant rankings by state. Recommendation results are pre-cached in Redis to optimize response times, and Celery is used to handle recommendation calculations asynchronously.

3. **Real-Time Business Status Updates**: Scheduled background tasks powered by Celery automatically update the open/closed status of each business according to real-world operating hours. The frontend reflects the current business status in real time for users.

4. **Full-Text Search with OpenSearch**: The system integrates with OpenSearch for fast, multi-field full-text searching of business data. Business information is pre-indexed, supporting queries by name, category, and location.

5. **Comprehensive Social Features**: Users can register, log in, manage their profiles, and view their review history. Authenticated users can submit new reviews or delete their own. Each review dynamically updates the associated business's average rating and the user's cumulative review statistics.

## Directory Structure

1. `Gastronome/`: The main Django project directory, containing core configuration files such as `settings.py` and `urls.py`. Sensitive information (e.g., database credentials, API keys) is managed via a separate `.env` file. The project uses [Django's template](https://docs.djangoproject.com/en/5.2/topics/templates/) (based on Jinja2); global HTML templates are stored in `Gastronome/templates/`, and static assets like CSS and JavaScript are placed in `static/`.

2. `business/`, `user/`, `review/`, `api/`, `recommend/`, `experiments/`, `core/`: Core Django apps implementing the main features of the system.
    - `business/` handles business data and presentation.
    - `user/` provides user registration, login, and profile services.
    - `review/` manages user reviews and rating logic.
    - `api/` centralizes reusable APIs, including interactions with third-party services and internal API wrappers.
    - `recommend/` contains the recommendation system implementation.
    - `experiments/` used for showcasing backend and recommendation algorithm experiments, providing interactive HTML pages that allow users to try out features like semantic scoring.
    - `core/` powers the homepage, search, and other key site features.

3. `assets/`: Stores state-specific recommendation model files (ALS, SGD, SVD, and ensemble models), as well as the fine-tuned DistilBERT tokenizer and model weights used for semantic scoring.

4. `docs/`: Documentation directory for the system.

5. `scripts/`: Contains system initialization and maintenance scripts, including data import utilities and model update workflows.

## Installation & Running

It is recommended to follow the configuration and deployment instructions in the documentation for setting up your local environment, environment variables, and dependencies. For detailed steps and important notes, please refer to [docs/setup.md](https://github.com/WilliamOdinson/Gastronome/tree/main/docs/setup.md).

## Contribution Guidelines

**Before contributing, please adhere to our [Code of Conduct](https://github.com/WilliamOdinson/Gastronome?tab=coc-ov-file#readme).** We welcome all forms of contributions! If you encounter any bugs or have suggestions for improvement, please open an **[Issue](https://github.com/WilliamOdinson/Gastronome/issues/new?template=request.yaml)** describing the details. To fix issues or propose new features, feel free to fork the repository and submit a Pull Request. Make sure to clearly explain the changes you've made and include any relevant tests or documentation.

If you discover a potential security vulnerability, **do not open a public issue**. Instead, please refer to our [Security Policy](https://github.com/WilliamOdinson/Gastronome?tab=security-ov-file) for instructions on how to report it responsibly.

## License

This project is licensed under the **MIT License**. You are free to use, copy, modify, and distribute the software, provided that the original copyright notice and license terms are retained.
