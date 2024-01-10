

echo "Installing Dependancies..."
pip install -r requirements.txt

echo "Make Migrations..."
python3.9 manage.py makemigrations --noinput
python3.9 manage.py migrate --noinput

echo "Collecting Stats..."
python3.9 manage.py collectstatic --noinput