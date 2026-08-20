@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Depo Sayim - veritabanini sifirla

rem Deneme sayimlarindan kalan verileri temizler: oturumlar, okutmalar, kuyruk,
rem fotograflar, OGRENILMIS BARKODLAR, yuklenen Excel dosyalari ve raporlar.
rem Silmez, tasir: her sey data\yedek-<tarih> klasorune alinir, geri donulebilir.
rem Tiger'daki hicbir kayda dokunmaz - bu sadece bu uygulamanin kendi veritabani.

echo.
echo  ============================================
echo   VERITABANINI SIFIRLA
echo  ============================================
echo.
echo   Silinecekler (yedege tasinacak):
echo     - tum sayim oturumlari ve okutmalar
echo     - kuyruk kayitlari ve fotograflar
echo     - OGRENILMIS BARKODLAR (barkod -^> malzeme kodu tablosu)
echo     - yuklenen Excel raporlari ve uretilmis rapor dosyalari
echo.
echo   Tiger'daki verilere DOKUNULMAZ.
echo.

curl -s -o nul -m 2 http://127.0.0.1:8000/api/saglik
if not errorlevel 1 (
  echo  [DUR] Uygulama su an calisiyor. Once sunucu penceresinde Ctrl+C ile
  echo        durdurun, sonra bu dosyayi tekrar calistirin.
  echo.
  pause
  exit /b 1
)

set ONAY=
set /p ONAY=  Devam etmek icin buyuk harfle SIFIRLA yazip Enter'a basin:
if /i not "%ONAY%"=="SIFIRLA" (
  echo.
  echo  Vazgecildi, hicbir sey silinmedi.
  echo.
  pause
  exit /b 0
)

if not exist "data" (
  echo.
  echo  data klasoru zaten yok - sifirlanacak bir sey yok.
  echo.
  pause
  exit /b 0
)

for /f "delims=" %%t in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd-HHmmss"') do set TS=%%t
set YEDEK=data\yedek-%TS%
mkdir "%YEDEK%" 2>nul

for %%f in (data\*.db data\*.db-wal data\*.db-shm) do (
  if exist "%%f" move /y "%%f" "%YEDEK%\" >nul
)
if exist "data\yuklenen" move /y "data\yuklenen" "%YEDEK%\" >nul
if exist "data\rapor"    move /y "data\rapor"    "%YEDEK%\" >nul

echo.
echo  Sifirlandi. Eski veriler burada duruyor:
echo     %YEDEK%
echo.
echo  Uygulamayi baslat.bat ile actiginizda bos veritabani kendiliginden
echo  olusur; ilk ekrandan Excel raporunu yeniden yukleyin.
echo.
pause
