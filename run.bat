@echo off
setlocal EnableExtensions
title SatyaSpandan launcher
cd /d "%~dp0"

rem ---------------------------------------------------------------
rem  SatyaSpandan launcher
rem    run.bat          start API + website (dev mode) and open browser
rem    run.bat prod     build the website and run the production server (use for the live demo)
rem    run.bat test     run the synthetic test suite only
rem    run.bat report [folder]
rem                     write accuracy_report.html and open it; optional folder with real\ and fake\ clips
rem ---------------------------------------------------------------

set "MODE=%~1"
if "%MODE%"=="" set "MODE=dev"
set "ENV_NAME=satya"
set "MODEL=backend\models\face_landmarker.task"
set "MODEL_URL=https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"

rem ---- 1. Find conda and the "satya" Python environment ------------
set "CONDA_BASE="
for /f "delims=" %%i in ('conda info --base 2^>nul') do set "CONDA_BASE=%%i"
if not defined CONDA_BASE if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe" set "CONDA_BASE=%USERPROFILE%\anaconda3"
if not defined CONDA_BASE if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe" set "CONDA_BASE=%USERPROFILE%\miniconda3"
if not defined CONDA_BASE (
    echo [ERROR] Could not find conda. Install Anaconda or Miniconda first.
    goto :fail
)
set "PY=%CONDA_BASE%\envs\%ENV_NAME%\python.exe"

if not exist "%PY%" (
    echo [setup] Creating conda environment "%ENV_NAME%" with Python 3.11 ...
    call "%CONDA_BASE%\Scripts\conda.exe" create -n %ENV_NAME% python=3.11 -y || goto :fail
    echo [setup] Installing Python packages ...
    "%PY%" -m pip install -r backend\requirements.txt || goto :fail
)

"%PY%" -c "import cv2, mediapipe, scipy, fastapi" >nul 2>&1
if errorlevel 1 (
    echo [setup] Installing missing Python packages ...
    "%PY%" -m pip install -r backend\requirements.txt || goto :fail
)

rem ---- 2. MediaPipe face model ---------------------------------------
if not exist "%MODEL%" (
    echo [setup] Downloading MediaPipe face landmarker model ...
    if not exist backend\models mkdir backend\models
    curl -L -o "%MODEL%" "%MODEL_URL%" || goto :fail
)

rem ---- Test mode ----------------------------------------------------
if /i "%MODE%"=="test" goto :test
if /i "%MODE%"=="report" goto :report

rem ---- 3. Node.js and website packages ------------------------------
where node >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found. Install Node 22 LTS from https://nodejs.org
    goto :fail
)
if not exist web\node_modules (
    echo [setup] Installing website packages ...
    pushd web
    call npm install || (popd & goto :fail)
    popd
)

rem ---- 4. Make sure the ports are free ------------------------------
for %%P in (8000 3000) do (
    netstat -ano | findstr /r /c:":%%P .*LISTENING" >nul && (
        echo [WARN] Port %%P is already in use. Close the other SatyaSpandan windows first.
        goto :fail
    )
)

rem ---- 5. Start the API in its own window ---------------------------
echo [run] Starting analysis API on http://localhost:8000 ...
start "SatyaSpandan API (close to stop)" /d "%~dp0backend" cmd /k ""%PY%" -m uvicorn api:app --port 8000"

rem wait until the API answers (max ~60 s)
set /a TRIES=0
:wait_api
set /a TRIES+=1
curl -s http://127.0.0.1:8000/api/health >nul 2>&1 && goto :api_up
if %TRIES% GEQ 60 (
    echo [ERROR] The API did not start. Check the "SatyaSpandan API" window for errors.
    goto :fail
)
timeout /t 1 /nobreak >nul
goto :wait_api
:api_up
echo [run] API is up.

rem ---- 6. Start the website in its own window -----------------------
if /i "%MODE%"=="prod" (
    echo [run] Building website for production ...
    pushd web
    call npm run build || (popd & goto :fail)
    popd
    start "SatyaSpandan Web (close to stop)" /d "%~dp0web" cmd /k "npm start"
) else (
    start "SatyaSpandan Web (close to stop)" /d "%~dp0web" cmd /k "npm run dev"
)

set /a TRIES=0
:wait_web
set /a TRIES+=1
curl -s -o nul http://127.0.0.1:3000/ >nul 2>&1 && goto :web_up
if %TRIES% GEQ 90 (
    echo [ERROR] The website did not start. Check the "SatyaSpandan Web" window for errors.
    goto :fail
)
timeout /t 1 /nobreak >nul
goto :wait_web
:web_up

echo.
echo ============================================================
echo   SatyaSpandan is running
echo     Website : http://localhost:3000
echo     API docs: http://localhost:8000/docs
echo   Close the two "SatyaSpandan" windows to stop it.
echo ============================================================
start "" http://localhost:3000
exit /b 0

:test
pushd backend
"%PY%" demo_test.py
set "RC=%ERRORLEVEL%"
popd
pause
exit /b %RC%

:report
set "VIDEOS=%~f2"
pushd backend
if defined VIDEOS (
    echo [report] Synthetic tests + clips in "%VIDEOS%" ...
    "%PY%" tools\accuracy_report.py --videos "%VIDEOS%"
) else (
    echo [report] Synthetic tests only. Add a folder with real\ and fake\ clips to include real videos.
    "%PY%" tools\accuracy_report.py
)
set "RC=%ERRORLEVEL%"
popd
if "%RC%"=="0" start "" "%~dp0accuracy_report.html"
exit /b %RC%

:fail
echo.
echo Launch failed. See the messages above.
pause
exit /b 1
