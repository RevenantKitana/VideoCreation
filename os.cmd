@echo off
rem Windows wrapper: runs run.py inside this folder's own toolchain (.pixi), nothing global.
setlocal
cd /d "%~dp0"
set "PIXI_HOME=%~dp0.tools\pixi-home"
"%~dp0.tools\pixi.exe" run --quiet python run.py %*
