# Infrastructure Orchestrator Backend

Backend API built with Django for Asset Management and Automated Resource Deployment using Terraform.  

![Python 3.10](https://img.shields.io/badge/python-3.10-yellow)
![Django 4.2](https://img.shields.io/badge/django-4.2-purple)

## Commands

### Setting Up the Environment
To set up the environment, run the following command:
```sh
bash ./bin/setup.sh
```
To activate the virtual environment, run: 
```sh
source venv/bin/activate
```
### Linting
To check the code for style guide enforcement and linting errors, use:
```sh
flake8
```
To format code, run:
```sh
black .
```
To sort imports, run:
```sh
isort .
```

### Testing
To run the tests, use:
```sh
python manage.py test
```
To run tests with coverage, use:
```sh
coverage run manage.py test
```

### Starting the App
To start the application, execute:
```sh
python manage.py runserver
```
