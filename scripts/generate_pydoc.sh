#!/bin/bash
# Script para gerar documentacao Pydoc HTML
# Execute na raiz do projeto: ./scripts/generate_pydoc.sh

set -e

echo "Gerando documentacao Pydoc..."

# Criar diretorio de saida
mkdir -p docs/pydoc

# Adicionar servicos ao PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(pwd)/services/api_service:$(pwd)/services/mqtt_ingestor:$(pwd)/services/opcua_server"

# Gerar documentacao do api_service
echo "Gerando docs do api_service..."
cd services/api_service
python -m pydoc -w app routes schemas services config 2>/dev/null || true
mv *.html ../../docs/pydoc/ 2>/dev/null || true
cd ../..

# Gerar documentacao do mqtt_ingestor
echo "Gerando docs do mqtt_ingestor..."
cd services/mqtt_ingestor
python -m pydoc -w main mqtt_client rabbitmq_publisher validators config 2>/dev/null || true
mv *.html ../../docs/pydoc/ 2>/dev/null || true
cd ../..

# Gerar documentacao do opcua_server
echo "Gerando docs do opcua_server..."
cd services/opcua_server
python -m pydoc -w main server nodeset alarms history_storage rabbitmq_consumer config 2>/dev/null || true
mv *.html ../../docs/pydoc/ 2>/dev/null || true
cd ../..

echo ""
echo "Documentacao gerada em: docs/pydoc/"
echo "Arquivos:"
ls -la docs/pydoc/

echo ""
echo "Para visualizar, abra os arquivos HTML no navegador"
echo "Ou execute: python -m http.server 8080 -d docs/pydoc"
