@echo off
cd e:\proIT
call e:\proIT\.venv\Scripts\activate.bat
python -m django --version
echo.
python -m django test people --verbosity 2
echo.
python manage.py check
echo.
Test execution complete.
pause
