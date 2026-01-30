import json
import os
from typing import List, Optional
from datetime import datetime
from app.config import settings
from app.models import SubscriptionSource, VPNConfig, AggregatedSubscription

class FileStorage:
    """Файловое хранилище данных (без Redis)"""
    
    def __init__(self):
        self.data_dir = settings.DATA_DIR
        os.makedirs(self.data_dir, exist_ok=True)
        
        self.sources_file = os.path.join(self.data_dir, "sources.json")
        self.configs_file = os.path.join(self.data_dir, "configs.json")
        self.subscription_file = os.path.join(self.data_dir, "subscription.json")
        
        self._init_files()
    
    def _init_files(self):
        """Инициализация файлов если не существуют"""
        if not os.path.exists(self.sources_file):
            self._write_json(self.sources_file, [])
        if not os.path.exists(self.configs_file):
            self._write_json(self.configs_file, [])
        if not os.path.exists(self.subscription_file):
            self._write_json(self.subscription_file, {})
    
    def _read_json(self, filepath: str):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None
    
    def _write_json(self, filepath: str, data):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Sources
    def get_sources(self) -> List[SubscriptionSource]:
        data = self._read_json(self.sources_file) or []
        return [SubscriptionSource.from_dict(s) for s in data]
    
    def add_source(self, source: SubscriptionSource) -> bool:
        sources = self.get_sources()
        # Проверяем дубликаты по URL
        for s in sources:
            if s.url == source.url:
                return False
        sources.append(source)
        self._write_json(self.sources_file, [s.to_dict() for s in sources])
        return True
    
    def remove_source(self, source_id: str) -> bool:
        sources = self.get_sources()
        new_sources = [s for s in sources if s.id != source_id]
        if len(new_sources) < len(sources):
            self._write_json(self.sources_file, [s.to_dict() for s in new_sources])
            return True
        return False
    
    def update_source(self, source: SubscriptionSource) -> bool:
        sources = self.get_sources()
        for i, s in enumerate(sources):
            if s.id == source.id:
                sources[i] = source
                self._write_json(self.sources_file, [s.to_dict() for s in sources])
                return True
        return False
    
    def toggle_source(self, source_id: str) -> bool:
        sources = self.get_sources()
        for s in sources:
            if s.id == source_id:
                s.enabled = not s.enabled
                self._write_json(self.sources_file, [s.to_dict() for s in sources])
                return True
        return False
    
    # Configs
    def get_configs(self) -> List[VPNConfig]:
        data = self._read_json(self.configs_file) or []
        return [VPNConfig.from_dict(c) for c in data]
    
    def save_configs(self, configs: List[VPNConfig]):
        self._write_json(self.configs_file, [c.to_dict() for c in configs])
    
    def get_active_configs(self) -> List[VPNConfig]:
        configs = self.get_configs()
        return [c for c in configs if c.is_active]
    
    # Subscription
    def get_subscription(self) -> Optional[AggregatedSubscription]:
        data = self._read_json(self.subscription_file)
        if data and data.get('configs'):
            configs = [VPNConfig.from_dict(c) for c in data.get('configs', [])]
            return AggregatedSubscription(
                id=data.get('id', ''),
                configs=configs,
                generated_at=data.get('generated_at', ''),
                expires_at=data.get('expires_at', ''),
                total_sources=data.get('total_sources', 0),
                active_configs=data.get('active_configs', 0),
                update_interval_hours=data.get('update_interval_hours', 1)
            )
        return None
    
    def save_subscription(self, subscription: AggregatedSubscription):
        self._write_json(self.subscription_file, subscription.to_dict())
    
    # Stats
    def get_stats(self) -> dict:
        sources = self.get_sources()
        configs = self.get_configs()
        subscription = self.get_subscription()
        
        return {
            "total_sources": len(sources),
            "enabled_sources": len([s for s in sources if s.enabled]),
            "total_configs": len(configs),
            "active_configs": len([c for c in configs if c.is_active]),
            "last_update": subscription.generated_at if subscription else None,
            "update_interval_hours": settings.UPDATE_INTERVAL_HOURS
        }


storage = FileStorage()
