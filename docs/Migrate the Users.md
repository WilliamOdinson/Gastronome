## Initialization: Set Email as the Login Field

**Prerequisites**
- `init.sh` has been fully executed.
- The `user_user` table contains no `NULL` values in the `email` field.
- To verify, run the following SQL queries:
  ```sql
  SELECT COUNT(email) FROM user_user;
  SELECT COUNT(DISTINCT email) FROM user_user;
  ```
  The two resulting numbers should both be `1987897` (equal to the total number of users).

**Execution Steps**

1. **Modify the `User` model in `models.py`**, ensuring the following:
   ```python
   email = models.EmailField(max_length=254, unique=True, verbose_name="User's Email")
   USERNAME_FIELD = 'email'
   REQUIRED_FIELDS = ['user_id']
   ```

2. **Generate a database migration file**

   Run the command to create a new migration:
   ```bash
   python manage.py makemigrations
   ```
   When prompted with:
   ```
   It is impossible to change a nullable field 'email' on user to non-nullable without providing a default. This is because the database needs something to populate existing rows.
   Please select a fix:
    1) Provide a one-off default now (will be set on all existing rows with a null value for this column)
    2) Ignore for now. Existing rows that contain NULL values will have to be handled manually, for example with a RunPython or RunSQL operation.
    3) Quit and manually define a default value in models.py.
   Select an option:
   ```
   choose:
   ```
   2) Ignore for now. Existing rows that contain NULL values will have to be handled manually, for example with a RunPython or RunSQL operation.
   ```

3. **Apply the migration**

   Update the database structure by running:
   ```bash
   python manage.py migrate
   ```
   