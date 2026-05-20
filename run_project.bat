@echo off
setlocal

echo [INFO] Iniciando o projeto Motor50CV com Docker Compose...

where docker >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Docker nao encontrado no PATH.
  exit /b 1
)

docker compose version >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Docker Compose (plugin 'docker compose') nao disponivel.
  exit /b 1
)

echo [INFO] Subindo containers (build + detach)...
docker compose up -d --build
if errorlevel 1 (
  echo [ERRO] Falha ao subir os containers.
  exit /b 1
)

echo.
echo [INFO] Status dos servicos:
docker compose ps

echo.
echo [OK] Projeto iniciado.
echo API:     http://localhost:8000
echo Swagger: http://localhost:8000/docs
echo Grafana: http://localhost:3000
echo RabbitMQ:http://localhost:15672
echo OPC UA:  opc.tcp://localhost:4840/motor50cv/server

endlocal
