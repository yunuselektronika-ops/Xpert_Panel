"""
Интеграция Xpert Panel с Marzban
Автоматическое добавление проверенных конфигураций в Marzban
"""

import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.db.crud import add_host, get_or_create_inbound
from app.db.models import ProxyInbound, ProxyHost
from app.models.proxy import ProxyHost as ProxyHostModify
from app.xpert.models import AggregatedConfig
from app.xpert.storage import storage
from app import db

logger = logging.getLogger(__name__)


class MarzbanIntegration:
    """Сервис интеграции с Marzban"""
    
    def __init__(self):
        self.db_session = db.SessionLocal()
        
    def __del__(self):
        if hasattr(self, 'db_session'):
            self.db_session.close()
    
    def get_inbound_tag_for_protocol(self, protocol: str) -> str:
        """Получение тега inbound для протокола"""
        protocol_mapping = {
            "vless": "VLESS_INBOUND",
            "vmess": "VMess_INBOUND", 
            "trojan": "Trojan_INBOUND",
            "shadowsocks": "SS_INBOUND"
        }
        return protocol_mapping.get(protocol.lower(), "DEFAULT_INBOUND")
    
    def config_to_proxy_host(self, config: AggregatedConfig) -> ProxyHostModify:
        """Конвертация конфигурации в ProxyHost для Marzban"""
        return ProxyHostModify(
            remark=f"Xpert-{config.protocol.upper()}-{config.server[:15]}",
            address=config.server,
            port=config.port,
            path="",  # Будет заполнено в зависимости от протокола
            sni="",
            host="",
            security="none",
            alpn="",
            fingerprint=""
        )
    
    def sync_active_configs_to_marzban(self) -> Dict:
        """Синхронизация активных конфигов с Marzban"""
        try:
            # Получаем активные конфиги
            active_configs = storage.get_active_configs()
            
            if not active_configs:
                logger.info("No active configs to sync")
                return {"status": "no_configs", "count": 0}
            
            # Группируем по протоколам
            configs_by_protocol = {}
            for config in active_configs:
                protocol = config.protocol.lower()
                if protocol not in configs_by_protocol:
                    configs_by_protocol[protocol] = []
                configs_by_protocol[protocol].append(config)
            
            synced_count = 0
            errors = []
            
            # Обрабатываем каждый протокол
            for protocol, configs in configs_by_protocol.items():
                try:
                    result = self._sync_protocol_configs(protocol, configs)
                    synced_count += result["synced"]
                    errors.extend(result.get("errors", []))
                except Exception as e:
                    error_msg = f"Failed to sync {protocol}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
            
            logger.info(f"Marzban sync complete: {synced_count} configs synced")
            
            return {
                "status": "success",
                "total_synced": synced_count,
                "total_configs": len(active_configs),
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Marzban integration failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    def _sync_protocol_configs(self, protocol: str, configs: List[AggregatedConfig]) -> Dict:
        """Синхронизация конфигов для конкретного протокола"""
        inbound_tag = self.get_inbound_tag_for_protocol(protocol)
        
        # Получаем или создаем inbound
        inbound = get_or_create_inbound(self.db_session, inbound_tag)
        
        # Получаем текущие хосты
        current_hosts = inbound.hosts or []
        current_addresses = {host.address for host in current_hosts}
        
        # Определяем какие хосты добавить
        new_addresses = set()
        synced_count = 0
        errors = []
        
        for config in configs:
            if config.server not in current_addresses:
                new_addresses.add(config.server)
        
        # Добавляем новые хосты
        for config in configs:
            if config.server in new_addresses:
                try:
                    proxy_host = self.config_to_proxy_host(config)
                    
                    # Настраиваем параметры для разных протоколов
                    if protocol.lower() == "vless":
                        proxy_host.path = f"?id={config.raw.split('vless://')[1].split('@')[0] if '@' in config.raw else ''}"
                        proxy_host.security = "tls"
                    elif protocol.lower() == "vmess":
                        proxy_host.path = f"?id={config.raw.split('vmess://')[1].split('?')[0] if '?' in config.raw else ''}"
                        proxy_host.security = "none"
                    elif protocol.lower() == "trojan":
                        proxy_host.path = f"?password={config.raw.split('trojan://')[1].split('@')[0] if '@' in config.raw else ''}"
                        proxy_host.security = "tls"
                    elif protocol.lower() == "shadowsocks":
                        proxy_host.security = "none"
                    
                    # Добавляем хост
                    add_host(self.db_session, inbound_tag, proxy_host)
                    synced_count += 1
                    logger.info(f"Added {protocol} host: {config.server}:{config.port}")
                    
                except Exception as e:
                    error_msg = f"Failed to add host {config.server}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
        
        return {
            "synced": synced_count,
            "errors": errors
        }
    
    def cleanup_inactive_hosts(self, active_configs: List[AggregatedConfig]) -> Dict:
        """Очистка неактивных хостов из Marzban"""
        try:
            active_addresses = {config.server for config in active_configs}
            removed_count = 0
            errors = []
            
            # Получаем все inbound'ы
            inbounds = self.db_session.query(ProxyInbound).all()
            
            for inbound in inbounds:
                if not inbound.hosts:
                    continue
                
                # Удаляем неактивные хосты
                hosts_to_keep = []
                for host in inbound.hosts:
                    if host.address in active_addresses:
                        hosts_to_keep.append(host)
                    else:
                        try:
                            self.db_session.delete(host)
                            removed_count += 1
                            logger.info(f"Removed inactive host: {host.address}")
                        except Exception as e:
                            error_msg = f"Failed to remove host {host.address}: {str(e)}"
                            logger.error(error_msg)
                            errors.append(error_msg)
                
                inbound.hosts = hosts_to_keep
            
            self.db_session.commit()
            
            logger.info(f"Cleanup complete: {removed_count} inactive hosts removed")
            
            return {
                "status": "success",
                "removed_count": removed_count,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return {
                "status": "error",
                "error": str(e)
            }


# Глобальный экземпляр интеграции
marzban_integration = MarzbanIntegration()
