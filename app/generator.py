import base64
import json
from datetime import datetime, timedelta
from typing import List
from app.config import settings
from app.models import VPNConfig, AggregatedSubscription

class SubscriptionGenerator:
    """Генератор подписок в разных форматах"""
    
    def __init__(self):
        self.domain = settings.DOMAIN
        self.update_interval = settings.UPDATE_INTERVAL_HOURS
    
    def generate(self, configs: List[VPNConfig], format_type: str = "universal") -> str:
        """Генерация подписки в нужном формате"""
        if format_type == "base64":
            return self.generate_base64(configs)
        elif format_type == "clash":
            return self.generate_clash(configs)
        elif format_type == "surge":
            return self.generate_surge(configs)
        elif format_type == "happ":
            return self.generate_happ(configs)
        else:
            return self.generate_universal(configs)
    
    def generate_universal(self, configs: List[VPNConfig]) -> str:
        """Универсальный текстовый формат"""
        lines = []
        
        lines.append("# =========================================")
        lines.append(f"# Xpert Panel - Smart VPN Subscription")
        lines.append(f"# Domain: {self.domain}")
        lines.append(f"# Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
        lines.append(f"# Active servers: {len(configs)}")
        lines.append(f"# Auto-update: Every {self.update_interval} hour(s)")
        lines.append("# =========================================")
        lines.append("")
        
        for i, config in enumerate(configs, 1):
            quality = self._get_quality(config)
            lines.append(f"# [{i}] {config.remarks} | {config.protocol.upper()}")
            lines.append(f"# Quality: {quality} | Ping: {config.ping_ms:.0f}ms | Loss: {config.packet_loss:.0f}%")
            lines.append(config.raw)
            lines.append("")
        
        lines.append("# =========================================")
        lines.append(f"# Next update: {(datetime.utcnow() + timedelta(hours=self.update_interval)).strftime('%H:%M UTC')}")
        lines.append("# =========================================")
        
        return '\n'.join(lines)
    
    def generate_base64(self, configs: List[VPNConfig]) -> str:
        """Base64 формат (для большинства клиентов)"""
        raw_configs = [c.raw for c in configs]
        content = '\n'.join(raw_configs)
        return base64.b64encode(content.encode()).decode()
    
    def generate_happ(self, configs: List[VPNConfig]) -> str:
        """Формат для Happ/Proxy Utility"""
        lines = []
        
        lines.append(f"# Xpert Panel Subscription")
        lines.append(f"# Update-Interval: {self.update_interval * 3600}")
        lines.append(f"# Generated: {datetime.utcnow().isoformat()}")
        lines.append(f"# Configs: {len(configs)}")
        lines.append("")
        
        for config in configs:
            quality = self._get_quality(config)
            lines.append(f"# [{config.country}] {quality} - {config.ping_ms:.0f}ms")
            lines.append(config.raw)
            lines.append("")
        
        return '\n'.join(lines)
    
    def generate_clash(self, configs: List[VPNConfig]) -> str:
        """Clash YAML формат"""
        clash_config = {
            'port': 7890,
            'socks-port': 7891,
            'mixed-port': 7890,
            'allow-lan': False,
            'mode': 'rule',
            'log-level': 'info',
            'proxies': [],
            'proxy-groups': [
                {
                    'name': 'Auto',
                    'type': 'url-test',
                    'proxies': [],
                    'url': 'http://www.gstatic.com/generate_204',
                    'interval': 300
                },
                {
                    'name': 'Select',
                    'type': 'select',
                    'proxies': ['Auto']
                }
            ],
            'rules': [
                'MATCH,Auto'
            ]
        }
        
        for i, config in enumerate(configs):
            proxy_name = f"{config.remarks} [{config.ping_ms:.0f}ms]"
            
            proxy = {
                'name': proxy_name,
                'type': config.protocol if config.protocol in ['ss', 'vmess', 'trojan', 'vless'] else 'http',
                'server': config.server,
                'port': config.port
            }
            
            clash_config['proxies'].append(proxy)
            clash_config['proxy-groups'][0]['proxies'].append(proxy_name)
            clash_config['proxy-groups'][1]['proxies'].append(proxy_name)
        
        import yaml
        return yaml.dump(clash_config, allow_unicode=True, sort_keys=False, default_flow_style=False)
    
    def generate_surge(self, configs: List[VPNConfig]) -> str:
        """Surge формат"""
        lines = []
        
        lines.append(f"#!MANAGED-CONFIG https://{self.domain}/sub interval={self.update_interval * 3600}")
        lines.append("")
        lines.append("[Proxy]")
        
        for config in configs:
            name = f"{config.remarks} [{config.ping_ms:.0f}ms]"
            lines.append(f"{name} = custom, {config.server}, {config.port}, chacha20-ietf-poly1305, password")
        
        lines.append("")
        lines.append("[Proxy Group]")
        lines.append("Auto = url-test, " + ", ".join([f"{c.remarks} [{c.ping_ms:.0f}ms]" for c in configs[:10]]) + ", url=http://www.gstatic.com/generate_204, interval=300")
        
        return '\n'.join(lines)
    
    def _get_quality(self, config: VPNConfig) -> str:
        """Определение качества соединения"""
        ping = config.ping_ms
        loss = config.packet_loss
        
        if ping < 50 and loss < 1:
            return "EXCELLENT"
        elif ping < 100 and loss < 5:
            return "GOOD"
        elif ping < 200 and loss < 10:
            return "FAIR"
        elif ping < 300 and loss < 20:
            return "POOR"
        else:
            return "BAD"
    
    def get_subscription_headers(self) -> dict:
        """HTTP заголовки для автообновления подписки"""
        return {
            'Content-Type': 'text/plain; charset=utf-8',
            'Subscription-Userinfo': 'upload=0; download=0; total=107374182400; expire=2546246231',
            'Profile-Update-Interval': str(self.update_interval),
            'Profile-Web-Page-Url': f'https://{self.domain}',
            'Cache-Control': f'public, max-age={self.update_interval * 3600}',
            'X-Subscription-Userinfo': 'upload=0; download=0; total=107374182400; expire=2546246231'
        }


generator = SubscriptionGenerator()
