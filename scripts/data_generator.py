#!/usr/bin/env python3
"""
Gerador de dados simulados para testes.

Este script gera dados JSON no mesmo formato dos sensores reais
para testar o sistema sem depender do broker MQTT externo.
"""

import asyncio
import json
import random
import logging
from datetime import datetime
from typing import Dict, Any

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataGenerator:
    """
    Gerador de dados simulados para os sensores do motor.
    
    Gera dados realistas com variações aleatórias para testar
    o fluxo completo do sistema.
    """
    
    # Valores nominais
    NOMINAL_VOLTAGE = 220.0
    NOMINAL_CURRENT = 10.0
    NOMINAL_FREQUENCY = 60.0
    NOMINAL_POWER_FACTOR = 0.95
    
    def __init__(self):
        """Inicializa o gerador."""
        self.connection = None
        self.channel = None
        self.exchange = None
        
    async def connect(self, host: str = "localhost", port: int = 5672):
        """
        Conecta ao RabbitMQ.
        
        Args:
            host: Host do RabbitMQ
            port: Porta do RabbitMQ
        """
        url = f"amqp://admin:admin123@{host}:{port}/"
        
        self.connection = await aio_pika.connect_robust(url)
        self.channel = await self.connection.channel()
        
        # Declarar exchange
        self.exchange = await self.channel.declare_exchange(
            "motor_data",
            ExchangeType.TOPIC,
            durable=True
        )
        
        logger.info(f"Conectado ao RabbitMQ: {host}:{port}")
        
    async def close(self):
        """Fecha conexão com RabbitMQ."""
        if self.connection:
            await self.connection.close()
            
    def generate_electrical(self) -> Dict[str, Any]:
        """
        Gera dados do sensor elétrico.
        
        Returns:
            Dicionário com dados elétricos simulados
        """
        # Variação de ±5% nos valores nominais
        voltage_var = random.uniform(-0.05, 0.05)
        current_var = random.uniform(-0.05, 0.05)
        
        voltage_a = self.NOMINAL_VOLTAGE * (1 + voltage_var + random.uniform(-0.01, 0.01))
        voltage_b = self.NOMINAL_VOLTAGE * (1 + voltage_var + random.uniform(-0.01, 0.01))
        voltage_c = self.NOMINAL_VOLTAGE * (1 + voltage_var + random.uniform(-0.01, 0.01))
        
        current_a = self.NOMINAL_CURRENT * (1 + current_var + random.uniform(-0.02, 0.02))
        current_b = self.NOMINAL_CURRENT * (1 + current_var + random.uniform(-0.02, 0.02))
        current_c = self.NOMINAL_CURRENT * (1 + current_var + random.uniform(-0.02, 0.02))
        
        # Calcular potências
        avg_voltage = (voltage_a + voltage_b + voltage_c) / 3
        avg_current = (current_a + current_b + current_c) / 3
        power_factor = self.NOMINAL_POWER_FACTOR + random.uniform(-0.03, 0.03)
        
        apparent_power = 1.732 * avg_voltage * avg_current  # Trifásico
        active_power = apparent_power * power_factor
        reactive_power = apparent_power * (1 - power_factor**2)**0.5
        
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "voltage": {
                "a": round(voltage_a, 1),
                "b": round(voltage_b, 1),
                "c": round(voltage_c, 1)
            },
            "current": {
                "a": round(current_a, 2),
                "b": round(current_b, 2),
                "c": round(current_c, 2)
            },
            "power": {
                "active": round(active_power, 0),
                "reactive": round(reactive_power, 0),
                "apparent": round(apparent_power, 0)
            },
            "energy": {
                "active": round(random.uniform(10000, 15000), 0),
                "reactive": round(random.uniform(1000, 2000), 0),
                "apparent": round(random.uniform(10500, 15500), 0)
            },
            "powerFactor": round(power_factor, 2),
            "frequency": round(self.NOMINAL_FREQUENCY + random.uniform(-0.1, 0.1), 1)
        }
        
    def generate_environment(self, simulate_alarm: bool = False) -> Dict[str, Any]:
        """
        Gera dados do sensor ambiental.
        
        Args:
            simulate_alarm: Se True, gera temperatura crítica
            
        Returns:
            Dicionário com dados ambientais simulados
        """
        base_temp = 45.0 if not simulate_alarm else 65.0
        
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "temperature": round(random.uniform(25, 35), 1),
            "humidity": round(random.uniform(40, 70), 1),
            "caseTemperature": round(base_temp + random.uniform(-5, 5), 1)
        }
        
    def generate_vibration(self) -> Dict[str, Any]:
        """
        Gera dados do sensor de vibração.
        
        Returns:
            Dicionário com dados de vibração simulados
        """
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "axial": round(random.uniform(0.05, 0.25), 3),
            "radial": round(random.uniform(0.05, 0.30), 3)
        }
        
    async def publish(self, sensor_type: str, data: Dict[str, Any]):
        """
        Publica dados no RabbitMQ.
        
        Args:
            sensor_type: Tipo do sensor
            data: Dados a publicar
        """
        if not self.exchange:
            raise RuntimeError("Não conectado ao RabbitMQ")
            
        # Adicionar metadados
        data['_sensor_type'] = sensor_type
        data['_received_at'] = datetime.utcnow().isoformat()
        
        message = Message(
            body=json.dumps(data).encode(),
            delivery_mode=DeliveryMode.PERSISTENT,
            content_type="application/json"
        )
        
        routing_key = f"motor.{sensor_type}"
        await self.exchange.publish(message, routing_key=routing_key)
        
        logger.debug(f"Publicado: {sensor_type}")
        
    async def run(
        self,
        duration_seconds: int = 60,
        electrical_interval: float = 5.0,
        environment_interval: float = 5.0,
        vibration_interval: float = 60.0,
        simulate_alarm: bool = False
    ):
        """
        Executa geração de dados por um período.
        
        Args:
            duration_seconds: Duração em segundos
            electrical_interval: Intervalo para dados elétricos
            environment_interval: Intervalo para dados ambientais
            vibration_interval: Intervalo para dados de vibração
            simulate_alarm: Se True, simula alarme de temperatura
        """
        start_time = asyncio.get_event_loop().time()
        
        electrical_last = 0
        environment_last = 0
        vibration_last = 0
        
        logger.info(f"Gerando dados por {duration_seconds} segundos...")
        
        while asyncio.get_event_loop().time() - start_time < duration_seconds:
            current_time = asyncio.get_event_loop().time()
            
            # Dados elétricos
            if current_time - electrical_last >= electrical_interval:
                data = self.generate_electrical()
                await self.publish("electrical", data)
                electrical_last = current_time
                logger.info(f"Elétrico: V={data['voltage']['a']:.1f}V, I={data['current']['a']:.2f}A")
                
            # Dados ambientais
            if current_time - environment_last >= environment_interval:
                data = self.generate_environment(simulate_alarm)
                await self.publish("environment", data)
                environment_last = current_time
                logger.info(f"Ambiente: T={data['caseTemperature']:.1f}°C")
                
            # Dados de vibração
            if current_time - vibration_last >= vibration_interval:
                data = self.generate_vibration()
                await self.publish("vibration", data)
                vibration_last = current_time
                logger.info(f"Vibração: Axial={data['axial']:.3f}, Radial={data['radial']:.3f}")
                
            await asyncio.sleep(0.5)
            
        logger.info("Geração de dados finalizada")


async def main():
    """Função principal."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Gerador de dados simulados")
    parser.add_argument("--host", default="localhost", help="Host do RabbitMQ")
    parser.add_argument("--port", type=int, default=5672, help="Porta do RabbitMQ")
    parser.add_argument("--duration", type=int, default=60, help="Duração em segundos")
    parser.add_argument("--alarm", action="store_true", help="Simular alarme de temperatura")
    
    args = parser.parse_args()
    
    generator = DataGenerator()
    
    try:
        await generator.connect(args.host, args.port)
        await generator.run(
            duration_seconds=args.duration,
            simulate_alarm=args.alarm
        )
    finally:
        await generator.close()


if __name__ == "__main__":
    asyncio.run(main())
