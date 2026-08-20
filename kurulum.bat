@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Depo Sayim - kurulum

echo.
echo  ============================================
echo   DEPO SAYIM - KURULUM
echo   Bu adim internet baglantisi ister.
echo   Bir kez calistirmak yeterlidir.
echo.
echo   DIKKAT: Adimlar uzun surebilir (yavas disk veya antivirus
echo   taramasi varsa 10+ dakika). Ekranda bir sure hicbir sey
echo   yazmayabilir - bu normaldir. Ctrl+C ile KESMEYIN.
echo  ============================================
echo.

rem ---------------------------------------------------------------- Python
where python >nul 2>&1
if errorlevel 1 (
  echo  [HATA] Python bulunamadi.
  echo  python.org/downloads adresinden Python 3.10+ kurun,
  echo  kurulumda "Add python.exe to PATH" secenegini isaretleyin.
  echo.
  pause
  exit /b 1
)
for /f "delims=" %%v in ('python --version') do echo  Python : %%v

rem ---------------------------------------------------------------- Node
where npm >nul 2>&1
if errorlevel 1 (
  echo  [HATA] npm bulunamadi.
  echo  nodejs.org adresinden Node.js LTS kurun ve bu pencereyi kapatip
  echo  kurulum.bat dosyasini tekrar calistirin.
  echo.
  pause
  exit /b 1
)
for /f "delims=" %%v in ('node --version') do echo  Node   : %%v
echo.

rem ---------------------------------------------------------------- 1/4 venv
rem Sanal ortam, onu yaratan Python'un MUTLAK yolunu pyvenv.cfg icinde tasir.
rem Klasor USB ile baska bilgisayara kopyalanirsa .venv\Scripts\python.exe
rem yerinde durur ama calismaz ("No Python at ..."). Bu yuzden varligina degil,
rem gercekten calisip calismadigina bakiyoruz.
echo  [1/4] Python sanal ortami hazirlaniyor...
set "VENV_OK="
if exist ".venv\Scripts\python.exe" (
  .venv\Scripts\python.exe -c "import sys" >nul 2>&1
  if not errorlevel 1 set "VENV_OK=1"
)
if defined VENV_OK (
  echo        .venv calisiyor, atlaniyor.
) else (
  if exist ".venv" (
    echo        Mevcut .venv bu bilgisayarda calismiyor.
    echo        ^(Baska makineden kopyalanmis - icinde o makinenin Python yolu var.^)
    echo        Siliniyor ve sifirdan kuruluyor...
    rmdir /s /q ".venv"
  )
  echo        Sanal ortam olusturuluyor - bu adim ciktisi olmadan
  echo        birkac dakika surebilir, bekleyin...
  python -m venv .venv
  if errorlevel 1 goto :hata
  echo        Sanal ortam hazir.
)

rem ---------------------------------------------------------------- 2/3 pip
echo  [2/4] Python paketleri kuruluyor ^(fastapi, openpyxl, ...^)
.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 goto :hata

rem ---------------------------------------------------------------- 3/4 arayüz
rem tsconfig.tsbuildinfo mutlak yol tutar; baska makineden gelen bayat bir kopya
rem tsc'yi "her sey guncel" diye yaniltabilir. Silmek bedava, garanti ucuz.
if exist "web\tsconfig.tsbuildinfo" del /q "web\tsconfig.tsbuildinfo"
echo  [3/4] Arayuz derleniyor ^(npm install + build^)
cd web
echo        npm install calisiyor - ilk kurulumda uzun surer...
call npm install --no-audit --no-fund
if errorlevel 1 goto :hata_web
call npm run build
if errorlevel 1 goto :hata_web
cd ..

if not exist "app\static\index.html" goto :hata_web

rem ---------------------------------------------------------------- 4/4 kisayol
rem Klasorde onlarca dosya var; sayimi yapan kisi dogru .bat dosyasini
rem aramasin diye Masaustune ve Baslat menusune ikonlu kisayol koyuyoruz.
rem Basarisiz olmasi kurulumu bozmaz, uygulama baslat.bat ile yine calisir.
if exist "data\sayim.db" (
  echo.
  echo  [NOT] data klasorunde onceden bir veritabani var. Baska bir bilgisayardan
  echo        kopyalandiysa icinde yabanci bir sayim oturumu olabilir.
  echo        Temiz baslamak icin: sifirla.bat ^(siler degil, yedege tasir^)
  echo.
)

echo  [4/4] Masaustu kisayolu olusturuluyor...
call "%~dp0kisayol.bat" /sessiz >nul 2>&1
if errorlevel 1 (
  echo        Kisayol olusturulamadi ^(onemli degil^), baslat.bat ile acabilirsiniz.
) else (
  echo        Masaustune ve Baslat menusune "Depo Sayim" eklendi.
)

echo.
echo  ============================================
echo   KURULUM TAMAM
echo   Artik internet gerekmiyor.
echo.
echo   Baslatmak icin masaustundeki "Depo Sayim"
echo   kisayoluna cift tiklayin. ^(Ya da baslat.bat^)
echo  ============================================
echo.
choice /c EH /n /m "  Uygulamayi simdi baslatalim mi? (E/H) "
if errorlevel 2 goto :son
call "%~dp0baslat.bat"
goto :eof

:hata_web
cd /d "%~dp0"
echo.
echo  Ipucu: web\node_modules baska bir bilgisayardan kopyalandiysa icindeki
echo  derlenmis ikili dosyalar bu makineye uymaz. O klasoru silip tekrar deneyin.
:hata
echo.
echo  [HATA] Kurulum tamamlanamadi. Yukaridaki mesaji okuyun.
echo  Internet baglantisini ve varsa sirket proxy ayarlarini kontrol edin.
echo.
pause
exit /b 1

:son
echo.
echo  Hazir. baslat.bat ile calistirabilirsiniz.
ping -n 5 127.0.0.1 >nul
