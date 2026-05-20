@echo off
setlocal

echo [INFO] Parando o projeto Motor50CV...

where docker >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Docker nao encontrado no PATH.
  exit /b 1
)

docker compose down
if errorlevel 1 (
  echo [ERRO] Falha ao parar os containers.
  exit /b 1
)

echo [OK] Projeto parado com sucesso.
endlocal
