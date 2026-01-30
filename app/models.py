from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import Optional, List
import hashlib
import json

@dataclass
class VPNConfig:
    """VPN конфигурация"""
    id: str = ""
    raw: str = ""
    protocol: str = "unknown"
    server: str = ""
    port: int = 443
    country: str = "Unknown"
    ping_ms: float = 999.0
    jitter_ms: float = 0.0
    packet_loss: float = 100.0
    is_active: bool = False
    remarks: str = ""
    source: str = ""
    last_check: Optional[str] = None
    
    def __post_init__(self):
        if not self.id and self.server:
            self.id = hashlib.md5(f"{self.protocol}:{self.server}:{self.port}".encode()).hexdigest()[:8]
        if not self.last_check:
            self.last_check = datetime.utcnow().isoformat()
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class SubscriptionSource:
    """Источник подписки"""
    id: str = ""
    name: str = ""
    url: str = ""
    enabled: bool = True
    priority: int = 1
    last_fetched: Optional[str] = None
    config_count: int = 0
    success_rate: float = 0.0
    
    def __post_init__(self):
        if not self.id and self.url:
            self.id = hashlib.md5(self.url.encode()).hexdigest()[:8]
    
    def to_dict(self):
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class AggregatedSubscription:
    """Агрегированная подписка"""
    id: str = ""
    configs: List[VPNConfig] = field(default_factory=list)
    generated_at: str = ""
    expires_at: str = ""
    total_sources: int = 0
    active_configs: int = 0
    update_interval_hours: int = 1
    
    def __post_init__(self):
        if not self.id:
            self.id = hashlib.md5(str(datetime.utcnow().timestamp()).encode()).hexdigest()[:8]
        if not self.generated_at:
            self.generated_at = datetime.utcnow().isoformat()
    
    def to_dict(self):
        return {
            "id": self.id,
            "configs": [c.to_dict() if isinstance(c, VPNConfig) else c for c in self.configs],
            "generated_at": self.generated_at,
            "expires_at": self.expires_at,
            "total_sources": self.total_sources,
            "active_configs": self.active_configs,
            "update_interval_hours": self.update_interval_hours
        }
