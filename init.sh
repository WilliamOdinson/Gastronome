set -e

PROJECT_NAME="Gastronome"
DATA_DIR="./database"

# echo ">>> Creating Python virtual environment..."
# python3 -m venv venv
# source venv/bin/activate

# echo ">>> Upgrading pip and installing requirements..."
# pip install --upgrade pip
# pip install -r requirements.txt

# echo ">>> Applying database migrations..."
# python manage.py makemigrations
# python manage.py migrate

# If this is your first time running it, uncomment the line.
# Skip this step if it's already been created.
# echo ">>> Creating superuser (optional)..."
# python manage.py createsuperuser || true

echo "===The following import may take about 90 minutes (for an 8GB M2 Macbook). ==="
echo "===If your hardware is better, please adjust the batch size.==="
echo "===You can comment out line 39 if you read the entire init.sh before executing.==="
echo ">>> Press any key to continue..." && stty -echo -icanon && dd bs=1 count=1 2>/dev/null < /dev/tty && stty icanon echo

echo ">>> Importing category data, 1,311 entires (~0.1 min)"
python manage.py import_category "$DATA_DIR/yelp_academic_dataset_business.json"

echo ">>> Importing business data, 150,346 entires (~2 min for batch = 1,000)"
python manage.py import_business "$DATA_DIR/yelp_academic_dataset_business.json"

echo ">>> Importing hour data, 150,346 entires (~2 min for batch = 5,000)"
python manage.py import_hour "$DATA_DIR/yelp_academic_dataset_business.json"

echo ">>> Importing user data, 1,987,897 entires (~16 min for batch = 5,000)"
python manage.py import_user "$DATA_DIR/yelp_academic_dataset_user.json"

echo ">>> Importing user's email data, 1,987,897 entires (~25 min for batch = 10,000)"
python manage.py import_email

echo ">>> Importing user's password data, 1,987,897 entires (~1 min)"
echo ">>> [\!note]: Did you set the password in the .env file?"
echo ">>> Press any key to continue..." && stty -echo -icanon && dd bs=1 count=1 2>/dev/null < /dev/tty && stty icanon echo
python manage.py import_password

echo ">>> Importing checkin data, 131,930 entires (~14 min for batch = 5,000)"
python manage.py import_checkin "$DATA_DIR/yelp_academic_dataset_checkin.json"

echo ">>> Importing photo data, 201,000 entires (~0.1 min for batch = 10,000)"
echo ">>> [\!note]: photo.json is in Yelp Photos dataset"
echo ">>> Press any key to continue..." && stty -echo -icanon && dd bs=1 count=1 2>/dev/null < /dev/tty && stty icanon echo
python manage.py import_photo "$DATA_DIR/photos.json"

echo ">>> Importing reviews, 6,990,280 entires (~45 min for batch = 10,000)"
python manage.py import_review "$DATA_DIR/yelp_academic_dataset_review.json"

echo ">>> Importing tips, 908,915 entires (~2 min for batch = 10,000)"
python manage.py import_tip "$DATA_DIR/yelp_academic_dataset_tip.json"

echo ">>> All done. Run the server with:"
echo "    source venv/bin/activate && python manage.py runserver"
