Set "VIRTUAL_ENV=.venv"

If Not Exist "%VIRTUAL_ENV%\Scripts\activate.bat" (
    python -m venv %VIRTUAL_ENV%
)

If Not Exist "%VIRTUAL_ENV%\Scripts\activate.bat" Exit /B 1

Call "%VIRTUAL_ENV%\Scripts\activate.bat"
pip install -r requirements.txt
python main.py

PAUSE