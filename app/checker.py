import asyncio
import aiohttp
import re
import json
import base64
import socket
import subprocess
import platform
import logging
from typing import List, Tuple, Optional
from datetime import datetime, timedelta
from app.config import settings
from app.models import VPNConfig, SubscriptionSource, AggregatedSubscription
from app.storage import storage

logger = logging.getLogger(__name__)

class ConfigChecker:
    """Проверка и фильтрация VPN конфигураций"""
    
    def __init__(self):
        self.max_ping = settings.MAX_PING_MS
        self.ping_timeout = settings.PING_TIMEOUT
        self.max_configs = settings.MAX_CONFIGS
    
    async def fetch_source(self, source: SubscriptionSource) -> List[str]:
        """Получение конфигураций из источника"""
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                headers = {
                    'User-Agent': 'Xpert-Panel/1.0',
                    'Accept': '*/*'
                }
                async with session.get(source.url, headers=headers, ssl=False) as response:
                    if response.status == 200:
                        content = await response.text()
                        configs = self.parse_content(content)
                        
                        # Обновляем статистику источника
                        source.last_fetched = datetime.utcnow().isoformat()
                        source.config_count = len(configs)
                        source.success_rate = 100.0
                        storage.update_source(source)
                        
                        logger.info(f"Fetched {len(configs)} configs from {source.name}")
                        return configs
                    else:
                        logger.warning(f"Failed to fetch {source.name}: HTTP {response.status}")
                        source.success_rate = 0.0
                        storage.update_source(source)
        except Exception as e:
            logger.error(f"Error fetching {source.name}: {e}")
            source.success_rate = 0.0
            storage.update_source(source)
        
        return []
    
    def parse_content(self, content: str) -> List[str]:
        """Парсинг контента подписки"""
        configs = []
        
        # Пробуем декодировать base64
        try:
            decoded = base64.b64decode(content).decode('utf-8')
            content = decoded
        except:
            pass
        
        # Разбиваем на строки
        for line in content.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            # Проверяем известные протоколы
            if any(line.startswith(p) for p in ['ss://', 'vmess://', 'vless://', 'trojan://', 'hy2://', 'tuic://']):
                configs.append(line)
            # Проверяем Surge/Shadowrocket формат
            elif 'hostname=' in line.lower() or 'server=' in line.lower():
                configs.append(line)
        
        return configs
    
    def parse_config(self, raw: str) -> Tuple[str, str, int, str]:
        """Парсинг конфигурации: возвращает (protocol, server, port, remarks)"""
        protocol = "unknown"
        server = ""
        port = 443
        remarks = ""
        
        try:
            # Shadowsocks
            if raw.startswith('ss://'):
                protocol = "ss"
                parts = raw[5:].split('#')
                if len(parts) > 1:
                    remarks = parts[1]
                
                encoded = parts[0]
                if '@' in encoded:
                    # Формат: method:password@server:port
                    server_part = encoded.split('@')[1]
                    if ':' in server_part:
                        server, port_str = server_part.rsplit(':', 1)
                        port = int(port_str.split('/')[0].split('?')[0])
                else:
                    # Base64 encoded
                    try:
                        decoded = base64.b64decode(encoded + '===').decode()
                        if '@' in decoded:
                            server_part = decoded.split('@')[1]
                            if ':' in server_part:
                                server, port_str = server_part.rsplit(':', 1)
                                port = int(port_str)
                    except:
                        pass
            
            # VMess
            elif raw.startswith('vmess://'):
                protocol = "vmess"
                try:
                    encoded = raw[8:]
                    decoded = base64.b64decode(encoded + '===').decode()
                    data = json.loads(decoded)
                    server = data.get('add', '')
                    port = int(data.get('port', 443))
                    remarks = data.get('ps', '')
                except:
                    pass
            
            # VLESS
            elif raw.startswith('vless://'):
                protocol = "vless"
                try:
                    # vless://uuid@server:port?params#remarks
                    parts = raw[8:].split('#')
                    if len(parts) > 1:
                        remarks = parts[1]
                    
                    main = parts[0]
                    if '@' in main:
                        server_part = main.split('@')[1].split('?')[0]
                        if ':' in server_part:
                            server, port_str = server_part.rsplit(':', 1)
                            port = int(port_str)
                except:
                    pass
            
            # Trojan
            elif raw.startswith('trojan://'):
                protocol = "trojan"
                try:
                    parts = raw[9:].split('#')
                    if len(parts) > 1:
                        remarks = parts[1]
                    
                    main = parts[0]
                    if '@' in main:
                        server_part = main.split('@')[1].split('?')[0]
                        if ':' in server_part:
                            server, port_str = server_part.rsplit(':', 1)
                            port = int(port_str)
                except:
                    pass
            
            # Hysteria2
            elif raw.startswith('hy2://'):
                protocol = "hy2"
                try:
                    parts = raw[6:].split('#')
                    if len(parts) > 1:
                        remarks = parts[1]
                    
                    main = parts[0]
                    if '@' in main:
                        server_part = main.split('@')[1].split('?')[0]
                        if ':' in server_part:
                            server, port_str = server_part.rsplit(':', 1)
                            port = int(port_str)
                except:
                    pass
            
            # Surge/Shadowrocket формат
            elif 'hostname=' in raw.lower() or 'server=' in raw.lower():
                protocol = "http"
                # Ищем hostname или server
                match = re.search(r'(?:hostname|server)\s*=\s*([^,\s]+)', raw, re.IGNORECASE)
                if match:
                    server = match.group(1)
                
                # Ищем порт
                port_match = re.search(r'port\s*=\s*(\d+)', raw, re.IGNORECASE)
                if port_match:
                    port = int(port_match.group(1))
                
                # Ищем remarks
                remarks_match = re.search(r'(?:remarks|name)\s*=\s*([^,\n]+)', raw, re.IGNORECASE)
                if remarks_match:
                    remarks = remarks_match.group(1).strip()
        
        except Exception as e:
            logger.error(f"Error parsing config: {e}")
        
        return protocol, server, port, remarks
    
    async def check_ping(self, host: str, count: int = 2) -> Tuple[float, float, float]:
        """Проверка пинга: возвращает (avg_ping, jitter, packet_loss)"""
        try:
            # Определяем параметры для ОС
            if platform.system().lower() == 'windows':
                cmd = ['ping', '-n', str(count), '-w', str(self.ping_timeout * 1000), host]
            else:
                cmd = ['ping', '-c', str(count), '-W', str(self.ping_timeout), host]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=self.ping_timeout * count + 2
            )
            
            output = stdout.decode('utf-8', errors='ignore')
            
            if process.returncode == 0:
                # Извлекаем времена
                times = re.findall(r'(?:time[=<]|время[=<])(\d+(?:\.\d+)?)', output, re.IGNORECASE)
                if times:
                    times = [float(t) for t in times]
                    avg_ping = sum(times) / len(times)
                    
                    # Джиттер
                    jitter = 0.0
                    if len(times) > 1:
                        jitter = sum(abs(times[i] - times[i-1]) for i in range(1, len(times))) / (len(times) - 1)
                    
                    # Потери
                    loss_match = re.search(r'(\d+)%', output)
                    packet_loss = float(loss_match.group(1)) if loss_match else 0.0
                    
                    return avg_ping, jitter, packet_loss
        
        except asyncio.TimeoutError:
            pass
        except Exception as e:
            logger.debug(f"Ping error for {host}: {e}")
        
        return 999.0, 0.0, 100.0
    
    def check_port(self, host: str, port: int, timeout: int = 2) -> bool:
        """Проверка доступности порта"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    async def process_config(self, raw: str, source_name: str = "") -> Optional[VPNConfig]:
        """Обработка одной конфигурации"""
        protocol, server, port, remarks = self.parse_config(raw)
        
        if not server:
            return None
        
        config = VPNConfig(
            raw=raw,
            protocol=protocol,
            server=server,
            port=port,
            remarks=remarks or f"{protocol.upper()}-{server[:15]}",
            source=source_name,
            last_check=datetime.utcnow().isoformat()
        )
        
        # Проверяем пинг
        ping, jitter, loss = await self.check_ping(server)
        
        config.ping_ms = ping
        config.jitter_ms = jitter
        config.packet_loss = loss
        
        # Определяем активность
        config.is_active = (
            ping <= self.max_ping and
            loss < 50
        )
        
        return config
    
    async def collect_all_configs(self) -> List[VPNConfig]:
        """Сбор всех конфигураций из источников"""
        sources = storage.get_sources()
        enabled_sources = [s for s in sources if s.enabled]
        
        if not enabled_sources:
            logger.warning("No enabled sources found")
            return []
        
        logger.info(f"Collecting configs from {len(enabled_sources)} sources...")
        
        all_raw_configs = []
        
        # Собираем конфиги из всех источников
        for source in enabled_sources:
            raw_configs = await self.fetch_source(source)
            for raw in raw_configs:
                all_raw_configs.append((raw, source.name))
        
        logger.info(f"Total raw configs collected: {len(all_raw_configs)}")
        
        # Обрабатываем конфиги (ограничиваем для производительности)
        all_configs = []
        batch_size = 20
        
        for i in range(0, min(len(all_raw_configs), 200), batch_size):
            batch = all_raw_configs[i:i + batch_size]
            tasks = [self.process_config(raw, source) for raw, source in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, VPNConfig):
                    all_configs.append(result)
            
            logger.info(f"Processed batch {i//batch_size + 1}")
        
        # Фильтруем активные
        active_configs = [c for c in all_configs if c.is_active]
        
        # Сортируем по качеству
        active_configs.sort(key=lambda c: c.ping_ms + c.jitter_ms * 0.5 + c.packet_loss * 2)
        
        # Ограничиваем количество
        result = active_configs[:self.max_configs]
        
        logger.info(f"Final active configs: {len(result)}")
        
        return result
    
    async def update_subscription(self) -> AggregatedSubscription:
        """Обновление подписки"""
        logger.info("Starting subscription update...")
        
        configs = await self.collect_all_configs()
        
        # Сохраняем конфиги
        storage.save_configs(configs)
        
        # Создаем подписку
        subscription = AggregatedSubscription(
            configs=configs,
            generated_at=datetime.utcnow().isoformat(),
            expires_at=(datetime.utcnow() + timedelta(hours=settings.UPDATE_INTERVAL_HOURS)).isoformat(),
            total_sources=len(storage.get_sources()),
            active_configs=len(configs),
            update_interval_hours=settings.UPDATE_INTERVAL_HOURS
        )
        
        # Сохраняем подписку
        storage.save_subscription(subscription)
        
        logger.info(f"Subscription updated: {len(configs)} active configs")
        
        return subscription


checker = ConfigChecker()
