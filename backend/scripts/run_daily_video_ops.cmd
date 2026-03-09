@echo off
setlocal

set "BASE_DIR=C:\Users\ishit\ads_library\backend"
set "LOG_DIR=%BASE_DIR%\logs"
set "LOG_FILE=%LOG_DIR%\daily_video_ops.log"
set "LOG_BAK=%LOG_DIR%\daily_video_ops.log.1"
set "MAX_BYTES=5242880"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

rem Rotate log if it exceeds MAX_BYTES (5MB)
if exist "%LOG_FILE%" (
  for %%A in ("%LOG_FILE%") do set "LOG_SIZE=%%~zA"
  if defined LOG_SIZE (
    if %LOG_SIZE% GTR %MAX_BYTES% (
      if exist "%LOG_BAK%" del /f /q "%LOG_BAK%"
      move /y "%LOG_FILE%" "%LOG_BAK%" >nul
    )
  )
)

cd /d "%BASE_DIR%"
echo [%date% %time%] START daily_video_ops >> "%LOG_FILE%"
python -m scripts.daily_video_ops_notify --analyze-limit 50 --sample-limit 10 >> "%LOG_FILE%" 2>&1
echo [%date% %time%] END daily_video_ops >> "%LOG_FILE%"

endlocal
