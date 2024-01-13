

echo "Installing Dependancies..."
pip install -r requirements.txt



echo "Collecting Stats..."
python3.9 manage.py collectstatic --noinput