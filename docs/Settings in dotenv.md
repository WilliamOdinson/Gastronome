Dotenv files should store information that must not be accessible to unauthorized individuals. In other words, they contain constant variables that should be maintained securely in the backend and made available only to you and trusted team members.

In Gastronome, you should typically define the following environment variables in the `.env` file:

1. **DJANGO_SECRET_KEY**

   This is the key Django uses for cryptographic signing, session management, and the generation of security tokens.

2. **MYSQL_DATABASE**, **MYSQL_USER**, **MYSQL_PASSWORD**

   These variables configure the connection to the MySQL database and contain sensitive credentials that must remain confidential.

3. **DEFAULT_USER_PASSWORD**

   This sets a default password for users to log in to the system.

4. **GOOGLE_MAPS_API_KEY**
   
   The API key required by Google for integrating Google Maps into the website.
