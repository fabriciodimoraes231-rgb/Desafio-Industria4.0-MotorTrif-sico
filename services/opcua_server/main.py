"""
Ponto de entrada principal do servidor OPC UA.

Este módulo inicializa e executa o servidor OPC UA completo
para monitoramento do motor 50CV.
"""

import asyncio
import logging
import signal
import sys

from server import OPCUAServer

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


async def main():
    """
    Função principal de execução do servidor OPC UA.
    
    Inicializa o servidor e mantém rodando até receber sinal de parada.
    """
    server = OPCUAServer()
    
    # Configurar handlers de sinal para shutdown graceful
    loop = asyncio.get_event_loop()
    shutdown_event = asyncio.Event()
    
    def signal_handler():
        logger.info("Sinal de interrupção recebido")
        shutdown_event.set()
        
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)
        
    try:
        # Inicializar e iniciar servidor
        await server.initialize()
        await server.start()
        
        # Aguardar sinal de parada
        await shutdown_event.wait()
        
    except KeyboardInterrupt:
        logger.info("Interrupção por teclado")
    except Exception as e:
        logger.error(f"Erro fatal: {e}")
        raise
    finally:
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
