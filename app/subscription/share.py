import base64
import random
import secrets
from collections import defaultdict
from datetime import datetime as dt
from datetime import timedelta
from typing import TYPE_CHECKING, List, Literal, Union

from jdatetime import date as jd

from app import xray
from app.utils.system import get_public_ip, get_public_ipv6, readable_size

from . import *

if TYPE_CHECKING:
    from app.models.user import UserResponse

from config import (
    ACTIVE_STATUS_TEXT,
    DISABLED_STATUS_TEXT,
    EXPIRED_STATUS_TEXT,
    LIMITED_STATUS_TEXT,
    ONHOLD_STATUS_TEXT,
)

SERVER_IP = get_public_ip()
SERVER_IPV6 = get_public_ipv6()

STATUS_EMOJIS = {
    "active": "✅",
    "expired": "⌛️",
    "limited": "🪫",
    "disabled": "❌",
    "on_hold": "🔌",
}

STATUS_TEXTS = {
    "active": ACTIVE_STATUS_TEXT,
    "expired": EXPIRED_STATUS_TEXT,
    "limited": LIMITED_STATUS_TEXT,
    "disabled": DISABLED_STATUS_TEXT,
    "on_hold": ONHOLD_STATUS_TEXT,
}


def generate_v2ray_links(proxies: dict, inbounds: dict, extra_data: dict, reverse: bool) -> list:
    format_variables = setup_format_variables(extra_data)
    conf = V2rayShareLink()
    
    # Добавляем обычные конфиги Marzban
    marzban_links = process_inbounds_and_tags(inbounds, proxies, format_variables, conf=conf, reverse=reverse)
    
    # Добавляем конфиги из Xpert Panel только для активных пользователей
    try:
        from app.xpert.service import xpert_service
        import config as app_config
        
        # Если проверка статуса отключена в настройках, всегда добавляем
        if not app_config.XPERT_REQUIRE_ACTIVE_STATUS:
            xpert_configs = xpert_service.get_active_configs()
            for config in xpert_configs:
                conf.add_link(config.raw)
            return conf.render(reverse=reverse)
        
        # Проверяем статус пользователя
        user_status = extra_data.get('status', '')
        data_limit = extra_data.get('data_limit', 0)
        used_traffic = extra_data.get('used_traffic', 0)
        expire = extra_data.get('expire', 0)
        
        # Если пользователь неактивен, не добавляем Xpert конфиги
        if user_status not in ['active', 'on_hold']:
            return conf.render(reverse=reverse)
            
        # Если закончился трафик, не добавляем Xpert конфиги
        if data_limit > 0 and used_traffic >= data_limit:
            return conf.render(reverse=reverse)
            
        # Если истек срок, не добавляем Xpert конфиги
        if expire > 0 and expire <= 0:
            return conf.render(reverse=reverse)
        
        # Если все ок, добавляем конфиги из Xpert Panel с учетом реальной статистики
        xpert_configs = xpert_service.get_active_configs()
        
        # Фильтруем и берем только топ серверы
        try:
            from app.xpert.ping_stats import ping_stats_service
            import config as app_config
            
            # Сначала фильтруем нездоровые
            xpert_configs = ping_stats_service.get_healthy_configs(xpert_configs)
            
            # Затем берем только топ-N
            top_limit = app_config.XPERT_TOP_SERVERS_LIMIT
            xpert_configs = ping_stats_service.get_top_configs(xpert_configs, top_limit)
            
        except Exception as e:
            # Если статистика недоступна, используем оригинальные конфиги
            pass
        
        for config in xpert_configs:
            conf.add_link(config.raw)
            
    except Exception as e:
        # Если Xpert Panel не настроен, просто игнорируем
        pass
    
    return conf.render(reverse=reverse)


def generate_clash_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool, is_meta: bool = False
) -> str:
    if is_meta is True:
        conf = ClashMetaConfiguration()
    else:
        conf = ClashConfiguration()

    format_variables = setup_format_variables(extra_data)
    
    # Добавляем обычные конфиги Marzban
    marzban_config = process_inbounds_and_tags(
        inbounds, proxies, format_variables, conf=conf, reverse=reverse
    )
    
    # Добавляем конфиги из Xpert Panel (только для v2ray формата, clash требует специальной конвертации)
    # Пока пропускаем для clash, так как нужна конвертация в yaml формат
    
    return marzban_config


def generate_singbox_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool
) -> str:
    conf = SingBoxConfiguration()

    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(
        inbounds, proxies, format_variables, conf=conf, reverse=reverse
    )


def generate_outline_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool,
) -> str:
    conf = OutlineConfiguration()

    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(
        inbounds, proxies, format_variables, conf=conf, reverse=reverse
    )


def generate_v2ray_json_subscription(
        proxies: dict, inbounds: dict, extra_data: dict, reverse: bool,
) -> str:
    conf = V2rayJsonConfig()

    format_variables = setup_format_variables(extra_data)
    return process_inbounds_and_tags(
        inbounds, proxies, format_variables, conf=conf, reverse=reverse
    )


def generate_subscription(
        user: "UserResponse",
        config_format: Literal["v2ray", "clash-meta", "clash", "sing-box", "outline", "v2ray-json"],
        as_base64: bool,
        reverse: bool,
) -> str:
    kwargs = {
        "proxies": user.proxies,
        "inbounds": user.inbounds,
        "extra_data": user.__dict__,
        "reverse": reverse,
    }

    if config_format == "v2ray":
        config = "\n".join(generate_v2ray_links(**kwargs))
    elif config_format == "clash-meta":
        config = generate_clash_subscription(**kwargs, is_meta=True)
    elif config_format == "clash":
        config = generate_clash_subscription(**kwargs)
    elif config_format == "sing-box":
        config = generate_singbox_subscription(**kwargs)
    elif config_format == "outline":
        config = generate_outline_subscription(**kwargs)
    elif config_format == "v2ray-json":
        config = generate_v2ray_json_subscription(**kwargs)
    else:
        raise ValueError(f'Unsupported format "{config_format}"')

    if as_base64:
        config = base64.b64encode(config.encode()).decode()

    return config


def format_time_left(seconds_left: int) -> str:
    if not seconds_left or seconds_left <= 0:
        return "∞"

    minutes, seconds = divmod(seconds_left, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    months, days = divmod(days, 30)

    result = []
    if months:
        result.append(f"{months}m")
    if days:
        result.append(f"{days}d")
    if hours and (days < 7):
        result.append(f"{hours}h")
    if minutes and not (months or days):
        result.append(f"{minutes}m")
    if seconds and not (months or days):
        result.append(f"{seconds}s")
    return " ".join(result)


def setup_format_variables(extra_data: dict) -> dict:
    from app.models.user import UserStatus

    user_status = extra_data.get("status")
    expire_timestamp = extra_data.get("expire")
    on_hold_expire_duration = extra_data.get("on_hold_expire_duration")
    now = dt.utcnow()
    now_ts = now.timestamp()

    if user_status != UserStatus.on_hold:
        if expire_timestamp is not None and expire_timestamp >= 0:
            seconds_left = expire_timestamp - int(dt.utcnow().timestamp())
            expire_datetime = dt.fromtimestamp(expire_timestamp)
            expire_date = expire_datetime.date()
            jalali_expire_date = jd.fromgregorian(
                year=expire_date.year, month=expire_date.month, day=expire_date.day
            ).strftime("%Y-%m-%d")
            if now_ts < expire_timestamp:
                days_left = (expire_datetime - dt.utcnow()).days + 1
                time_left = format_time_left(seconds_left)
            else:
                days_left = "0"
                time_left = "0"

        else:
            days_left = "∞"
            time_left = "∞"
            expire_date = "∞"
            jalali_expire_date = "∞"
    else:
        if on_hold_expire_duration is not None and on_hold_expire_duration >= 0:
            days_left = timedelta(seconds=on_hold_expire_duration).days
            time_left = format_time_left(on_hold_expire_duration)
            expire_date = "-"
            jalali_expire_date = "-"
        else:
            days_left = "∞"
            time_left = "∞"
            expire_date = "∞"
            jalali_expire_date = "∞"

    if extra_data.get("data_limit"):
        data_limit = readable_size(extra_data["data_limit"])
        data_left = extra_data["data_limit"] - extra_data["used_traffic"]
        if data_left < 0:
            data_left = 0
        data_left = readable_size(data_left)
    else:
        data_limit = "∞"
        data_left = "∞"

    status_emoji = STATUS_EMOJIS.get(extra_data.get("status")) or ""
    status_text = STATUS_TEXTS.get(extra_data.get("status")) or ""

    format_variables = defaultdict(
        lambda: "<missing>",
        {
            "SERVER_IP": SERVER_IP,
            "SERVER_IPV6": SERVER_IPV6,
            "USERNAME": extra_data.get("username", "{USERNAME}"),
            "DATA_USAGE": readable_size(extra_data.get("used_traffic")),
            "DATA_LIMIT": data_limit,
            "DATA_LEFT": data_left,
            "DAYS_LEFT": days_left,
            "EXPIRE_DATE": expire_date,
            "JALALI_EXPIRE_DATE": jalali_expire_date,
            "TIME_LEFT": time_left,
            "STATUS_EMOJI": status_emoji,
            "STATUS_TEXT": status_text,
        },
    )

    return format_variables


def process_inbounds_and_tags(
        inbounds: dict,
        proxies: dict,
        format_variables: dict,
        conf: Union[
            V2rayShareLink,
            V2rayJsonConfig,
            SingBoxConfiguration,
            ClashConfiguration,
            ClashMetaConfiguration,
            OutlineConfiguration
        ],
        reverse=False,
) -> Union[List, str]:
    _inbounds = []
    for protocol, tags in inbounds.items():
        for tag in tags:
            _inbounds.append((protocol, [tag]))
    index_dict = {proxy: index for index, proxy in enumerate(
        xray.config.inbounds_by_tag.keys())}
    inbounds = sorted(
        _inbounds, key=lambda x: index_dict.get(x[1][0], float('inf')))

    for protocol, tags in inbounds:
        settings = proxies.get(protocol)
        if not settings:
            continue

        format_variables.update({"PROTOCOL": protocol.name})
        for tag in tags:
            inbound = xray.config.inbounds_by_tag.get(tag)
            if not inbound:
                continue

            format_variables.update({"TRANSPORT": inbound["network"]})
            host_inbound = inbound.copy()
            for host in xray.hosts.get(tag, []):
                sni = ""
                sni_list = host["sni"] or inbound["sni"]
                if sni_list:
                    salt = secrets.token_hex(8)
                    sni = random.choice(sni_list).replace("*", salt)

                if sids := inbound.get("sids"):
                    inbound["sid"] = random.choice(sids)

                req_host = ""
                req_host_list = host["host"] or inbound["host"]
                if req_host_list:
                    salt = secrets.token_hex(8)
                    req_host = random.choice(req_host_list).replace("*", salt)

                address = ""
                address_list = host['address']
                if host['address']:
                    salt = secrets.token_hex(8)
                    address = random.choice(address_list).replace('*', salt)

                if host["path"] is not None:
                    path = host["path"].format_map(format_variables)
                else:
                    path = inbound.get("path", "").format_map(format_variables)

                if host.get("use_sni_as_host", False) and sni:
                    req_host = sni

                host_inbound.update(
                    {
                        "port": host["port"] or inbound["port"],
                        "sni": sni,
                        "host": req_host,
                        "tls": inbound["tls"] if host["tls"] is None else host["tls"],
                        "alpn": host["alpn"] if host["alpn"] else None,
                        "path": path,
                        "fp": host["fingerprint"] or inbound.get("fp", ""),
                        "ais": host["allowinsecure"]
                        or inbound.get("allowinsecure", ""),
                        "mux_enable": host["mux_enable"],
                        "fragment_setting": host["fragment_setting"],
                        "noise_setting": host["noise_setting"],
                        "random_user_agent": host["random_user_agent"],
                    }
                )

                conf.add(
                    remark=host["remark"].format_map(format_variables),
                    address=address.format_map(format_variables),
                    inbound=host_inbound,
                    settings=settings.model_dump()
                )

    return conf.render(reverse=reverse)


def encode_title(text: str) -> str:
    return f"base64:{base64.b64encode(text.encode()).decode()}"
