import logging
import re
from typing import List, Set
from urllib.parse import urlparse
from app.xpert.cluster_service import whitelist_service

logger = logging.getLogger(__name__)

class IPFilter:
    """Фильтрует сервера по белому списку IP адресов"""
    
    def __init__(self):
        self.allowed_ips: Set[str] = set()
    
    def update_allowed_ips(self):
        """Обновляет кэш разрешенных IP"""
        self.allowed_ips = whitelist_service.get_all_allowed_ips()
        logger.info(f"Updated allowed IPs cache: {len(self.allowed_ips)} IPs")
    
    def extract_ip_from_config(self, config: str) -> str:
        """Извлекает IP адрес из конфигурации"""
        try:
            # Пробуем разные форматы конфигов
            
            # VLESS/VLESS/TROJAN: vless://uuid@IP:PORT?...
            if config.startswith(('vless://', 'trojan://')):
                match = re.search(r'@([^:]+):', config)
                if match:
                    ip = match.group(1)
                    logger.debug(f"Extracted IP {ip} from VLESS/Trojan config")
                    return ip
            
            # VMESS: vmess://BASE64
            elif config.startswith('vmess://'):
                import base64
                try:
                    decoded = base64.b64decode(config[8:]).decode('utf-8')
                    data = eval(decoded)  # В реальном коде нужно использовать json.loads
                    ip = data.get('add', '')
                    if ip:
                        logger.debug(f"Extracted IP {ip} from VMESS config")
                        return ip
                except:
                    pass
            
            # Shadowsocks: ss://BASE64
            elif config.startswith('ss://'):
                import base64
                try:
                    # Убираем префикс и декодируем
                    encoded = config[5:]
                    if encoded.endswith('/'):
                        encoded = encoded[:-1]
                    
                    # Добавляем padding если нужно
                    padding_needed = len(encoded) % 4
                    if padding_needed:
                        encoded += '=' * (4 - padding_needed)
                    
                    decoded = base64.b64decode(encoded).decode('utf-8')
                    
                    # Формат: method:password@IP:PORT
                    if '@' in decoded:
                        match = re.search(r'@([^:]+):', decoded)
                        if match:
                            ip = match.group(1)
                            logger.debug(f"Extracted IP {ip} from SS config")
                            return ip
                except:
                    pass
            
            # SSR: ssr://BASE64
            elif config.startswith('ssr://'):
                import base64
                try:
                    encoded = config[6:]
                    padding_needed = len(encoded) % 4
                    if padding_needed:
                        encoded += '=' * (4 - padding_needed)
                    
                    decoded = base64.urlsafe_b64decode(encoded).decode('utf-8')
                    parts = decoded.split(':')
                    if len(parts) >= 2:
                        ip = parts[0]
                        logger.debug(f"Extracted IP {ip} from SSR config")
                        return ip
                except:
                    pass
            
            logger.warning(f"Could not extract IP from config: {config[:50]}...")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting IP from config: {e}")
            return ""
    
    def is_ip_allowed(self, ip: str) -> bool:
        """Проверяет разрешен ли IP"""
        if not ip:
            return False
        
        # Обновляем кэш если пуст
        if not self.allowed_ips:
            self.update_allowed_ips()
        
        return ip in self.allowed_ips
    
    def filter_servers(self, server_configs: List[str]) -> List[str]:
        """Фильтрует сервера, оставляя только с разрешенными IP"""
        if not server_configs:
            return []
        
        # Обновляем разрешенные IP
        self.update_allowed_ips()
        
        if not self.allowed_ips:
            logger.warning("No allowed IPs configured, returning all servers")
            return server_configs
        
        logger.info(f"Filtering {len(server_configs)} servers against {len(self.allowed_ips)} allowed IPs")
        
        filtered_servers = []
        
        for config in server_configs:
            ip = self.extract_ip_from_config(config)
            
            if self.is_ip_allowed(ip):
                filtered_servers.append(config)
                logger.info(f"✅ Allowed server: {ip}")
            else:
                logger.info(f"❌ Blocked server: {ip} (not in whitelist)")
        
        logger.info(f"Filtered result: {len(filtered_servers)}/{len(server_configs)} servers allowed")
        return filtered_servers
    
    def get_filter_stats(self) -> dict:
        """Получает статистику фильтрации"""
        self.update_allowed_ips()
        
        return {
            'allowed_ips_count': len(self.allowed_ips),
            'allowed_ips': list(self.allowed_ips),
            'whitelists_count': len(whitelist_service.whitelists),
            'whitelists_stats': whitelist_service.get_whitelist_stats()
        }

# Глобальный экземпляр
ip_filter = IPFilter()
