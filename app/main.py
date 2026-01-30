import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Form, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from app.config import settings
from app.storage import storage
from app.models import SubscriptionSource
from app.checker import checker
from app.generator import generator
from app.scheduler import scheduler_service

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle management"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    
    # Запускаем планировщик
    scheduler_service.start()
    
    # Первоначальное обновление при старте
    asyncio.create_task(initial_update())
    
    yield
    
    # Остановка
    scheduler_service.stop()
    logger.info("Shutting down...")


async def initial_update():
    """Первоначальное обновление при запуске"""
    await asyncio.sleep(2)  # Даем время на инициализацию
    sources = storage.get_sources()
    if sources:
        logger.info("Running initial subscription update...")
        try:
            await checker.update_subscription()
        except Exception as e:
            logger.error(f"Initial update failed: {e}")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)


# Pydantic models
class SourceCreate(BaseModel):
    name: str
    url: str
    priority: int = 1


class SourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    priority: Optional[int] = None
    enabled: Optional[bool] = None


# HTML Templates
ADMIN_HTML = '''
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Xpert Panel - Admin</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Inter', sans-serif; }
        .gradient-bg { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
        .card { background: white; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    </style>
</head>
<body class="bg-gray-100 min-h-screen">
    <!-- Header -->
    <header class="gradient-bg text-white py-6 px-4 shadow-lg">
        <div class="max-w-6xl mx-auto">
            <h1 class="text-3xl font-bold">⚡ Xpert Panel</h1>
            <p class="text-purple-200 mt-1">VPN Subscription Aggregator</p>
        </div>
    </header>

    <main class="max-w-6xl mx-auto px-4 py-8">
        <!-- Stats Cards -->
        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
            <div class="card p-4">
                <div class="text-gray-500 text-sm">Источников</div>
                <div class="text-2xl font-bold text-purple-600" id="stat-sources">0</div>
            </div>
            <div class="card p-4">
                <div class="text-gray-500 text-sm">Активных конфигов</div>
                <div class="text-2xl font-bold text-green-600" id="stat-configs">0</div>
            </div>
            <div class="card p-4">
                <div class="text-gray-500 text-sm">Последнее обновление</div>
                <div class="text-lg font-semibold text-gray-700" id="stat-update">-</div>
            </div>
            <div class="card p-4">
                <div class="text-gray-500 text-sm">Интервал обновления</div>
                <div class="text-2xl font-bold text-blue-600" id="stat-interval">1ч</div>
            </div>
        </div>

        <!-- Add Source Form -->
        <div class="card p-6 mb-8">
            <h2 class="text-xl font-semibold mb-4">➕ Добавить источник подписки</h2>
            <form id="add-source-form" class="space-y-4">
                <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-gray-700 mb-1">Название</label>
                        <input type="text" id="source-name" placeholder="Мой VPN" 
                            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent">
                    </div>
                    <div class="md:col-span-2">
                        <label class="block text-sm font-medium text-gray-700 mb-1">URL подписки</label>
                        <input type="url" id="source-url" placeholder="https://example.com/subscribe" 
                            class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent">
                    </div>
                </div>
                <button type="submit" 
                    class="bg-purple-600 hover:bg-purple-700 text-white font-medium py-2 px-6 rounded-lg transition">
                    Добавить
                </button>
            </form>
        </div>

        <!-- Sources List -->
        <div class="card p-6 mb-8">
            <div class="flex justify-between items-center mb-4">
                <h2 class="text-xl font-semibold">📋 Источники подписок</h2>
                <button onclick="refreshSources()" class="text-purple-600 hover:text-purple-800">
                    🔄 Обновить список
                </button>
            </div>
            <div id="sources-list" class="space-y-3">
                <p class="text-gray-500">Загрузка...</p>
            </div>
        </div>

        <!-- Subscription URL -->
        <div class="card p-6 mb-8">
            <h2 class="text-xl font-semibold mb-4">🔗 Ваша подписка</h2>
            <div class="bg-gray-50 p-4 rounded-lg">
                <p class="text-sm text-gray-600 mb-2">URL для добавления в Happ/Shadowrocket/Clash:</p>
                <div class="flex items-center gap-2">
                    <input type="text" id="sub-url" readonly
                        class="flex-1 px-4 py-2 bg-white border border-gray-300 rounded-lg font-mono text-sm">
                    <button onclick="copySubUrl()" 
                        class="bg-green-600 hover:bg-green-700 text-white font-medium py-2 px-4 rounded-lg transition">
                        📋 Копировать
                    </button>
                </div>
                <p class="text-xs text-gray-500 mt-2">Подписка обновляется автоматически каждый час</p>
            </div>
            
            <div class="mt-4 grid grid-cols-2 md:grid-cols-4 gap-2">
                <a href="/sub" target="_blank" class="text-center py-2 px-4 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">
                    Universal
                </a>
                <a href="/sub?format=base64" target="_blank" class="text-center py-2 px-4 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">
                    Base64
                </a>
                <a href="/sub?format=clash" target="_blank" class="text-center py-2 px-4 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">
                    Clash
                </a>
                <a href="/sub?format=happ" target="_blank" class="text-center py-2 px-4 bg-gray-100 hover:bg-gray-200 rounded-lg text-sm">
                    Happ
                </a>
            </div>
        </div>

        <!-- Actions -->
        <div class="card p-6">
            <h2 class="text-xl font-semibold mb-4">⚙️ Действия</h2>
            <div class="flex flex-wrap gap-4">
                <button onclick="forceUpdate()" 
                    class="bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-6 rounded-lg transition">
                    🔄 Обновить подписку сейчас
                </button>
                <button onclick="viewConfigs()" 
                    class="bg-gray-600 hover:bg-gray-700 text-white font-medium py-2 px-6 rounded-lg transition">
                    📊 Просмотреть конфиги
                </button>
            </div>
            <div id="update-status" class="mt-4 text-sm text-gray-600"></div>
        </div>

        <!-- Configs Modal -->
        <div id="configs-modal" class="fixed inset-0 bg-black bg-opacity-50 hidden items-center justify-center z-50">
            <div class="bg-white rounded-xl max-w-4xl w-full mx-4 max-h-[80vh] overflow-hidden">
                <div class="p-4 border-b flex justify-between items-center">
                    <h3 class="text-lg font-semibold">Активные конфигурации</h3>
                    <button onclick="closeConfigsModal()" class="text-gray-500 hover:text-gray-700">✕</button>
                </div>
                <div id="configs-content" class="p-4 overflow-y-auto max-h-[60vh]">
                    <p class="text-gray-500">Загрузка...</p>
                </div>
            </div>
        </div>
    </main>

    <footer class="text-center py-6 text-gray-500 text-sm">
        Xpert Panel v1.0.0 | Domain: <span id="domain-info"></span>
    </footer>

    <script>
        const API_BASE = '';
        const DOMAIN = window.location.host;
        
        document.getElementById('domain-info').textContent = DOMAIN;
        document.getElementById('sub-url').value = `${window.location.protocol}//${DOMAIN}/sub`;

        // Load stats
        async function loadStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                document.getElementById('stat-sources').textContent = data.total_sources || 0;
                document.getElementById('stat-configs').textContent = data.active_configs || 0;
                document.getElementById('stat-interval').textContent = (data.update_interval_hours || 1) + 'ч';
                
                if (data.last_update) {
                    const date = new Date(data.last_update);
                    document.getElementById('stat-update').textContent = date.toLocaleTimeString();
                }
            } catch (e) {
                console.error('Failed to load stats:', e);
            }
        }

        // Load sources
        async function loadSources() {
            try {
                const res = await fetch('/api/sources');
                const sources = await res.json();
                
                const container = document.getElementById('sources-list');
                
                if (sources.length === 0) {
                    container.innerHTML = '<p class="text-gray-500">Нет добавленных источников. Добавьте первый!</p>';
                    return;
                }
                
                container.innerHTML = sources.map(s => `
                    <div class="flex items-center justify-between p-3 bg-gray-50 rounded-lg ${!s.enabled ? 'opacity-50' : ''}">
                        <div class="flex-1">
                            <div class="font-medium">${s.name}</div>
                            <div class="text-sm text-gray-500 truncate max-w-md">${s.url}</div>
                            <div class="text-xs text-gray-400 mt-1">
                                Конфигов: ${s.config_count || 0} | 
                                Успех: ${(s.success_rate || 0).toFixed(0)}% |
                                ${s.last_fetched ? 'Обновлено: ' + new Date(s.last_fetched).toLocaleTimeString() : 'Не обновлялось'}
                            </div>
                        </div>
                        <div class="flex items-center gap-2 ml-4">
                            <button onclick="toggleSource('${s.id}')" 
                                class="${s.enabled ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'} px-3 py-1 rounded text-sm">
                                ${s.enabled ? 'Вкл' : 'Выкл'}
                            </button>
                            <button onclick="deleteSource('${s.id}')" 
                                class="bg-red-100 text-red-700 px-3 py-1 rounded text-sm hover:bg-red-200">
                                Удалить
                            </button>
                        </div>
                    </div>
                `).join('');
            } catch (e) {
                console.error('Failed to load sources:', e);
            }
        }

        // Add source
        document.getElementById('add-source-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const name = document.getElementById('source-name').value.trim();
            const url = document.getElementById('source-url').value.trim();
            
            if (!name || !url) {
                alert('Заполните все поля');
                return;
            }
            
            try {
                const res = await fetch('/api/sources', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, url, priority: 1 })
                });
                
                if (res.ok) {
                    document.getElementById('source-name').value = '';
                    document.getElementById('source-url').value = '';
                    loadSources();
                    loadStats();
                } else {
                    const err = await res.json();
                    alert(err.detail || 'Ошибка добавления');
                }
            } catch (e) {
                alert('Ошибка: ' + e.message);
            }
        });

        // Toggle source
        async function toggleSource(id) {
            try {
                await fetch(`/api/sources/${id}/toggle`, { method: 'POST' });
                loadSources();
            } catch (e) {
                console.error('Failed to toggle source:', e);
            }
        }

        // Delete source
        async function deleteSource(id) {
            if (!confirm('Удалить этот источник?')) return;
            
            try {
                await fetch(`/api/sources/${id}`, { method: 'DELETE' });
                loadSources();
                loadStats();
            } catch (e) {
                console.error('Failed to delete source:', e);
            }
        }

        // Refresh sources
        function refreshSources() {
            loadSources();
            loadStats();
        }

        // Force update
        async function forceUpdate() {
            const status = document.getElementById('update-status');
            status.textContent = '⏳ Обновление подписки...';
            
            try {
                const res = await fetch('/api/update', { method: 'POST' });
                const data = await res.json();
                
                if (data.success) {
                    status.textContent = `✅ Обновлено! Активных конфигов: ${data.active_configs}`;
                    loadStats();
                    loadSources();
                } else {
                    status.textContent = '❌ Ошибка обновления';
                }
            } catch (e) {
                status.textContent = '❌ Ошибка: ' + e.message;
            }
        }

        // View configs
        async function viewConfigs() {
            const modal = document.getElementById('configs-modal');
            const content = document.getElementById('configs-content');
            
            modal.classList.remove('hidden');
            modal.classList.add('flex');
            content.innerHTML = '<p class="text-gray-500">Загрузка...</p>';
            
            try {
                const res = await fetch('/api/configs');
                const configs = await res.json();
                
                if (configs.length === 0) {
                    content.innerHTML = '<p class="text-gray-500">Нет активных конфигураций</p>';
                    return;
                }
                
                content.innerHTML = `
                    <table class="w-full text-sm">
                        <thead class="bg-gray-100">
                            <tr>
                                <th class="p-2 text-left">#</th>
                                <th class="p-2 text-left">Протокол</th>
                                <th class="p-2 text-left">Сервер</th>
                                <th class="p-2 text-left">Пинг</th>
                                <th class="p-2 text-left">Потери</th>
                                <th class="p-2 text-left">Статус</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${configs.map((c, i) => `
                                <tr class="border-b">
                                    <td class="p-2">${i + 1}</td>
                                    <td class="p-2 font-mono">${c.protocol.toUpperCase()}</td>
                                    <td class="p-2 font-mono text-xs">${c.server}:${c.port}</td>
                                    <td class="p-2 ${c.ping_ms < 100 ? 'text-green-600' : c.ping_ms < 200 ? 'text-yellow-600' : 'text-red-600'}">
                                        ${c.ping_ms.toFixed(0)}ms
                                    </td>
                                    <td class="p-2">${c.packet_loss.toFixed(0)}%</td>
                                    <td class="p-2">
                                        <span class="${c.is_active ? 'text-green-600' : 'text-red-600'}">
                                            ${c.is_active ? '✓ Active' : '✗ Inactive'}
                                        </span>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;
            } catch (e) {
                content.innerHTML = '<p class="text-red-500">Ошибка загрузки: ' + e.message + '</p>';
            }
        }

        function closeConfigsModal() {
            const modal = document.getElementById('configs-modal');
            modal.classList.add('hidden');
            modal.classList.remove('flex');
        }

        // Copy subscription URL
        function copySubUrl() {
            const input = document.getElementById('sub-url');
            input.select();
            document.execCommand('copy');
            alert('URL скопирован!');
        }

        // Initial load
        loadStats();
        loadSources();
        
        // Auto-refresh every 30 seconds
        setInterval(() => {
            loadStats();
        }, 30000);
    </script>
</body>
</html>
'''


# Routes
@app.get("/", response_class=HTMLResponse)
async def admin_page():
    """Админ панель"""
    return HTMLResponse(content=ADMIN_HTML)


@app.get("/sub")
async def get_subscription(
    format: str = Query("universal", description="Format: universal, base64, clash, surge, happ")
):
    """Получение подписки"""
    subscription = storage.get_subscription()
    
    if not subscription or not subscription.configs:
        # Если нет подписки, возвращаем пустую
        content = "# No active configurations yet. Add sources and wait for update."
        return PlainTextResponse(
            content=content,
            headers=generator.get_subscription_headers()
        )
    
    # Генерируем подписку в нужном формате
    content = generator.generate(subscription.configs, format)
    
    return PlainTextResponse(
        content=content,
        headers=generator.get_subscription_headers()
    )


# API Routes
@app.get("/api/stats")
async def get_stats():
    """Статистика"""
    return storage.get_stats()


@app.get("/api/sources")
async def get_sources():
    """Список источников"""
    sources = storage.get_sources()
    return [s.to_dict() for s in sources]


@app.post("/api/sources")
async def add_source(source: SourceCreate):
    """Добавление источника"""
    new_source = SubscriptionSource(
        name=source.name,
        url=source.url,
        priority=source.priority
    )
    
    if storage.add_source(new_source):
        return {"success": True, "source": new_source.to_dict()}
    else:
        raise HTTPException(status_code=400, detail="Source with this URL already exists")


@app.delete("/api/sources/{source_id}")
async def delete_source(source_id: str):
    """Удаление источника"""
    if storage.remove_source(source_id):
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail="Source not found")


@app.post("/api/sources/{source_id}/toggle")
async def toggle_source(source_id: str):
    """Включение/выключение источника"""
    if storage.toggle_source(source_id):
        return {"success": True}
    else:
        raise HTTPException(status_code=404, detail="Source not found")


@app.get("/api/configs")
async def get_configs():
    """Список конфигураций"""
    configs = storage.get_configs()
    return [c.to_dict() for c in configs]


@app.post("/api/update")
async def force_update():
    """Принудительное обновление подписки"""
    try:
        subscription = await checker.update_subscription()
        return {
            "success": True,
            "active_configs": subscription.active_configs,
            "generated_at": subscription.generated_at
        }
    except Exception as e:
        logger.error(f"Force update failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/scheduler")
async def get_scheduler_status():
    """Статус планировщика"""
    return scheduler_service.get_status()


@app.get("/health")
async def health_check():
    """Health check"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.VERSION,
        "domain": settings.DOMAIN
    }
