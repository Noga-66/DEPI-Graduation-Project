@echo off
echo  Initializing Depi-Grid Infrastructure


mkdir data\raw 2>nul
mkdir data\cleaned 2>nul
mkdir notebooks 2>nul
mkdir knowledge_base\manuals 2>nul
mkdir src\simulation 2>nul
mkdir src\api 2>nul


type nul > docker-compose.yml
type nul > requirements.txt
type nul > notebooks\data_cleaning.ipynb
type nul > knowledge_base\extract_text.py
type nul > src\simulation\sender.py
type nul > src\simulation\receiver.py
type nul > src\api\main.py


echo # Python ^& Environments> .gitignore
echo __pycache__/>> .gitignore
echo *.pyc>> .gitignore
echo venv/>> .gitignore
echo env/>> .gitignore
echo .env>> .gitignore
echo.>> .gitignore
echo # MacOS/Windows Junk>> .gitignore
echo .DS_Store>> .gitignore
echo Thumbs.db>> .gitignore
echo.>> .gitignore
echo # Data Sourcing (Protect GitHub from massive Kaggle datasets)>> .gitignore
echo data/raw/*>> .gitignore
echo data/cleaned/*>> .gitignore
echo !data/.gitkeep>> .gitignore
echo.>> .gitignore
echo # Knowledge Base (Keep PDFs local)>> .gitignore
echo knowledge_base/manuals/*.pdf>> .gitignore
echo !knowledge_base/manuals/.gitkeep>> .gitignore


type nul > data\raw\.gitkeep
type nul > data\cleaned\.gitkeep
type nul > knowledge_base\manuals\.gitkeep

echo  Depi-Grid is Complete
pause