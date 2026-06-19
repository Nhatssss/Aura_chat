@echo off
chcp 65001 > nul
title AURA CHAT SERVER
echo.
echo  ===================================================
echo    AURA CHAT - He thong chat da nguoi dung
echo  ===================================================
echo.
echo  [1/2] Cai dat thu vien Python...
pip install flask flask-socketio --quiet
echo.
echo  [2/2] Khoi dong server...
echo  Mo trinh duyet tai: http://localhost:5000
echo  Nhan Ctrl+C de dung server
echo.
python app.py
pause
