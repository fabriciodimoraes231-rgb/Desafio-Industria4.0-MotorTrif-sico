Param(
    [switch]$WithProducer
)

$ErrorActionPreference = "Stop"

Write-Host "[INFO] Iniciando o projeto Motor50CV com Docker Compose..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker nao encontrado no PATH."
}

$composeCmd = "docker compose"
try {
    docker compose version | Out-Null
} catch {
    throw "Docker Compose (plugin 'docker compose') nao disponivel."
}

if ($WithProducer) {
    Write-Host "[INFO] Subindo containers com profile 'producer' (build + detach)..."
    docker compose --profile producer up -d --build
} else {
    Write-Host "[INFO] Subindo containers (build + detach)..."
    docker compose up -d --build
}

Write-Host ""
Write-Host "[INFO] Status dos servicos:"
docker compose ps

Write-Host ""
Write-Host "[OK] Projeto iniciado."
Write-Host "API:      http://localhost:8000"
Write-Host "Swagger:  http://localhost:8000/docs"
Write-Host "Grafana:  http://localhost:3000"
Write-Host "RabbitMQ: http://localhost:15672"
Write-Host "OPC UA:   opc.tcp://localhost:4840/motor50cv/server"
