#!/usr/bin/env python3
"""
MQTT Producer - Gerador de dados simulados para o Motor 50CV.

Este script gera dados aleatórios (normais e de alarme) e envia
para o broker MQTT para testar o sistema de monitoramento.

Uso:
    python mqtt_producer.py [--alarm-rate 0.1] [--interval 1.0]

Argumentos:
    --alarm-rate: Probabilidade de gerar valores de alarme (0.0 a 1.0, padrão: 0.1)
    --interval: Intervalo entre mensagens em segundos (padrão: 1.0)
    --host: Host do broker MQTT (padrão: lse.dev.br)
    --port: Porta do broker MQTT (padrão: 1883)
"""

import asyncio
import argparse
import json
import os
import random
import signal
import sys
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Any, Optional

try:
    from gmqtt import Client as MQTTClient
    from gmqtt.mqtt.constants import MQTTv311
except ImportError:
    print("Erro: gmqtt não instalado. Execute: pip install gmqtt")
    sys.exit(1)


# ============== Configurações ==============

@dataclass
class ProducerConfig:
    """Configurações do producer."""
    mqtt_host: str = "lse.dev.br"
    mqtt_port: int = 1883
    client_id: str = "motor50cv_producer"
    
    # Tópicos MQTT (mesmos que o mqtt-ingestor escuta)
    topic_electrical: str = "scgdi/motor/electrical"
    topic_environment: str = "scgdi/motor/environment"
    topic_vibration: str = "scgdi/motor/vibration"
    
    # Valores nominais
    nominal_voltage: float = 220.0
    nominal_current: float = 10.0
    nominal_frequency: float = 60.0
    nominal_power_factor: float = 0.92
    
    # Limites de alarme
    voltage_deviation: float = 0.10  # ±10%
    current_deviation: float = 0.10  # ±10%
    max_case_temperature: float = 60.0  # °C
    
    # Faixas normais
    ambient_temp_range: tuple = (25.0, 40.0)
    humidity_range: tuple = (40.0, 70.0)
    case_temp_range: tuple = (35.0, 55.0)
    vibration_range: tuple = (0.05, 0.20)


# ============== Geradores de Dados ==============

class DataGenerator:
    """Gerador de dados simulados para o motor."""
    
    def __init__(self, config: ProducerConfig, alarm_rate: float = 0.1):
        self.config = config
        self.alarm_rate = alarm_rate
        
        # Estado acumulado (energia)
        self._energy_active = random.uniform(10000, 50000)
        self._energy_reactive = random.uniform(1000, 5000)
        self._energy_apparent = random.uniform(10000, 55000)
        
    def should_generate_alarm(self) -> bool:
        """Decide se deve gerar valor de alarme."""
        return random.random() < self.alarm_rate
    
    def generate_electrical(self) -> Dict[str, Any]:
        """Gera dados elétricos."""
        cfg = self.config
        is_alarm = self.should_generate_alarm()
        
        if is_alarm:
            # Gerar algum tipo de alarme elétrico
            alarm_type = random.choice(["overvoltage", "undervoltage", "overcurrent"])
            
            if alarm_type == "overvoltage":
                # Sobretensão: >110% do nominal
                voltage_factor = random.uniform(1.12, 1.20)
                voltage_a = cfg.nominal_voltage * voltage_factor
                voltage_b = cfg.nominal_voltage * random.uniform(0.98, 1.02)
                voltage_c = cfg.nominal_voltage * random.uniform(0.98, 1.02)
            elif alarm_type == "undervoltage":
                # Subtensão: <90% do nominal
                voltage_factor = random.uniform(0.80, 0.88)
                voltage_a = cfg.nominal_voltage * voltage_factor
                voltage_b = cfg.nominal_voltage * random.uniform(0.98, 1.02)
                voltage_c = cfg.nominal_voltage * random.uniform(0.98, 1.02)
            else:  # overcurrent
                voltage_a = cfg.nominal_voltage * random.uniform(0.98, 1.02)
                voltage_b = cfg.nominal_voltage * random.uniform(0.98, 1.02)
                voltage_c = cfg.nominal_voltage * random.uniform(0.98, 1.02)
        else:
            # Valores normais de tensão (±5% do nominal)
            voltage_a = cfg.nominal_voltage * random.uniform(0.95, 1.05)
            voltage_b = cfg.nominal_voltage * random.uniform(0.95, 1.05)
            voltage_c = cfg.nominal_voltage * random.uniform(0.95, 1.05)
        
        # Corrente
        if is_alarm and alarm_type == "overcurrent":
            # Sobrecorrente: >110% do nominal
            current_factor = random.uniform(1.12, 1.25)
            current_a = cfg.nominal_current * current_factor
        else:
            current_a = cfg.nominal_current * random.uniform(0.90, 1.05)
        
        current_b = cfg.nominal_current * random.uniform(0.90, 1.05)
        current_c = cfg.nominal_current * random.uniform(0.90, 1.05)
        
        # Potência
        power_active = random.uniform(4000, 5500)
        power_reactive = random.uniform(400, 800)
        power_apparent = (power_active**2 + power_reactive**2)**0.5
        
        # Energia (acumulativa)
        self._energy_active += power_active * 0.001  # kWh
        self._energy_reactive += power_reactive * 0.001
        self._energy_apparent += power_apparent * 0.001
        
        # Power factor e frequência
        power_factor = random.uniform(0.88, 0.98)
        frequency = cfg.nominal_frequency + random.uniform(-0.5, 0.5)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "voltage": {
                "a": round(voltage_a, 2),
                "b": round(voltage_b, 2),
                "c": round(voltage_c, 2)
            },
            "current": {
                "a": round(current_a, 2),
                "b": round(current_b, 2),
                "c": round(current_c, 2)
            },
            "power": {
                "active": round(power_active, 2),
                "reactive": round(power_reactive, 2),
                "apparent": round(power_apparent, 2)
            },
            "energy": {
                "active": round(self._energy_active, 2),
                "reactive": round(self._energy_reactive, 2),
                "apparent": round(self._energy_apparent, 2)
            },
            "powerFactor": round(power_factor, 3),
            "frequency": round(frequency, 2)
        }
    
    def generate_environment(self) -> Dict[str, Any]:
        """Gera dados ambientais."""
        cfg = self.config
        is_alarm = self.should_generate_alarm()
        
        # Temperatura ambiente (nunca gera alarme direto)
        temperature = random.uniform(*cfg.ambient_temp_range)
        
        # Umidade
        humidity = random.uniform(*cfg.humidity_range)
        
        # Temperatura da carcaça
        if is_alarm:
            # Alarme: temperatura acima de 60°C
            case_temperature = random.uniform(62.0, 80.0)
        else:
            # Normal: entre 35°C e 55°C
            case_temperature = random.uniform(*cfg.case_temp_range)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "caseTemperature": round(case_temperature, 1)
        }
    
    def generate_vibration(self) -> Dict[str, Any]:
        """Gera dados de vibração."""
        cfg = self.config
        is_alarm = self.should_generate_alarm()
        
        if is_alarm:
            # Alarme: vibração alta (acima de 0.5 mm/s)
            axial = random.uniform(0.5, 1.5)
            radial = random.uniform(0.5, 1.5)
        else:
            # Normal
            axial = random.uniform(*cfg.vibration_range)
            radial = random.uniform(*cfg.vibration_range)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "axial": round(axial, 3),
            "radial": round(radial, 3)
        }


# ============== MQTT Producer ==============

class MQTTProducer:
    """Producer MQTT para envio de dados simulados."""
    
    def __init__(self, config: ProducerConfig, generator: DataGenerator):
        self.config = config
        self.generator = generator
        self.client: Optional[MQTTClient] = None
        self._running = False
        self._connected = False
        
    def _on_connect(self, client, flags, rc, properties):
        """Callback de conexão."""
        if rc == 0:
            self._connected = True
            print(f"✅ Conectado ao broker MQTT: {self.config.mqtt_host}:{self.config.mqtt_port}")
        else:
            print(f"❌ Falha na conexão: código {rc}")
            
    def _on_disconnect(self, client, packet, exc=None):
        """Callback de desconexão."""
        self._connected = False
        print("⚠️ Desconectado do broker MQTT")
        
    async def connect(self):
        """Conecta ao broker MQTT."""
        self.client = MQTTClient(self.config.client_id)
        
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        
        print(f"🔌 Conectando ao broker MQTT {self.config.mqtt_host}:{self.config.mqtt_port}...")
        
        try:
            await self.client.connect(
                self.config.mqtt_host,
                self.config.mqtt_port,
                version=MQTTv311
            )
            # Aguardar conexão
            await asyncio.sleep(1)
        except Exception as e:
            print(f"❌ Erro ao conectar: {e}")
            raise
            
    async def disconnect(self):
        """Desconecta do broker MQTT."""
        if self.client:
            await self.client.disconnect()
            print("👋 Desconectado do broker MQTT")
            
    def publish(self, topic: str, data: Dict[str, Any]):
        """Publica dados em um tópico."""
        if not self._connected:
            print("⚠️ Não conectado, pulando publicação")
            return
            
        payload = json.dumps(data)
        self.client.publish(topic, payload, qos=1)
        
    async def run(self, interval: float = 1.0):
        """Executa o producer em loop."""
        self._running = True
        count = 0
        
        print(f"\n🚀 Iniciando producer (intervalo: {interval}s)")
        print(f"📊 Taxa de alarme: {self.generator.alarm_rate * 100:.0f}%")
        print("-" * 50)
        
        while self._running:
            try:
                count += 1
                
                # Gerar e publicar dados elétricos
                electrical_data = self.generator.generate_electrical()
                self.publish(self.config.topic_electrical, electrical_data)
                
                # Gerar e publicar dados ambientais
                environment_data = self.generator.generate_environment()
                self.publish(self.config.topic_environment, environment_data)
                
                # Gerar e publicar dados de vibração
                vibration_data = self.generator.generate_vibration()
                self.publish(self.config.topic_vibration, vibration_data)
                
                # Log resumido
                voltage_a = electrical_data["voltage"]["a"]
                case_temp = environment_data["caseTemperature"]
                vibration = vibration_data["axial"]
                
                # Detectar alarmes para mostrar no log
                alarms = []
                if voltage_a > 242 or voltage_a < 198:
                    alarms.append(f"V={voltage_a:.1f}V")
                if case_temp > 60:
                    alarms.append(f"T={case_temp:.1f}°C")
                if vibration > 0.5:
                    alarms.append(f"Vib={vibration:.3f}")
                
                alarm_str = f" 🚨 ALARM: {', '.join(alarms)}" if alarms else ""
                
                print(f"[{count:04d}] V={voltage_a:.1f}V | T={case_temp:.1f}°C | Vib={vibration:.3f}{alarm_str}")
                
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"❌ Erro: {e}")
                await asyncio.sleep(1)
                
    def stop(self):
        """Para o producer."""
        self._running = False
        print("\n🛑 Parando producer...")


# ============== Main ==============

async def main():
    """Função principal."""
    parser = argparse.ArgumentParser(
        description="MQTT Producer para Motor 50CV",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python mqtt_producer.py                          # Valores padrão
  python mqtt_producer.py --alarm-rate 0.2         # 20% de chance de alarme
  python mqtt_producer.py --interval 0.5           # Intervalo de 0.5s
  python mqtt_producer.py --host localhost         # Broker local
        """
    )
    parser.add_argument(
        "--alarm-rate", "-a",
        type=float,
        default=float(os.environ.get("ALARM_RATE", "0.1")),
        help="Probabilidade de gerar alarme (0.0 a 1.0, padrão: 0.1)"
    )
    parser.add_argument(
        "--interval", "-i",
        type=float,
        default=float(os.environ.get("INTERVAL", "2.0")),
        help="Intervalo entre mensagens em segundos (padrão: 2.0)"
    )
    parser.add_argument(
        "--host", "-H",
        type=str,
        default=os.environ.get("MQTT_HOST", "lse.dev.br"),
        help="Host do broker MQTT (padrão: lse.dev.br)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=int(os.environ.get("MQTT_PORT", "1883")),
        help="Porta do broker MQTT (padrão: 1883)"
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=0,
        help="Número de mensagens a enviar (0 = infinito, padrão: 0)"
    )
    
    args = parser.parse_args()
    
    # Validar argumentos
    if not 0.0 <= args.alarm_rate <= 1.0:
        print("Erro: alarm-rate deve estar entre 0.0 e 1.0")
        sys.exit(1)
        
    if args.interval <= 0:
        print("Erro: interval deve ser positivo")
        sys.exit(1)
    
    # Configuração
    config = ProducerConfig(
        mqtt_host=args.host,
        mqtt_port=args.port
    )
    
    # Gerador de dados
    generator = DataGenerator(config, alarm_rate=args.alarm_rate)
    
    # Producer
    producer = MQTTProducer(config, generator)
    
    # Tratamento de sinais
    loop = asyncio.get_event_loop()
    
    def signal_handler():
        producer.stop()
        
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, signal_handler)
    
    print("=" * 50)
    print("🔧 MQTT Producer - Motor 50CV")
    print("=" * 50)
    print(f"📡 Broker: {config.mqtt_host}:{config.mqtt_port}")
    print(f"📊 Taxa de alarme: {args.alarm_rate * 100:.0f}%")
    print(f"⏱️  Intervalo: {args.interval}s")
    print("=" * 50)
    
    try:
        await producer.connect()
        await producer.run(interval=args.interval)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"❌ Erro fatal: {e}")
    finally:
        await producer.disconnect()
        print("✅ Producer finalizado")


if __name__ == "__main__":
    asyncio.run(main())
