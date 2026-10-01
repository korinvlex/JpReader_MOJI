@echo off
REM JpReader 打包脚本（Windows）
REM 需要 Python 3.11 / 3.12（mobi 库依赖 imghdr，3.13+ 已移除该标准库）

setlocal

echo [1/3] 安装依赖...
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto :fail

echo [2/3] 清理旧构建...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist JpReader.spec del /q JpReader.spec

echo [3/3] 开始打包...
pyinstaller --noconfirm --onefile --windowed ^
  --name JpReader ^
  --icon assets\icon.ico ^
  --add-data "assets;assets" ^
  --collect-all ebooklib ^
  --collect-all mobi ^
  main.py
if errorlevel 1 goto :fail

echo.
echo 打包完成：dist\JpReader.exe
pause
exit /b 0

:fail
echo.
echo 打包失败，请检查上方错误信息。
pause
exit /b 1
