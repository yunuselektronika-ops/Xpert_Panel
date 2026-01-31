from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import List, Optional

from app.xpert.service import xpert_service
from app.xpert.marzban_integration import marzban_integration
from app.xpert.ping_stats import ping_stats_service
import config

router = APIRouter(prefix="/xpert", tags=["Xpert Panel"])


class SourceCreate(BaseModel):
    name: str
    url: str
    priority: int = 1


class SourceResponse(BaseModel):
    id: int
    name: str
    url: str
    enabled: bool
    priority: int
    config_count: int
    success_rate: float


class PingReport(BaseModel):
    server: str
    port: int
    protocol: str
    ping_ms: float
    success: bool


class StatsResponse(BaseModel):
    total_sources: int
    enabled_sources: int
    total_configs: int
    active_configs: int
    avg_ping: float
    target_ips: List[str]
    domain: str


@router.get("/clusters")
async def get_clusters():
    """Получить все кластеры"""
    try:
        from app.xpert.cluster_service import cluster_service
        clusters = cluster_service.get_all_clusters()
        return {
            "clusters": [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "servers_count": len(c.servers),
                    "active_servers": sum(1 for s in c.servers if s.is_active),
                    "created_at": c.created_at,
                    "updated_at": c.updated_at,
                    "is_active": c.is_active
                }
                for c in clusters
            ],
            "stats": cluster_service.get_cluster_stats()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clusters")
async def create_cluster(data: dict):
    """Создать новый кластер"""
    try:
        from app.xpert.cluster_service import cluster_service
        
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            raise HTTPException(status_code=400, detail="Cluster name is required")
        
        cluster_id = cluster_service.create_cluster(name, description)
        return {"cluster_id": cluster_id, "message": "Cluster created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/clusters/{cluster_id}/servers")
async def add_server_to_cluster(cluster_id: str, data: dict):
    """Добавить сервер в кластер"""
    try:
        from app.xpert.cluster_service import cluster_service
        
        ip = data.get('ip', '').strip()
        domain = data.get('domain', '').strip()
        host = data.get('host', '').strip()
        sni = data.get('sni', '').strip()
        port = data.get('port', 443)
        country = data.get('country', '').strip()
        
        if not ip:
            raise HTTPException(status_code=400, detail="IP address is required")
        
        success = cluster_service.add_server_to_cluster(
            cluster_id, ip, domain, host, sni, port, country
        )
        
        if success:
            return {"message": "Server added successfully"}
        else:
            raise HTTPException(status_code=404, detail="Cluster not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/clusters/{cluster_id}/servers")
async def get_cluster_servers(cluster_id: str):
    """Получить сервера кластера"""
    try:
        from app.xpert.cluster_service import cluster_service
        
        clusters = cluster_service.get_all_clusters()
        cluster = next((c for c in clusters if c.id == cluster_id), None)
        
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")
        
        return {
            "cluster_id": cluster_id,
            "cluster_name": cluster.name,
            "servers": [
                {
                    "ip": s.ip,
                    "domain": s.domain,
                    "host": s.host,
                    "sni": s.sni,
                    "port": s.port,
                    "country": s.country,
                    "is_active": s.is_active,
                    "last_check": s.last_check,
                    "ping_ms": s.ping_ms
                }
                for s in cluster.servers
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/clusters/{cluster_id}/servers/{server_ip}/status")
async def update_server_status(cluster_id: str, server_ip: str, data: dict):
    """Обновить статус сервера"""
    try:
        from app.xpert.cluster_service import cluster_service
        
        is_active = data.get('is_active', True)
        ping_ms = data.get('ping_ms', 0.0)
        
        success = cluster_service.update_server_status(server_ip, is_active, ping_ms)
        
        if success:
            return {"message": "Server status updated successfully"}
        else:
            raise HTTPException(status_code=404, detail="Server not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clusters/{cluster_id}")
async def delete_cluster(cluster_id: str):
    """Удалить кластер"""
    try:
        from app.xpert.cluster_service import cluster_service
        
        success = cluster_service.delete_cluster(cluster_id)
        
        if success:
            return {"message": "Cluster deleted successfully"}
        else:
            raise HTTPException(status_code=404, detail="Cluster not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/active-servers")
async def get_active_servers():
    """Получить все активные сервера для подписки"""
    try:
        from app.xpert.cluster_service import cluster_service
        servers = cluster_service.get_active_servers()
        
        return {
            "servers": [
                {
                    "ip": s.ip,
                    "domain": s.domain,
                    "host": s.host,
                    "sni": s.sni,
                    "port": s.port,
                    "country": s.country,
                    "ping_ms": s.ping_ms
                }
                for s in servers
            ],
            "total": len(servers)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/stats")
async def get_stats():
    """Получение статистики Xpert Panel"""
    return xpert_service.get_stats()


@router.get("/sources")
async def get_sources():
    """Получение списка источников подписок"""
    sources = xpert_service.get_sources()
    return [
        {
            "id": s.id,
            "name": s.name,
            "url": s.url,
            "enabled": s.enabled,
            "priority": s.priority,
            "config_count": s.config_count,
            "success_rate": s.success_rate,
            "last_fetched": s.last_fetched
        }
        for s in sources
    ]


@router.post("/sources")
async def add_source(source: SourceCreate):
    """Добавление источника подписки"""
    try:
        s = xpert_service.add_source(source.name, source.url, source.priority)
        return {
            "id": s.id,
            "name": s.name,
            "url": s.url,
            "enabled": s.enabled,
            "priority": s.priority,
            "config_count": s.config_count,
            "success_rate": s.success_rate
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/sources/{source_id}")
async def delete_source(source_id: int):
    """Удаление источника подписки"""
    if xpert_service.delete_source(source_id):
        return {"success": True}
    raise HTTPException(status_code=404, detail="Source not found")


@router.post("/sources/{source_id}/toggle")
async def toggle_source(source_id: int):
    """Включение/выключение источника"""
    source = xpert_service.toggle_source(source_id)
    if source:
        return {"success": True, "enabled": source.enabled}
    raise HTTPException(status_code=404, detail="Source not found")


@router.post("/update")
async def force_update():
    """Принудительное обновление подписок"""
    try:
        # Увеличиваем таймаут для долгих операций
        import asyncio
        result = await asyncio.wait_for(xpert_service.update_subscription(), timeout=300)  # 5 минут
        return {"success": True, **result}
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Update timeout - operation took too long")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configs")
async def get_configs():
    """Получение списка конфигураций"""
    configs = xpert_service.get_all_configs()
    return [
        {
            "id": c.id,
            "protocol": c.protocol,
            "server": c.server,
            "port": c.port,
            "remarks": c.remarks,
            "ping_ms": c.ping_ms,
            "packet_loss": c.packet_loss,
            "is_active": c.is_active
        }
        for c in configs
    ]


@router.post("/test-url")
async def test_subscription_url(url_data: dict):
    """Тестирование URL подписки перед добавлением"""
    url = url_data.get("url", "")
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    try:
        configs = await checker.fetch_subscription(url)
        return {
            "success": True,
            "url": url,
            "config_count": len(configs),
            "sample_configs": configs[:3]  # Показываем первые 3 конфига для примера
        }
    except Exception as e:
        return {
            "success": False,
            "url": url,
            "error": str(e),
            "config_count": 0
        }


@router.post("/sync-marzban")
async def sync_to_marzban():
    """Принудительная синхронизация с Marzban"""
    try:
        result = marzban_integration.sync_active_configs_to_marzban()
        return {"success": True, **result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ping-report")
async def report_ping(ping_data: PingReport, user_id: int = 1):
    """Запись результата пинга от пользователя"""
    try:
        ping_stats_service.record_ping(
            server=ping_data.server,
            port=ping_data.port,
            protocol=ping_data.protocol,
            user_id=user_id,
            ping_ms=ping_data.ping_ms,
            success=ping_data.success
        )
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/server-health/{server}/{port}/{protocol}")
async def get_server_health(server: str, port: int, protocol: str):
    """Получение статистики здоровья сервера"""
    try:
        health = ping_stats_service.get_server_health(server, port, protocol)
        return health
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/ping-stats")
async def get_ping_stats():
    """Получение сводной статистики пингов"""
    try:
        return ping_stats_service.get_stats_summary()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup-stats")
async def cleanup_ping_stats(days: int = 7):
    """Очистка старой статистики"""
    try:
        ping_stats_service.cleanup_old_stats(days)
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top-configs")
async def get_top_configs(limit: int = 10):
    """Получение топ-N конфигов с их score"""
    try:
        configs = xpert_service.get_active_configs()
        
        # Получаем топ конфиги с score
        try:
            from app.xpert.ping_stats import ping_stats_service
            import config as app_config
            
            # Фильтруем здоровые
            healthy_configs = ping_stats_service.get_healthy_configs(configs)
            
            # Получаем топ с score
            top_limit = min(limit, app_config.XPERT_TOP_SERVERS_LIMIT)
            top_configs = ping_stats_service.get_top_configs(healthy_configs, top_limit)
            
            # Добавляем score для отображения
            result = []
            for config in top_configs:
                health = ping_stats_service.get_server_health(config.server, config.port, config.protocol)
                score = 0
                
                if health['healthy'] is None:
                    score = ping_stats_service._calculate_original_score(config)
                elif health['healthy']:
                    score = ping_stats_service._calculate_stats_score(health, config)
                
                result.append({
                    "id": config.id,
                    "protocol": config.protocol,
                    "server": config.server,
                    "port": config.port,
                    "remarks": config.remarks,
                    "ping_ms": config.ping_ms,
                    "packet_loss": config.packet_loss,
                    "is_active": config.is_active,
                    "score": round(score, 2),
                    "health": health
                })
            
            return {"configs": result, "total": len(result)}
            
        except Exception as e:
            # Если статистика недоступна, возвращаем базовые конфиги
            return {"configs": configs[:limit], "total": len(configs[:limit])}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/queue-configs")
async def get_queue_configs():
    """Получение конфигов в очереди (не попавших в топ)"""
    try:
        configs = xpert_service.get_active_configs()
        
        # Получаем топ конфиги
        try:
            from app.xpert.ping_stats import ping_stats_service
            import config as app_config
            
            # Фильтруем здоровые
            healthy_configs = ping_stats_service.get_healthy_configs(configs)
            
            # Получаем топ
            top_limit = app_config.XPERT_TOP_SERVERS_LIMIT
            top_configs = ping_stats_service.get_top_configs(healthy_configs, top_limit)
            
            # Очередь = все здоровые минус топ
            top_servers = {(c.server, c.port, c.protocol) for c in top_configs}
            queue_configs = [
                c for c in healthy_configs 
                if (c.server, c.port, c.protocol) not in top_servers
            ]
            
            return {"configs": queue_configs, "total": len(queue_configs)}
            
        except Exception as e:
            # Если статистика недоступна, возвращаем пустую очередь
            return {"configs": [], "total": 0}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sub")
async def get_subscription(format: str = "universal"):
    """Получение агрегированной подписки"""
    content = xpert_service.generate_subscription(format)
    
    headers = {
        "Content-Type": "text/plain; charset=utf-8",
        "Profile-Update-Interval": "1",
        "Subscription-Userinfo": "upload=0; download=0; total=0; expire=0",
        "Profile-Title": "Xpert Panel"
    }
    
    return PlainTextResponse(content=content, headers=headers)
