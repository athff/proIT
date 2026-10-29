@echo off
cd e:\proIT
e:\proIT\.venv\Scripts\python.exe -m django test people --verbosity 2
echo.
echo Test execution complete.
pause