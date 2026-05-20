$ErrorActionPreference = "Stop"

Write-Host "[INFO] Parando o projeto Motor50CV..."

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker nao encontrado no PATH."
}

docker compose down

Write-Host "[OK] Projeto parado com sucesso."
