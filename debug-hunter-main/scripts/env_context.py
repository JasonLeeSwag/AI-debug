"""
SWAG QA 環境脈絡收集器
每次執行測試前自動收集當下環境資訊，附加到測試報告
"""

import platform
import socket
import json
import sys
from datetime import datetime, timezone, timedelta
from typing import Optional

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ─────────────────────────────────────────
# OS & Device
# ─────────────────────────────────────────

def get_os_info() -> dict:
    system = platform.system()
    machine = platform.machine()

    # 判斷是否行動裝置（Appium 執行時 platform 會是 Android/iOS）
    is_mobile = system.lower() in ("android", "ios") or "arm" in machine.lower()

    os_map = {
        "Darwin": f"macOS {platform.mac_ver()[0] or platform.version()}",
        "Windows": f"Windows {platform.version()}",
        "Linux": f"Linux {platform.release()}",
        "Android": f"Android {platform.version()}",
        "iOS": f"iOS {platform.version()}",
    }

    return {
        "system": os_map.get(system, system),
        "arch": machine,
        "device_type": "mobile" if is_mobile else "desktop",
        "python": sys.version.split()[0],
    }


# ─────────────────────────────────────────
# Network
# ─────────────────────────────────────────

def get_network_info() -> dict:
    """
    偵測網路類型：ethernet / wifi / cellular / unknown
    同時偵測 VPN 介面（tun/tap/utun/ppp/wg）
    """
    result = {
        "type": "unknown",
        "interface": None,
        "vpn_active": False,
        "vpn_interface": None,
    }

    if not HAS_PSUTIL:
        return {**result, "note": "psutil 未安裝，跳過網路偵測"}

    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    # VPN 介面前綴（WireGuard: wg, OpenVPN: tun/tap, macOS: utun, PPP: ppp）
    VPN_PREFIXES = ("tun", "tap", "utun", "ppp", "wg", "vpn", "nordlynx", "mullvad")
    # 有線網路前綴
    ETHERNET_PREFIXES = ("eth", "en0", "enpXs", "eno", "enp")
    # 無線網路前綴
    WIFI_PREFIXES = ("wlan", "wi-fi", "wlp", "en1", "en2")

    for iface, stat in stats.items():
        if not stat.isup:
            continue
        iface_lower = iface.lower()

        # 先偵測 VPN（優先）
        if any(iface_lower.startswith(p) for p in VPN_PREFIXES):
            result["vpn_active"] = True
            result["vpn_interface"] = iface

        # 再偵測主要網路類型（跳過 loopback）
        if iface_lower in ("lo", "lo0", "localhost"):
            continue
        if result["type"] == "unknown":
            if any(iface_lower.startswith(p) for p in ETHERNET_PREFIXES):
                result["type"] = "ethernet"
                result["interface"] = iface
            elif any(iface_lower.startswith(p) for p in WIFI_PREFIXES):
                result["type"] = "wifi"
                result["interface"] = iface

    return result


# ─────────────────────────────────────────
# IP & 地理位置
# ─────────────────────────────────────────

def get_location_info(timeout: int = 4) -> dict:
    """
    透過 ipinfo.io 取得 IP 地理位置與 ISP 資訊
    若 VPN 啟用，org 欄位通常會顯示 VPN 服務商名稱
    """
    if not HAS_REQUESTS:
        return {"note": "requests 未安裝，跳過地理位置偵測"}

    try:
        resp = requests.get("https://ipinfo.io/json", timeout=timeout)
        resp.raise_for_status()
        data = resp.json()

        # org 欄位格式：'AS9924 Taiwan Fixed Network Co.' 或 'AS13335 Cloudflare, Inc.'
        org = data.get("org", "")
        is_vpn_ip = any(
            keyword in org.lower()
            for keyword in ("vpn", "nordvpn", "expressvpn", "mullvad", "cloudflare",
                            "digitalocean", "linode", "vultr", "amazon", "google cloud")
        )

        return {
            "ip": data.get("ip"),
            "city": data.get("city"),
            "region": data.get("region"),
            "country": data.get("country"),
            "isp": org,
            "timezone": data.get("timezone"),
            "coordinates": data.get("loc"),   # "25.0478,121.5318"
            "ip_looks_like_vpn": is_vpn_ip,
        }
    except Exception as e:
        return {"error": str(e), "note": "無法取得地理位置（可能是離線環境）"}


# ─────────────────────────────────────────
# 彙整
# ─────────────────────────────────────────

def collect(include_location: bool = True) -> dict:
    """
    收集完整環境脈絡，回傳 dict
    include_location=False 可跳過 HTTP 請求（離線環境）
    """
    tz_taipei = timezone(timedelta(hours=8))
    network = get_network_info()
    location = get_location_info() if include_location else {"note": "已略過"}

    # VPN 判斷：介面偵測 OR IP 看起來是 VPN
    vpn_likely = network.get("vpn_active") or location.get("ip_looks_like_vpn", False)

    ctx = {
        "collected_at": datetime.now(tz_taipei).isoformat(),
        "os": get_os_info(),
        "network": {
            "type": network.get("type"),             # ethernet / wifi / cellular / unknown
            "interface": network.get("interface"),
            "vpn_active": vpn_likely,
            "vpn_interface": network.get("vpn_interface"),
        },
        "location": location,
    }
    return ctx


def collect_as_json(indent: int = 2, **kwargs) -> str:
    return json.dumps(collect(**kwargs), ensure_ascii=False, indent=indent)


def print_summary(ctx: Optional[dict] = None) -> None:
    """印出給人看的摘要（適合貼到 Bug report）"""
    if ctx is None:
        ctx = collect()

    os_info = ctx["os"]
    net = ctx["network"]
    loc = ctx["location"]

    print("=" * 52)
    print("  SWAG QA 環境脈絡（Environment Context）")
    print("=" * 52)
    print(f"  時間     : {ctx['collected_at']}")
    print(f"  OS       : {os_info['system']} ({os_info['arch']})")
    print(f"  裝置類型 : {os_info['device_type']}")
    print(f"  網路類型 : {net['type']}  介面: {net['interface'] or 'n/a'}")
    print(f"  VPN      : {'⚠️  已啟用' if net['vpn_active'] else '未啟用'}  "
          f"({net['vpn_interface'] or 'n/a'})")
    if loc and "ip" in loc:
        print(f"  IP       : {loc.get('ip')}  ({loc.get('city')}, {loc.get('country')})")
        print(f"  ISP      : {loc.get('isp')}")
    print("=" * 52)


# ─────────────────────────────────────────
# Playwright 輔助（inject 到 browser 內執行）
# ─────────────────────────────────────────

PLAYWRIGHT_ENV_SCRIPT = """
() => {
  const conn = navigator.connection || navigator.mozConnection || navigator.webkitConnection;
  const ua   = navigator.userAgent;
  return {
    userAgent     : ua,
    os            : (() => {
      if (/iPhone|iPad|iPod/.test(ua)) return 'iOS';
      if (/Android/.test(ua))          return 'Android';
      if (/Mac OS X/.test(ua))         return 'macOS';
      if (/Windows/.test(ua))          return 'Windows';
      if (/Linux/.test(ua))            return 'Linux';
      return 'unknown';
    })(),
    deviceType    : /Mobi|Android|iPhone|iPad/i.test(ua) ? 'mobile' : 'desktop',
    screen        : {
      width            : screen.width,
      height           : screen.height,
      devicePixelRatio : window.devicePixelRatio,
      isTouchDevice    : navigator.maxTouchPoints > 0,
    },
    network       : {
      type          : conn ? conn.type          : 'unknown',
      effectiveType : conn ? conn.effectiveType : 'unknown',
      downlinkMbps  : conn ? conn.downlink      : null,
      rttMs         : conn ? conn.rtt           : null,
      saveData      : conn ? conn.saveData      : null,
    },
    language      : navigator.language,
    timezone      : Intl.DateTimeFormat().resolvedOptions().timeZone,
    cookieEnabled : navigator.cookieEnabled,
  };
}
"""


def get_browser_env(page) -> dict:
    """
    在 Playwright page 中收集瀏覽器端環境資訊
    用法：
        env = get_browser_env(page)
        print(env['network']['effectiveType'])  # '4g' / '3g' / '2g'
    """
    return page.evaluate(PLAYWRIGHT_ENV_SCRIPT)


# ─────────────────────────────────────────
# Robot Framework keyword（可被 .robot 檔 import）
# ─────────────────────────────────────────

class EnvContextLibrary:
    """Robot Framework Library：自動收集並記錄環境脈絡"""

    ROBOT_LIBRARY_SCOPE = "SUITE"

    def collect_environment_context(self) -> dict:
        """收集環境資訊並回傳 dict，同時輸出 RF log"""
        from robot.api import logger
        ctx = collect()
        logger.info(f"[ENV] OS: {ctx['os']['system']} / {ctx['os']['device_type']}")
        logger.info(f"[ENV] 網路: {ctx['network']['type']} / VPN: {ctx['network']['vpn_active']}")
        loc = ctx.get("location", {})
        if "ip" in loc:
            logger.info(f"[ENV] IP: {loc['ip']} ({loc.get('city')}, {loc.get('country')})")
        return ctx

    def assert_no_vpn(self):
        """斷言：當前不應啟用 VPN（某些支付測試需要台灣 IP）"""
        ctx = collect()
        if ctx["network"]["vpn_active"]:
            iface = ctx["network"]["vpn_interface"]
            raise AssertionError(
                f"偵測到 VPN 介面 [{iface}]。"
                "部分支付回調測試需要真實台灣 IP，請關閉 VPN 後重試。"
            )

    def get_network_type(self) -> str:
        """回傳網路類型：ethernet / wifi / cellular / unknown"""
        return get_network_info().get("type", "unknown")


# ─────────────────────────────────────────
# CLI
# ─────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SWAG QA 環境脈絡收集器")
    parser.add_argument("--json", action="store_true", help="輸出 JSON 格式")
    parser.add_argument("--no-location", action="store_true", help="跳過 IP 地理位置查詢")
    args = parser.parse_args()

    ctx = collect(include_location=not args.no_location)

    if args.json:
        print(collect_as_json())
    else:
        print_summary(ctx)
