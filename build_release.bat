@echo off
REM build_release.bat — 一键构建发布版
REM
REM 顺序很重要：版本号 -> 例句挂载 -> 质检 -> 打包
REM 漏掉任何一步都会导致发布产物与源码不一致。
REM
REM 用法：build_release.bat 1.0.0

setlocal
set VER=%1
if "%VER%"=="" (
  echo 用法: build_release.bat ^<版本号^>  例如 build_release.bat 1.0.0
  exit /b 1
)

echo ============================================
echo  漢法辭典 構建 v%VER%
echo ============================================

cd /d "%~dp0"

echo.
echo [1/6] 掛載例句（音標 + 聯誦）
python tools\apply_examples.py
if errorlevel 1 goto fail

echo.
echo [2/6] 設置版本號
python tools\set_version.py %VER%
if errorlevel 1 goto fail

echo.
echo [3/6] 影像標查詢詞典（若 Lexique 更新過）
REM 平時可跳過；僅在原始數據變動時需要
if exist "..\..\02_数据管线\原始数据\Lexique383.tsv" (
  python tools\build_ipa_dict.py
)

echo.
echo [4/6] 質量檢查
python tools\qa_check.py
if errorlevel 1 goto fail

echo.
echo [5/6] 聯誦 / 音標查詢 / i18n 測試
node tools\test_liaison.js
if errorlevel 1 goto fail
node tools\test_ipa_query.js
if errorlevel 1 goto fail
node tools\check_i18n.js
if errorlevel 1 goto fail

echo.
echo [6/6] 打包 Windows
call npx electron-builder --win nsis --config.directories.output=release-out
if errorlevel 1 goto fail

echo.
echo ============================================
echo  構建完成：release-out\HanFrDict-setup.exe
echo ============================================
goto end

:fail
echo.
echo *** 構建失敗，已中止 ***
exit /b 1

:end
endlocal