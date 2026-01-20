"""
Aplicação FastAPI principal.

Este módulo define a aplicação FastAPI com todos os endpoints
e configurações para o serviço de API do Motor 50CV.
"""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routes import router as motor_router
from services import get_data_service, close_data_service
from schemas import HealthResponse

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerenciador de ciclo de vida da aplicação.
    
    Inicializa serviços no startup e limpa recursos no shutdown.
    """
    # Startup
    logger.info("Iniciando API Service...")
    
    try:
        # Inicializar serviço de dados
        await get_data_service()
        logger.info("Serviços inicializados com sucesso")
    except Exception as e:
        logger.error(f"Erro ao inicializar serviços: {e}")
        # Continuar mesmo com erro - endpoints podem funcionar parcialmente
        
    yield
    
    # Shutdown
    logger.info("Encerrando API Service...")
    await close_data_service()
    logger.info("API Service encerrado")


# Criar aplicação FastAPI
settings = get_settings()

app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar origens permitidas
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rotas
app.include_router(motor_router)


# ============== Endpoints de Saúde ==============

@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
    description="Verifica o status de saúde do serviço e suas dependências."
)
async def health_check():
    """
    Verifica status de saúde do serviço.
    
    Returns:
        HealthResponse: Status do serviço e dependências
    """
    services_status = {}
    overall_status = "healthy"
    
    # Verificar banco de dados
    try:
        service = await get_data_service()
        if service._db:
            await service._db.execute("SELECT 1")
            services_status["database"] = "connected"
        else:
            services_status["database"] = "not_connected"
            overall_status = "degraded"
    except Exception as e:
        services_status["database"] = f"error: {str(e)}"
        overall_status = "degraded"
        
    # Verificar RabbitMQ
    try:
        if service._rabbitmq_conn and not service._rabbitmq_conn.is_closed:
            services_status["rabbitmq"] = "connected"
        else:
            services_status["rabbitmq"] = "not_connected"
            overall_status = "degraded"
    except Exception as e:
        services_status["rabbitmq"] = f"error: {str(e)}"
        overall_status = "degraded"
        
    return HealthResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc),
        version=settings.api_version,
        services=services_status
    )


@app.get(
    "/",
    tags=["root"],
    summary="Informações da API",
    description="Retorna informações básicas sobre a API."
)
async def root():
    """
    Endpoint raiz com informações da API.
    
    Returns:
        Informações básicas da API
    """
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "latest": "/api/v1/motor/latest",
            "history": "/api/v1/motor/history/{variable}",
            "alarms": "/api/v1/motor/alarms",
            "variables": "/api/v1/motor/variables"
        }
    }


# ============== Error Handlers ==============

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handler global de exceções."""
    logger.error(f"Erro não tratado: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Erro interno do servidor"}
    )
