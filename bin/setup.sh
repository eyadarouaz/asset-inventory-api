#!/bin/bash

# Update package list and install Python and virtual environment tools
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv

# Create a virtual environment
python3 -m venv venv

# Activate the virtual environment
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install Django and other common packages
pip install django djangorestframework psycopg2-binary gunicorn

# Echo Python and Django versions
echo "Python version: $(python3 --version)"
echo "Django version: $(pip show django | grep Version)"

# Install required packages from requirements.txt if it exists
if [ -f requirements.txt ]; then
    pip install -r requirements.txt
else
    echo "No requirements.txt file found."
fi

# Check if Django is installed
if pip show django > /dev/null 2>&1; then
    echo "Django is installed."
else
    echo "Django is not installed."
    exit 1
fi

# Print success message
echo "Setup completed successfully."
echo "To activate the virtual environment, run: source venv/bin/activate"

# Optionally, create a Django project if none exists
if [ ! -d "myproject" ]; then
    echo "Creating Django project 'myproject'..."
    django-admin startproject myproject
    echo "Django project 'myproject' created."
else
    echo "Django project directory already exists."
fi
