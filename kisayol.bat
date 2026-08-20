@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Depo Sayim - kisayol olustur

rem Klasorde onlarca dosya var; sayimi yapan kisi her seferinde dogru .bat
rem dosyasini aramak zorunda kalmasin diye Masaustune ve Baslat menusune
rem bukelemun ikonlu bir kisayol koyuyoruz. Baslat menusundeki kopya sayesinde
rem Windows tusuna basip "depo" yazmak da yetiyor.
rem
rem /sessiz : kurulum.bat icinden cagrilirken kullanilir - banner ve pause yok.

set "SESSIZ="
if /i "%~1"=="/sessiz" set "SESSIZ=1"

if not defined SESSIZ (
  echo.
  echo  ============================================
  echo   DEPO SAYIM - KISAYOL OLUSTUR
  echo  ============================================
  echo.
)

if not exist "baslat.bat" (
  echo  [HATA] baslat.bat bulunamadi.
  echo  Bu dosyayi proje klasorunun icinden calistirin.
  if not defined SESSIZ pause
  exit /b 1
)

set "IKON=%~dp0app.ico"
if not exist "%IKON%" (
  if not defined SESSIZ echo  [UYARI] app.ico yok, kisayol varsayilan ikonla olusacak.
  set "IKON="
)

rem Kisayol adindaki Turkce "i" (U+0131) bat dosyasinin kod sayfasina
rem takilmasin diye PowerShell tarafinda karakter kodundan uretiliyor.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$kok = '%~dp0'.TrimEnd('\');" ^
  "$i = [char]0x0131;" ^
  "$ad = 'Depo Say' + $i + 'm';" ^
  "$ikon = '%IKON%';" ^
  "$hedefler = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'));" ^
  "$kabuk = New-Object -ComObject WScript.Shell;" ^
  "foreach ($k in $hedefler) {" ^
  "  if (-not $k -or -not (Test-Path $k)) { continue }" ^
  "  $yol = Join-Path $k ($ad + '.lnk');" ^
  "  $ln = $kabuk.CreateShortcut($yol);" ^
  "  $ln.TargetPath       = Join-Path $kok 'baslat.bat';" ^
  "  $ln.WorkingDirectory = $kok;" ^
  "  $ln.Description      = $ad + ' - barkodla envanter say' + $i + 'm' + $i;" ^
  "  if ($ikon) { $ln.IconLocation = $ikon + ',0' }" ^
  "  $ln.Save();" ^
  "  Write-Host ('  olusturuldu: ' + $yol);" ^
  "}"

if errorlevel 1 (
  echo.
  echo  [HATA] Kisayol olusturulamadi.
  echo  Sirket bilgisayarinda PowerShell kisitli olabilir. O durumda elle:
  echo    baslat.bat dosyasina sag tikla ^> Kisayol olustur ^> Masaustune tasi
  echo.
  if not defined SESSIZ pause
  exit /b 1
)

if defined SESSIZ exit /b 0

echo.
echo  ============================================
echo   TAMAM
echo.
echo   Masaustunde ve Baslat menusunde
echo   "Depo Sayim" kisayolu olustu.
echo.
echo   Ipucu: kisayola sag tiklayip "Gorev cubuguna
echo   sabitle" derseniz her zaman elinizin altinda olur.
echo  ============================================
echo.
pause
