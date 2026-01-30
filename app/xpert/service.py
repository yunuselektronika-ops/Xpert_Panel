import asyncio
import base64
import logging
from datetime import datetime
from typing import List, Optional

from app.xpert.models import SubscriptionSource, AggregatedConfig
from app.xpert.storage import storage
from app.xpert.checker import checker
from app.xpert.marzban_integration import marzban_integration
import config as app_config

logger = logging.getLogger(__name__)


class XpertService:
    """Сервис агрегации подписок"""
    
    def add_source(self, name: str, url: str, priority: int = 1) -> SubscriptionSource:
        """Добавление источника подписки"""
        return storage.add_source(name, url, priority)
    
    def get_sources(self) -> List[SubscriptionSource]:
        """Получение всех источников"""
        return storage.get_sources()
    
    def get_enabled_sources(self) -> List[SubscriptionSource]:
        """Получение активных источников"""
        return storage.get_enabled_sources()
    
    def toggle_source(self, source_id: int) -> Optional[SubscriptionSource]:
        """Включение/выключение источника"""
        return storage.toggle_source(source_id)
    
    def delete_source(self, source_id: int) -> bool:
        """Удаление источника"""
        return storage.delete_source(source_id)
    
    def get_active_configs(self) -> List[AggregatedConfig]:
        """Получение активных конфигураций"""
        return storage.get_active_configs()
    
    def get_all_configs(self) -> List[AggregatedConfig]:
        """Получение всех конфигураций"""
        return storage.get_configs()
    
    async def update_subscription(self) -> dict:
        """Обновление всех подписок"""
        sources = self.get_enabled_sources()
        
        if not sources:
            logger.warning("No enabled sources found")
            return {"active_configs": 0, "total_configs": 0}
        
        all_configs = []
        total_configs = 0
        active_configs = 0
        config_id = 1
        
        for source in sources:
            try:
                logger.info(f"Fetching configs from: {source.name}")
                raw_configs = await checker.fetch_subscription(source.url)
                
                source.last_fetched = datetime.utcnow().isoformat()
                source.config_count = len(raw_configs)
                
                source_active = 0
                for raw in raw_configs:
                    result = await checker.process_config(raw)
                    if result:
                        config_obj = AggregatedConfig(
                            id=config_id,
                            raw=result["raw"],
                            protocol=result["protocol"],
                            server=result["server"],
                            port=result["port"],
                            remarks=result["remarks"],
                            source_id=source.id,
                            ping_ms=result["ping_ms"],
                            jitter_ms=result["jitter_ms"],
                            packet_loss=result["packet_loss"],
                            is_active=result["is_active"],
                            last_check=datetime.utcnow().isoformat()
                        )
                        all_configs.append(config_obj)
                        config_id += 1
                        total_configs += 1
                        if result["is_active"]:
                            active_configs += 1
                            source_active += 1
                
                source.success_rate = (source_active / len(raw_configs) * 100) if raw_configs else 0
                storage.update_source(source)
                
                logger.info(f"Source {source.name}: {source_active}/{len(raw_configs)} active configs")
                
            except Exception as e:
                logger.error(f"Failed to process source {source.name}: {e}")
                source.success_rate = 0
                storage.update_source(source)
        
        storage.save_configs(all_configs)
        logger.info(f"Subscription update complete: {active_configs}/{total_configs} active configs")
        
        # Синхронизация с Marzban
        try:
            sync_result = marzban_integration.sync_active_configs_to_marzban()
            logger.info(f"Marzban sync result: {sync_result}")
            
            # Очистка неактивных хостов
            cleanup_result = marzban_integration.cleanup_inactive_hosts(all_configs)
            logger.info(f"Marzban cleanup result: {cleanup_result}")
            
        except Exception as e:
            logger.error(f"Marzban integration failed: {e}")
        
        return {"active_configs": active_configs, "total_configs": total_configs}
    
    def generate_subscription(self, format: str = "universal") -> str:
        """Генерация подписки в указанном формате"""
        configs = self.get_active_configs()
        
        if format == "base64":
            content = "\n".join([c.raw for c in configs])
            return base64.b64encode(content.encode()).decode()
        else:
            return "\n".join([c.raw for c in configs])
    
    def get_stats(self) -> dict:
        """Получение статистики"""
        stats = storage.get_stats()
        stats["target_ips"] = app_config.XPERT_TARGET_CHECK_IPS
        stats["domain"] = app_config.XPERT_DOMAIN
        return stats


xpert_service = XpertService()
