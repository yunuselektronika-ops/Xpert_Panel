import asyncio
import base64
import re
import socket
import subprocess
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
    
    async def check_ping(self, host: str) -> Tuple[float, float, float]:
        """Проверка пинга до хоста"""
        try:
            process = await asyncio.create_subprocess_exec(
                "ping", "-c", "3", "-W", str(self.timeout), host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
            output = stdout.decode()
            
            times = re.findall(r'time[=<](\d+\.?\d*)', output)
            if times:
                pings = [float(t) for t in times]
                avg_ping = sum(pings) / len(pings)
                jitter = max(pings) - min(pings) if len(pings) > 1 else 0
                
                loss_match = re.search(r'(\d+)% packet loss', output)
                loss = float(loss_match.group(1)) if loss_match else 0
                
                return avg_ping, jitter, loss
        except Exception as e:
            logger.debug(f"Ping failed for {host}: {e}")
        
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
                    
                    # Попробуем декодировать base64 (несколько попыток)
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
        """Обработка одной конфигурации"""
        protocol, server, port, remarks = self.parse_config(raw)
        
        if not server or not port:
            return None
        
        ping, jitter, loss = await self.check_ping(server)
        port_open = self.check_port(server, port)
        
        is_active = (
            ping <= self.max_ping and
            loss < 50 and
            port_open
        )
        
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
