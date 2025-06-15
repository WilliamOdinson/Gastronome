# PgBouncer + PostgreSQL Setup Guide

To safely accommodate more than 100 concurrent users during load testing and future peak usage of the Gastronome System, PostgreSQL's default connection limit, typically set at 100 by the `max_connections` parameter in `postgresql.conf`, must be strategically managed. Rather than simply increasing this limit, which can negatively impact database performance due to resource overhead, deploying a connection pooler such as [PgBouncer](https://www.pgbouncer.org/) is advisable. PgBouncer efficiently manages client connections by pooling thousands of simultaneous connections into a significantly smaller, controlled number of actual physical database connections. This approach maintains database stability and ensures optimal performance even under heavy user loads.

## Installation & Configuration Steps

### 1. PostgreSQL Configuration

Modify your PostgreSQL configuration file (`postgresql.conf`):

```ini
# CONNECTIONS AND AUTHENTICATION
max_connections = 53
superuser_reserved_connections = 3
```

Apply changes by restarting PostgreSQL:

```bash
brew services restart postgresql@14
```

### 2. PgBouncer Installation

Install PgBouncer via Homebrew:

```bash
brew install pgbouncer
```

Identify the installation paths for configuration files (`pgbouncer.ini` and `userlist.txt`):

```bash
brew info pgbouncer
```

Typically found at:

* `/opt/homebrew/etc/pgbouncer.ini`
* `/opt/homebrew/etc/userlist.txt`

Start PgBouncer service:

```bash
brew services start pgbouncer
```

### 3. PgBouncer Configuration

Update `/opt/homebrew/etc/pgbouncer.ini` with the following settings:

```ini
[databases]
gastronome = host=127.0.0.1 port=5432 dbname=gastronome

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432

auth_type = md5
auth_file = /opt/homebrew/etc/userlist.txt
admin_users = postgres, appuser

pool_mode = transaction
default_pool_size = 45
reserve_pool_size = 5
reserve_pool_timeout = 5
max_client_conn = 1000

log_connections = 1
log_disconnections = 1
logfile = /opt/homebrew/var/log/pgbouncer.log
pidfile = /opt/homebrew/var/run/pgbouncer.pid
```

### 4. Create Application User in PostgreSQL

Connect as superuser (`postgres`) and create an application user (`appuser`):

```bash
psql -U postgres -h 127.0.0.1 -p 5432 -d gastronome
```

Execute the following SQL commands:

```sql
-- Create the application user
CREATE USER appuser WITH LOGIN PASSWORD 'APPUSER_PASSWORD';

-- Grant required privileges
GRANT CONNECT, CREATE, TEMP ON DATABASE gastronome TO appuser;
GRANT USAGE, CREATE ON SCHEMA public TO appuser;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO appuser;
GRANT USAGE, UPDATE ON ALL SEQUENCES IN SCHEMA public TO appuser;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO appuser;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, UPDATE ON SEQUENCES TO appuser;
```

### 5. Django Application Configuration

Update Django's database configuration to point to PgBouncer:

```python
DATABASES["default"].update({
    "HOST": "127.0.0.1",
    "PORT": "6432",
    "CONN_MAX_AGE": None,
})
```

### 6. Generate `userlist.txt` Passwords

Use the provided script (`generate_md5.py`) to create hashed passwords:

```bash
python generate_md5.py
```

This appends hashed passwords to `docs/pgbouncer/userlist.txt`:

```ini
"postgres" "md5XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
"appuser"  "md5XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
```

Copy these hashes to `/opt/homebrew/etc/userlist.txt`.

## Verification

Test connection through PgBouncer. When prompted, enter your password:

```bash
psql -U appuser -h 127.0.0.1 -p 6432 -d gastronome

# Password for user appuser:
```

Successful connection output:

```bash
psql (14.18 (Homebrew))
Type "help" for help.

gastronome=> 
```

Run these queries to confirm the active user:

```sql
-- Confirm the current logged-in user
SELECT current_user;
```

```sql
-- Check privileges on the current database
\l gastronome
```

```sql
-- List default privileges that apply to future tables/sequences
SELECT * FROM information_schema.role_table_grants WHERE grantee = 'appuser';
```
