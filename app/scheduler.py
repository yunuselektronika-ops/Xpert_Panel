import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from app.config import settings
from app.checker import checker

logger = logging.getLogger(__name__)

class SubscriptionScheduler:
    """Планировщик обновления подписок"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        self.last_update = None
        self.next_update = None
    
    async def update_job(self):
        """Задача обновления подписки"""
        logger.info(f"[{datetime.utcnow().isoformat()}] Running scheduled update...")
        
        try:
            subscription = await checker.update_subscription()
            self.last_update = datetime.utcnow()
            logger.info(f"Scheduled update completed: {subscription.active_configs} active configs")
        except Exception as e:
            logger.error(f"Scheduled update failed: {e}")
    
    def start(self):
        """Запуск планировщика"""
        if self.is_running:
            return
        
        # Добавляем задачу обновления каждый час
        self.scheduler.add_job(
            self.update_job,
            trigger=IntervalTrigger(hours=settings.UPDATE_INTERVAL_HOURS),
            id='subscription_update',
            name='Update VPN Subscription',
            replace_existing=True
        )
        
        self.scheduler.start()
        self.is_running = True
        logger.info(f"Scheduler started with {settings.UPDATE_INTERVAL_HOURS}-hour interval")
    
    def stop(self):
        """Остановка планировщика"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Scheduler stopped")
    
    def get_status(self) -> dict:
        """Статус планировщика"""
        jobs = self.scheduler.get_jobs() if self.is_running else []
        next_run = None
        
        for job in jobs:
            if job.id == 'subscription_update':
                next_run = job.next_run_time.isoformat() if job.next_run_time else None
        
        return {
            "is_running": self.is_running,
            "update_interval_hours": settings.UPDATE_INTERVAL_HOURS,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "next_update": next_run,
            "jobs_count": len(jobs)
        }
    
    async def trigger_update(self):
        """Ручной запуск обновления"""
        await self.update_job()


scheduler_service = SubscriptionScheduler()
