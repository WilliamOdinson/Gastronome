# Local Environment Provisioning Guide

## 1  Prerequisites

For consistent behaviour across development teams, the application is validated on macOS and modern Linux distributions. Windows is supported through WSL 2 only. The current development stack assumes **Python 3.13.3**, **PostgreSQL 14.18**, **Redis 8.0.2**, **OpenSearch 3.0.0**, and **RabbitMQ 4.1.0**.

Although any native installation method will work, containerised deployment with Docker remains the fastest path to parity with production. If you prefer a host-managed installation on macOS, Homebrew is recommended and described below.

## 2  Platform-specific installation options

### 2.1  macOS installation with Homebrew

Begin by installing Homebrew if it is not already present:

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Next, install the required services:

```zsh
brew install postgresql redis opensearch rabbitmq
```

Register each component as a launch agent so that it starts automatically after reboots:

```zsh
brew services start postgresql redis opensearch rabbitmq
```

Confirm that every service is running:

```zsh
brew services list
```

You should see four entries with a `started` status similar to:

```
Name            Status   User       File
opensearch      started  <username> ~/Library/LaunchAgents/homebrew.mxcl.opensearch.plist
postgresql@14   started  <username> ~/Library/LaunchAgents/homebrew.mxcl.postgresql@14.plist
rabbitmq        started  <username> ~/Library/LaunchAgents/homebrew.mxcl.rabbitmq.plist
redis           started  <username> ~/Library/LaunchAgents/homebrew.mxcl.redis.plist
```

### 2.2  Linux installation (Debian / Ubuntu)

### 2.3  Containerised installation with Docker Compose (macOS / Linux / Windows WSL 2)

### 2.4  Minimum security configuration

## 3  Cloning the source repository

```zsh
git clone git@github.com:WilliamOdinson/Gastronome.git
cd Gastronome
cp .env.example .env
```

Open the `.env` file and update the connection strings to match the credentials configured in the previous [2.4 Minimum security configuration](#24--minimum-security-configuration) section. For more details on how `.env` files are structured and used, refer to [docs/dotenv.md](https://github.com/WilliamOdinson/Gastronome/blob/main/docs/dotenv.md)

## 4  Python environment and dependencies

A per-project virtual environment ensures repeatability. The pyenv toolchain makes version management trivial:

```bash
pyenv install 3.13
pyenv virtualenv 3.13 gastronome
pyenv activate gastronome
pyenv local gastronome
pip install --upgrade pip
pip install -r requirements.txt
```

## 5  Database Initialization

After successfully resolving all dependencies, you need to set up the Yelp dataset. First, download the Yelp Open Dataset available from the [Yelp Official Website](https://business.yelp.com/data/resources/open-dataset/). It includes two separate files:

* [Yelp-JSON.zip](https://business.yelp.com/external-assets/files/Yelp-JSON.zip) (\~ 4.35 GB)
* [Yelp-Photos.zip](https://business.yelp.com/external-assets/files/Yelp-Photos.zip) (\~ 7.45 GB)

After extracting both files, ensure your `database/` directory is structured as follows:

```bash
database/
├── photos.json
├── review_predictions.json      # generated in next step via scripts/init-auto-score.py or notebooks/02_Yelp Review Model (transformers).ipynb
├── Yelp Dataset Documentation & ToS.pdf
├── yelp_academic_dataset_business.json
├── yelp_academic_dataset_checkin.json
├── yelp_academic_dataset_review.json
├── yelp_academic_dataset_tip.json
├── yelp_academic_dataset_user.json
└── Yelp_final.csv               # generated in next step via scripts/generate_yelp_final.py or notebooks/03_Recommendation Algorithm (Data Preprocessing).ipynb
```

Next, generate the necessary dataset files using the provided scripts:

```bash
python scripts/init-auto-score.py  # Generates review_predictions.json (semantic scoring predictions)
python scripts/generate_yelp_final.py  # Generates Yelp_final.csv used in model training (details below)
```

Confirm the CSV file structure with:

```bash
head -n 1 database/Yelp_final.csv
# review_id,user_id,business_id,stars,true_stars,state,city,categories
```

## 6. Django Database Migration and Data Import

Before proceeding, ensure you have completed the [5 Database Initialization](#5--database-initialization) step, verifying the existence of all necessary files in the `database/` directory.

> [!CAUTION]
>
> **Important Configuration Checklist:**
>
> 1. Edit `user/models.py`, change the email field to allow empty values:
>
>    ```python
>    email = models.EmailField(max_length=254, unique=True, null=True, blank=True, verbose_name="User's Email")
>    ```
>
>    *(This change is necessary because the Yelp dataset does not provide email addresses.)*
>
> 2. Adjust user identification fields in `user/models.py`:
>
>    ```python
>    USERNAME_FIELD = 'user_id'
>    REQUIRED_FIELDS = []
>    ```
>
>    *(By default, this project uses email for login. Adjust this temporarily for dataset import.)*
>
>    For more details on migrating the users, refer to [docs/migrate-users.md](https://github.com/WilliamOdinson/Gastronome/blob/main/docs/migrate-users.md)
>
> 3. **Delete previous migration**:
>
>    ```bash
>    rm user/migrations/0002_alter_user_email.py
>    ```
>
> 4. Set the environment variable `DEFAULT_USER_PASSWORD` in your `.env` file.

Run migrations and import data using Django management commands:

```bash
python manage.py migrate

python manage.py import_category "./database/yelp_academic_dataset_business.json"
python manage.py import_business "./database/yelp_academic_dataset_business.json"
python manage.py import_hour "./database/yelp_academic_dataset_business.json"
python manage.py import_user "./database/yelp_academic_dataset_user.json"
python manage.py import_email
python manage.py import_password
python manage.py import_checkin "./database/yelp_academic_dataset_checkin.json"
python manage.py import_photo "./database/photos.json"
python manage.py import_review "./database/yelp_academic_dataset_review.json"
python manage.py import_tip "./database/yelp_academic_dataset_tip.json"
python manage.py import_autoscore "./database/review_predictions.json"
```

Alternatively, use the provided shell script for automated execution with estimated timing (approximately 160 minutes):

```bash
bash scripts/init.sh
```

## 7  Training the Recommendation Models

To train recommendation models for each state, run:

```bash
python scripts/train_all_states.py
```

If you prefer to quickly set up an Minimum Viable Product (MVP) by training only models for Pennsylvania (PA), use these commands individually (\~ 90 minutes):

```bash
python manage.py train_svd --state PA
python manage.py train_sgd --state PA
python manage.py train_als --state PA
python manage.py train_ensemble --state PA
```

These models will be used for generating personalized recommendations on your platform.

## 8  Revert User Model Email Field for Production

After all data imports are complete, update the `User` model to require an email address for each user, as expected in production environments. Update your `user/models.py` as follows:

```python
class User(AbstractUser):
    # After importing, set the email field to NOT allow null or blank values
    email = models.EmailField(max_length=254, unique=True, null=False, blank=False, verbose_name="User's Email")
    # Previously, during data import:
    # email = models.EmailField(max_length=254, unique=True, null=True, blank=True, verbose_name="User's Email")

    # Set email as the username field and require user_id for account creation
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['user_id']
    # Previously, during import:
    # USERNAME_FIELD = 'user_id'
    # REQUIRED_FIELDS = []
```

The commented lines show the earlier configuration used for importing dataset users.

After updating the model, run:

```bash
python manage.py makemigrations
python manage.py migrate
```

This ensures that all new users must register with a unique, non-empty email address, preparing the project for production deployment.

## 9  Indexing Data into OpenSearch

Once your database is populated, the next step is indexing the `business`, `user`, `review`, and `tip` models into OpenSearch for efficient and fast search capabilities.

While Django's ORM (backed by psycopg2 in this project) is powerful for general querying, it becomes inefficient and problematic for large-scale search operations. ORM-based searches often suffer from performance issues such as the "N+1 query" problem. For detailed reasoning about why ORMs aren't optimal for large-scale search functionalities, please refer to [docs/search-engine.md](https://github.com/WilliamOdinson/Gastronome/blob/main/docs/search-engine.md).

To address this, the project uses **OpenSearch**, an open-source counterpart of Elasticsearch, optimized for fast, scalable, and efficient searching.

The project provides built-in Django management commands to bulk index data into OpenSearch:

```bash
python manage.py index_business
python manage.py index_review
python manage.py index_tip
python manage.py index_user
```

> [!NOTE]
>
> After running these commands once, new records or updates - such as newly registered users or recently submitted reviews - will be automatically synchronized into OpenSearch through Django signals configured in each app's `apps.py`. This eliminates the need to manually re-run indexing commands for incremental updates.

## 10  Starting the development server

Launch the Django development server:

```bash
python manage.py runserver
```

By default, the server runs at `http://127.0.0.1:8000/`. If you need to serve the application over HTTPS, refer to [docs/https-server.md](https://github.com/WilliamOdinson/Gastronome/blob/main/docs/https-server.md) for setup instructions.
