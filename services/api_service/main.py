"""
Ponto de entrada principal do serviço de API.

Este módulo inicializa e executa o servidor FastAPI
para a API REST do Motor 50CV.
"""

import uvicorn
from config import get_settings


def main():
    """
    Função principal de execução do servidor FastAPI.
    
    Inicia o servidor Uvicorn com as configurações apropriadas.
    """
    settings = get_settings()
    
    uvicorn.run(
        "app:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
        log_level="info"
    )


if __name__ == "__main__":
    main()
