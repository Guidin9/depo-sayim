@echo off
cd /d "%~dp0"
set PORT=8000
set TELEFON=
for /f "delims=" %%a in ('.venv\Scripts\python.exe -c "from app.main import _ag_adresleri as f; a=f(%PORT%); print(a[0]+'/telefon' if a else '-')" 2^>nul') do set TELEFON=%%a
echo TELEFON=[%TELEFON%]
