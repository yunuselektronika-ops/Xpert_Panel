import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class ClusterServer:
    """Один сервер в кластере"""
    ip: str
    domain: str = ""
    host: str = ""
    sni: str = ""
    port: int = 443
    country: str = ""
    is_active: bool = True
    last_check: str = ""
    ping_ms: float = 0.0

@dataclass 
class Cluster:
    """Кластер серверов"""
    id: str
    name: str
    description: str
    servers: List[ClusterServer]
    created_at: str
    updated_at: str
    is_active: bool = True

class ClusterService:
    """Сервис управления кластерами серверов"""
    
    def __init__(self):
        self.clusters: Dict[str, Cluster] = {}
        self.storage_file = "clusters.json"
        self._load_clusters()
    
    def _load_clusters(self):
        """Загружает кластеры из файла"""
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for cluster_id, cluster_data in data.items():
                    servers = [ClusterServer(**s) for s in cluster_data['servers']]
                    self.clusters[cluster_id] = Cluster(
                        id=cluster_data['id'],
                        name=cluster_data['name'],
                        description=cluster_data['description'],
                        servers=servers,
                        created_at=cluster_data['created_at'],
                        updated_at=cluster_data['updated_at'],
                        is_active=cluster_data.get('is_active', True)
                    )
                logger.info(f"Loaded {len(self.clusters)} clusters")
        except FileNotFoundError:
            logger.info("No clusters file found, starting empty")
        except Exception as e:
            logger.error(f"Error loading clusters: {e}")
    
    def _save_clusters(self):
        """Сохраняет кластеры в файл"""
        try:
            data = {}
            for cluster_id, cluster in self.clusters.items():
                data[cluster_id] = {
                    'id': cluster.id,
                    'name': cluster.name,
                    'description': cluster.description,
                    'servers': [asdict(server) for server in cluster.servers],
                    'created_at': cluster.created_at,
                    'updated_at': cluster.updated_at,
                    'is_active': cluster.is_active
                }
            
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(self.clusters)} clusters")
        except Exception as e:
            logger.error(f"Error saving clusters: {e}")
    
    def create_cluster(self, name: str, description: str = "") -> str:
        """Создает новый кластер"""
        cluster_id = f"cluster_{len(self.clusters) + 1}_{int(datetime.now().timestamp())}"
        
        cluster = Cluster(
            id=cluster_id,
            name=name,
            description=description,
            servers=[],
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat()
        )
        
        self.clusters[cluster_id] = cluster
        self._save_clusters()
        
        logger.info(f"Created cluster: {name} ({cluster_id})")
        return cluster_id
    
    def add_server_to_cluster(self, cluster_id: str, ip: str, domain: str = "", 
                            host: str = "", sni: str = "", port: int = 443, 
                            country: str = "") -> bool:
        """Добавляет сервер в кластер"""
        if cluster_id not in self.clusters:
            logger.error(f"Cluster {cluster_id} not found")
            return False
        
        server = ClusterServer(
            ip=ip,
            domain=domain,
            host=host,
            sni=sni,
            port=port,
            country=country,
            last_check=datetime.utcnow().isoformat()
        )
        
        self.clusters[cluster_id].servers.append(server)
        self.clusters[cluster_id].updated_at = datetime.utcnow().isoformat()
        self._save_clusters()
        
        logger.info(f"Added server {ip} to cluster {cluster_id}")
        return True
    
    def get_active_servers(self) -> List[ClusterServer]:
        """Получает все активные сервера из всех кластеров"""
        active_servers = []
        
        for cluster in self.clusters.values():
            if not cluster.is_active:
                continue
                
            for server in cluster.servers:
                if server.is_active:
                    active_servers.append(server)
        
        logger.info(f"Found {len(active_servers)} active servers")
        return active_servers
    
    def update_server_status(self, ip: str, is_active: bool, ping_ms: float = 0.0):
        """Обновляет статус сервера"""
        for cluster in self.clusters.values():
            for server in cluster.servers:
                if server.ip == ip:
                    server.is_active = is_active
                    server.ping_ms = ping_ms
                    server.last_check = datetime.utcnow().isoformat()
                    cluster.updated_at = datetime.utcnow().isoformat()
                    self._save_clusters()
                    logger.info(f"Updated server {ip}: active={is_active}, ping={ping_ms}ms")
                    return True
        
        logger.warning(f"Server {ip} not found in any cluster")
        return False
    
    def get_cluster_stats(self) -> Dict:
        """Получает статистику по кластерам"""
        stats = {
            'total_clusters': len(self.clusters),
            'active_clusters': sum(1 for c in self.clusters.values() if c.is_active),
            'total_servers': sum(len(c.servers) for c in self.clusters.values()),
            'active_servers': sum(
                sum(1 for s in c.servers if s.is_active) 
                for c in self.clusters.values() if c.is_active
            )
        }
        
        return stats
    
    def delete_cluster(self, cluster_id: str) -> bool:
        """Удаляет кластер"""
        if cluster_id in self.clusters:
            del self.clusters[cluster_id]
            self._save_clusters()
            logger.info(f"Deleted cluster {cluster_id}")
            return True
        return False
    
    def get_all_clusters(self) -> List[Cluster]:
        """Получает все кластеры"""
        return list(self.clusters.values())

# Глобальный экземпляр
cluster_service = ClusterService()
