import json
import logging
from typing import Dict, List, Optional, Set
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class AllowedIP:
    """Разрешенный IP адрес"""
    ip: str
    description: str = ""
    country: str = ""
    is_active: bool = True
    added_at: str = ""

@dataclass 
class IPWhitelist:
    """Белый список IP адресов"""
    id: str
    name: str
    description: str
    allowed_ips: List[AllowedIP]
    created_at: str
    updated_at: str
    is_active: bool = True

class WhitelistService:
    """Сервис управления белым списком IP адресов"""
    
    def __init__(self):
        self.whitelists: Dict[str, IPWhitelist] = {}
        self.storage_file = "ip_whitelist.json"
        self._load_whitelists()
    
    def _load_whitelists(self):
        """Загружает белые списки из файла"""
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for whitelist_id, whitelist_data in data.items():
                    ips = [AllowedIP(**ip) for ip in whitelist_data['allowed_ips']]
                    self.whitelists[whitelist_id] = IPWhitelist(
                        id=whitelist_data['id'],
                        name=whitelist_data['name'],
                        description=whitelist_data['description'],
                        allowed_ips=ips,
                        created_at=whitelist_data['created_at'],
                        updated_at=whitelist_data['updated_at'],
                        is_active=whitelist_data.get('is_active', True)
                    )
                logger.info(f"Loaded {len(self.whitelists)} IP whitelists")
        except FileNotFoundError:
            logger.info("No IP whitelist file found, starting empty")
        except Exception as e:
            logger.error(f"Error loading IP whitelist: {e}")
    
    def _save_whitelists(self):
        """Сохраняет белые списки в файл"""
        try:
            data = {}
            for whitelist_id, whitelist in self.whitelists.items():
                data[whitelist_id] = {
                    'id': whitelist.id,
                    'name': whitelist.name,
                    'description': whitelist.description,
                    'allowed_ips': [asdict(ip) for ip in whitelist.allowed_ips],
                    'created_at': whitelist.created_at,
                    'updated_at': whitelist.updated_at,
                    'is_active': whitelist.is_active
                }
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.whitelists)} IP whitelists")
        except Exception as e:
            logger.error(f"Error saving IP whitelist: {e}")
    
    def create_whitelist(self, name: str, description: str = "") -> str:
        """Создает новый белый список IP"""
        whitelist_id = f"whitelist_{len(self.whitelists) + 1}_{int(datetime.now().timestamp())}"
        
        whitelist = IPWhitelist(
            id=whitelist_id,
            name=name,
            description=description,
            allowed_ips=[],
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        
        self.whitelists[whitelist_id] = whitelist
        self._save_whitelists()
        
        logger.info(f"Created IP whitelist: {name} ({whitelist_id})")
        return whitelist_id
    
    def add_allowed_ip(self, whitelist_id: str, ip: str, description: str = "", country: str = "") -> bool:
        """Добавляет разрешенный IP в белый список"""
        if whitelist_id not in self.whitelists:
            logger.error(f"IP whitelist {whitelist_id} not found")
            return False
        
        allowed_ip = AllowedIP(
            ip=ip,
            description=description,
            country=country,
            added_at=datetime.utcnow().isoformat()
        )
        
        self.whitelists[whitelist_id].allowed_ips.append(allowed_ip)
        self.whitelists[whitelist_id].updated_at = datetime.utcnow().isoformat()
        self._save_whitelists()
        
        logger.info(f"Added allowed IP {ip} to whitelist {whitelist_id}")
        return True
    
    def get_all_allowed_ips(self) -> Set[str]:
        """Получает все разрешенные IP адреса"""
        allowed_ips = set()
        
        for whitelist in self.whitelists.values():
            if not whitelist.is_active:
                continue
                
            for ip in whitelist.allowed_ips:
                if ip.is_active:
                    allowed_ips.add(ip.ip)
        
        logger.info(f"Found {len(allowed_ips)} allowed IPs")
        return allowed_ips
    
    def update_ip_status(self, ip: str, is_active: bool):
        """Обновляет статус IP"""
        for whitelist in self.whitelists.values():
            for allowed_ip in whitelist.allowed_ips:
                if allowed_ip.ip == ip:
                    allowed_ip.is_active = is_active
                    whitelist.updated_at = datetime.utcnow().isoformat()
                    self._save_whitelists()
                    logger.info(f"Updated IP {ip}: active={is_active}")
                    return True
        
        logger.warning(f"IP {ip} not found in any whitelist")
        return False
    
    def get_whitelist_stats(self) -> Dict:
        """Получает статистику по белым спискам"""
        stats = {
            'total_whitelists': len(self.whitelists),
            'active_whitelists': sum(1 for w in self.whitelists.values() if w.is_active),
            'total_ips': sum(len(w.allowed_ips) for w in self.whitelists.values()),
            'active_ips': sum(
                sum(1 for ip in w.allowed_ips if ip.is_active) 
                for w in self.whitelists.values() if w.is_active
            )
        }
        
        return stats
    
    def delete_whitelist(self, whitelist_id: str) -> bool:
        """Удаляет белый список"""
        if whitelist_id in self.whitelists:
            del self.whitelists[whitelist_id]
            self._save_whitelists()
            logger.info(f"Deleted IP whitelist {whitelist_id}")
            return True
        return False
    
    def get_all_whitelists(self) -> List[IPWhitelist]:
        """Получает все белые списки"""
        return list(self.whitelists.values())

# Глобальный экземпляр
whitelist_service = WhitelistService()
