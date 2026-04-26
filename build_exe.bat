@echo off
REM Build after installing PyInstaller: python -m pip install pyinstaller
python -m PyInstaller --noconfirm --onefile --windowed --name QingYuReader main.py
