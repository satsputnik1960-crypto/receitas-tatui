@echo off
cd /d "%~dp0"
rem Cria um ambiente Python so do projeto (na primeira vez) com as mesmas versoes do site
if not exist ".venv\Scripts\python.exe" (
    echo Preparando o ambiente pela primeira vez, aguarde...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
)
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
".venv\Scripts\python.exe" -m streamlit run app.py
pause
