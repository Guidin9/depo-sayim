@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Depo Sayim - sunucu

set PORT=8000
set URL=http://127.0.0.1:%PORT%

rem Sadece varligina degil, calisip calismadigina bakiyoruz: klasor baska
rem bilgisayardan kopyalandiysa .venv yerinde durur ama icindeki mutlak Python
rem yolu tutmaz ve "No Python at ..." hatasi verir.
set "VENV_OK="
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -c "import sys" >nul 2>&1
  if not errorlevel 1 set "VENV_OK=1"
)
if not defined VENV_OK (
  echo.
  if exist ".venv" (
    echo  [HATA] .venv var ama bu bilgisayarda calismiyor.
    echo  Klasor baska bir makineden kopyalanmis olabilir.
  ) else (
    echo  [HATA] .venv klasoru yok.
  )
  echo.
  echo  Cozum: kurulum.bat calistirin. ^(Bozuk .venv'i kendisi siler.^)
  echo.
  pause
  exit /b 1
)

if not exist "app\static\index.html" (
  echo.
  echo  [HATA] Arayuz derlenmemis. Once web klasorunde:
  echo.
  echo     cd web
  echo     npm install
  echo     npm run build
  echo.
  pause
  exit /b 1
)

rem Uygulama zaten acikse ikinci sunucu baslatma, sadece tarayiciyi ac.
curl -s -o nul -m 2 %URL%/api/saglik
if not errorlevel 1 (
  echo.
  echo  Uygulama zaten calisiyor. Tarayici aciliyor: %URL%
  start "" %URL%
  ping -n 3 127.0.0.1 >nul
  exit /b 0
)

rem Telefonun baglanacagi adres. Laptopta sanal ag kartlari da IP tasir
rem (Hyper-V / VirtualBox); asagidaki yardimci gercek Wi-Fi adresini basa alir.
set TELEFON=
for /f "delims=" %%a in ('.venv\Scripts\python.exe -c "from app.main import _ag_adresleri as f; a=f(%PORT%); print(a[0]+'/telefon' if a else 'ag adresi bulunamadi')" 2^>nul') do set TELEFON=%%a

rem Sunucu ayaga kalkinca tarayiciyi acan arka plan bekleyicisi.
start "" /b cmd /c "for /l %%i in (1,1,40) do (curl -s -o nul -m 1 %URL%/api/saglik && (start "" %URL% & exit /b) || ping -n 2 127.0.0.1 >nul)"

echo.
echo  ============================================
echo   DEPO SAYIM
echo.
echo   Bu laptoptan : %URL%
echo   Telefondan   : %TELEFON%
echo.
echo   Telefonu baglamak icin sayim ekranindaki
echo   [Telefon] dugmesine bas, cikan QR kodu
echo   telefon kamerasiyla okut. Telefon ayni
echo   Wi-Fi'da olmali.
echo  ============================================
echo.
echo   UYARI: Uygulama ayni agdaki herkese aciktir, sifre yoktur.
echo   Sadece guvendiginiz depo aginda kullanin.
echo.
echo   Durdurmak icin: bu pencerede Ctrl+C
echo   (Pencereyi kapatmak da sunucuyu durdurur)
echo.

rem 0.0.0.0: hem laptop hem telefon ayni sunucuya baglanir.
.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port %PORT%

echo.
echo  Sunucu durdu.
ping -n 4 127.0.0.1 >nul
