import asyncio
import base64
import re
import socket
import subprocess
import time
import logging
from typing import List, Tuple, Optional
from urllib.parse import urlparse, parse_qs, unquote
import httpx

import config

logger = logging.getLogger(__name__)


class ConfigChecker:
    """Проверка и парсинг VPN конфигураций"""
    
    def __init__(self):
        self.max_ping = config.XPERT_MAX_PING_MS
        self.target_ips = config.XPERT_TARGET_CHECK_IPS
        self.timeout = 3
    
    def parse_config(self, raw: str) -> Tuple[str, str, int, str]:
        """Парсинг конфигурации VPN"""
        raw = raw.strip()
        protocol = ""
        server = ""
        port = 0
        remarks = ""
        
        try:
            if raw.startswith("vless://"):
                protocol = "vless"
                server, port, remarks = self._parse_vless(raw)
            elif raw.startswith("vmess://"):
                protocol = "vmess"
                server, port, remarks = self._parse_vmess(raw)
            elif raw.startswith("trojan://"):
                protocol = "trojan"
                server, port, remarks = self._parse_trojan(raw)
            elif raw.startswith("ss://"):
                protocol = "shadowsocks"
                server, port, remarks = self._parse_shadowsocks(raw)
            elif raw.startswith("ssr://"):
                protocol = "ssr"
                server, port, remarks = self._parse_ssr(raw)
        except Exception as e:
            logger.debug(f"Failed to parse config: {e}")
        
        return protocol, server, port, remarks
    
    def _parse_vless(self, raw: str) -> Tuple[str, int, str]:
        try:
            parsed = urlparse(raw)
            server = parsed.hostname or ""
            port = parsed.port or 443
            remarks = unquote(parsed.fragment) if parsed.fragment else ""
            return server, port, remarks
        except:
            return "", 0, ""
    
    def _parse_vmess(self, raw: str) -> Tuple[str, int, str]:
        try:
            import json
            encoded = raw.replace("vmess://", "")
            padding = 4 - len(encoded) % 4
            if padding != 4:
                encoded += "=" * padding
            decoded = base64.b64decode(encoded).decode('utf-8')
            data = json.loads(decoded)
            server = data.get("add", "")
            port = int(data.get("port", 443))
            remarks = data.get("ps", "")
            return server, port, remarks
        except:
            return "", 0, ""
    
    def _parse_trojan(self, raw: str) -> Tuple[str, int, str]:
        try:
            parsed = urlparse(raw)
            server = parsed.hostname or ""
            port = parsed.port or 443
            remarks = unquote(parsed.fragment) if parsed.fragment else ""
            return server, port, remarks
        except:
            return "", 0, ""
    
    def _parse_shadowsocks(self, raw: str) -> Tuple[str, int, str]:
        try:
            parsed = urlparse(raw)
            server = parsed.hostname or ""
            port = parsed.port or 443
            remarks = unquote(parsed.fragment) if parsed.fragment else ""
            return server, port, remarks
        except:
            return "", 0, ""
    
    def _parse_ssr(self, raw: str) -> Tuple[str, int, str]:
        try:
            encoded = raw.replace("ssr://", "")
            padding = 4 - len(encoded) % 4
            if padding != 4:
                encoded += "=" * padding
            decoded = base64.urlsafe_b64decode(encoded).decode('utf-8')
            parts = decoded.split(":")
            if len(parts) >= 2:
                server = parts[0]
                port = int(parts[1])
                return server, port, ""
        except:
            pass
        return "", 0, ""
    
    async def check_connectivity(self, host: str, port: int) -> Tuple[bool, float]:
        """Комплексная проверка доступности сервера"""
        try:
            # Метод 1: TCP соединение (самый надежный)
            start_time = time.time()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)  # 5 секунд таймаут
            result = sock.connect_ex((host, port))
            end_time = time.time()
            sock.close()
            
            if result == 0:
                tcp_time = (end_time - start_time) * 1000  # в миллисекундах
                logger.debug(f"TCP connection successful to {host}:{port} in {tcp_time:.2f}ms")
                return True, tcp_time
            else:
                logger.debug(f"TCP connection failed to {host}:{port}")
                
        except Exception as e:
            logger.debug(f"TCP check failed for {host}:{port}: {e}")
        
        # Метод 2: HTTP/HTTPS проверка (если порт 80/443)
        if port in [80, 443, 8080, 8443]:
            try:
                import httpx
                protocol = "https" if port in [443, 8443] else "http"
                url = f"{protocol}://{host}:{port}"
                
                start_time = time.time()
                async with httpx.AsyncClient(timeout=5, verify=False) as client:
                    response = await client.head(url)
                    end_time = time.time()
                    
                if response.status_code < 500:
                    http_time = (end_time - start_time) * 1000
                    logger.debug(f"HTTP check successful to {url} in {http_time:.2f}ms")
                    return True, http_time
                    
            except Exception as e:
                logger.debug(f"HTTP check failed for {host}:{port}: {e}")
        
        return False, 999.0
    
    async def check_ping(self, host: str) -> Tuple[float, float, float]:
        """Улучшенная проверка пинга с fallback на connectivity"""
        try:
            # Сначала пробуем ICMP ping
            process = await asyncio.create_subprocess_exec(
                "ping", "-c", "2", "-W", "2", host,  # Уменьшили количество и таймаут
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5)
            output = stdout.decode()
            
            times = re.findall(r'time[=<](\d+\.?\d*)', output)
            if times:
                pings = [float(t) for t in times]
                avg_ping = sum(pings) / len(pings)
                jitter = max(pings) - min(pings) if len(pings) > 1 else 0
                
                loss_match = re.search(r'(\d+)% packet loss', output)
                loss = float(loss_match.group(1)) if loss_match else 0
                
                logger.debug(f"ICMP ping to {host}: {avg_ping:.2f}ms, loss: {loss}%")
                return avg_ping, jitter, loss
                
        except Exception as e:
            logger.debug(f"ICMP ping failed for {host}: {e}")
        
        # Fallback: если ICMP не работает, возвращаем высокие значения
        # Но проверка connectivity будет в основном методе
        return 999.0, 0.0, 100.0
    
    def check_port(self, host: str, port: int) -> bool:
        """Проверка доступности порта"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((host, port))
            sock.close()
            return result == 0
        except:
            return False
    
    async def fetch_subscription(self, url: str) -> List[str]:
        """Получение конфигураций из URL подписки"""
        configs = []
        try:
            # Улучшенные заголовки для GitHub и других сервисов
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
                "Accept": "text/plain, application/octet-stream, */*",
                "Accept-Encoding": "gzip, deflate",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache"
            }
            
            # Настройки клиента с поддержкой SSL
            async with httpx.AsyncClient(
                timeout=30, 
                follow_redirects=True,
                verify=False  # Отключаем проверку SSL для проблемных сертификатов
            ) as client:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 200:
                    content = response.text
                    
                    # Проверяем если контент уже содержит готовые конфиги
                    if any(proto in content for proto in ['vless://', 'vmess://', 'trojan://', 'ss://', 'ssr://']):
                        # Это готовые конфиги, используем как есть
                        final_content = content
                        logger.info(f"Detected direct configs from {url}")
                    else:
                        # Попробуем декодировать base64
                        decoded_content = content
                        for attempt in range(3):
                            try:
                                # Убираем возможные пробелы и переносы
                                clean_content = content.strip().replace('\n', '').replace('\r', '')
                                # Добавляем padding если нужно
                                padding_needed = len(clean_content) % 4
                                if padding_needed:
                                    clean_content += '=' * (4 - padding_needed)
                                
                                decoded = base64.b64decode(clean_content).decode('utf-8')
                                decoded_content = decoded
                                logger.info(f"Successfully decoded base64 from {url}")
                                break
                            except Exception as e:
                                if attempt == 2:  # Последняя попытка
                                    logger.debug(f"Base64 decode failed after 3 attempts: {e}")
                                continue
                        
                        # Используем декодированный контент или оригинал
                        final_content = decoded_content if decoded_content != content else content
                    
                    # Разбиваем на строки и фильтруем
                    for line in final_content.split('\n'):
                        line = line.strip()
                        if line and any(line.startswith(p) for p in ['vless://', 'vmess://', 'trojan://', 'ss://', 'ssr://']):
                            configs.append(line)
                    
                    logger.info(f"Fetched {len(configs)} configs from {url}")
                    
                else:
                    logger.error(f"HTTP {response.status_code} for {url}")
                    
        except httpx.SSLError as e:
            logger.error(f"SSL error for {url}: {e}")
        except httpx.TimeoutException as e:
            logger.error(f"Timeout for {url}: {e}")
        except Exception as e:
            logger.error(f"Failed to fetch subscription {url}: {e}")
        
        return configs
    
    async def process_config(self, raw: str) -> Optional[dict]:
        """Обработка одной конфигурации с улучшенной проверкой доступности"""
        import time
        
        protocol, server, port, remarks = self.parse_config(raw)
        
        if not server or not port:
            logger.warning(f"Failed to parse server/port from: {raw}")
            return None
        
        logger.info(f"Testing {protocol}://{server}:{port} - {remarks[:30]}...")
        
        # Комплексная проверка доступности
        is_connected, connection_time = await self.check_connectivity(server, port)
        
        # Дополнительная ping-проверка (если доступен)
        if is_connected:
            ping, jitter, loss = await self.check_ping(server)
            # Если ping не удался, используем время подключения как пинг
            if ping >= 999.0:
                ping = connection_time
                loss = 0
        else:
            ping, jitter, loss = 999.0, 0.0, 100.0
        
        # Критерии активности (более гибкие)
        is_active = (
            is_connected and  # Главное - доступность
            ping <= 1000 and  # Пинг до 1 секунды
            loss < 100        # Потери до 100%
        )
        
        logger.info(f"Result: {protocol}://{server}:{port} - "
                   f"{'ACTIVE' if is_active else 'INACTIVE'} "
                   f"(ping: {ping:.1f}ms, loss: {loss:.1f}%, connected: {is_connected})")
        
        return {
            "raw": raw,
            "protocol": protocol,
            "server": server,
            "port": port,
            "remarks": remarks or f"{protocol.upper()}-{server[:15]}",
            "ping_ms": ping,
            "jitter_ms": jitter,
            "packet_loss": loss,
            "is_active": is_active
        }


checker = ConfigChecker()
