@echo off
cd e:\proIT
SET DJANGO_SETTINGS_MODULE=config.settings
call e:\proIT\.venv\Scripts\activate.bat
python -m django --version
echo.
python manage.py test people --verbosity 2
echo.
python manage.py check
echo.
Test execution complete.
pause