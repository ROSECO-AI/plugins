@echo off
setlocal
set "VITRO_LOCAL_HOME=%USERPROFILE%\.codex\plugins\vitro-cad-local-mcp"
if not exist "%VITRO_LOCAL_HOME%\runtime\active\python.exe" (
  echo Run the Vitro-CAD installer before starting the MCP server. 1>&2
  exit /b 1
)
"%VITRO_LOCAL_HOME%\runtime\active\python.exe" "%VITRO_LOCAL_HOME%\server\mcp_server.py"
exit /b %ERRORLEVEL%
