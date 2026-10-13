@echo off
:: Daily crawl + flatten, run by Windows Task Scheduler (task name "ClashLab daily collect").
:: Uses the clash env's python directly, so no conda activation is needed.
:: Output is appended to data\logs\collect.log.

set PROJECT=%~dp0..
set PY=%USERPROFILE%\anaconda3\envs\clash\python.exe
set LOG=%PROJECT%\data\logs\collect.log

cd /d "%PROJECT%"
if not exist data\logs mkdir data\logs

echo ==== %DATE% %TIME% >> "%LOG%"
"%PY%" -m clashlab.collect --max-players 3000 --leaderboards 15 >> "%LOG%" 2>&1
"%PY%" -m clashlab.flatten >> "%LOG%" 2>&1
echo ==== done %DATE% %TIME% >> "%LOG%"
