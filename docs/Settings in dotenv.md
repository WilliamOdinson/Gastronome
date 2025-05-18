Dotenv files should store information that must not be accessible to unauthorized individuals. In other words, they contain constant variables that should be maintained securely in the backend and made available only to you and trusted team members.

In Gastronome, you should typically define the following environment variables in the `.env` file:

1. **DJANGO\_SECRET\_KEY**
   
   The key Django uses for cryptographic signing, session management, and generation of security tokens.

2. **DJANGO\_DEBUG**
   
   A flag (`True` or `False`) that controls whether Django runs in debug mode. It should be `False` in production to avoid leaking detailed error pages.

3. **DJANGO\_ALLOWED\_HOSTS**
   
   A comma-separated list of host/domain names that this Django site can serve. For example:

   ```
   DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1"
   ```

4. **MYSQL\_DATABASE**, **MYSQL\_USER**, **MYSQL\_PASSWORD**, **MYSQL\_HOST**, **MYSQL\_PORT**
   
   These variables configure the connection to the MySQL database:

   * `MYSQL_DATABASE`: the name of the database (e.g. `gastronome`)
   * `MYSQL_USER`: the database user (e.g. `root`)
   * `MYSQL_PASSWORD`: the user’s password
   * `MYSQL_HOST`: the database host (e.g. `localhost`)
   * `MYSQL_PORT`: the database port (e.g. `3306`)

5. **REDIS\_URL**
   
   The connection URL for Redis, including authentication, host, port, and database index. For example:

   ```
   REDIS_URL=redis://:foobared@127.0.0.1:6379/6
   ```

6. **DEFAULT\_USER\_PASSWORD**
   
   A default password for imported users.

7. **GOOGLE\_MAPS\_API\_KEY**
   
   The API key required by Google for integrating Google Maps into the website.
