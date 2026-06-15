"""Показать, видит ли Windows прокси от Happ. Запуск: python show_proxy.py"""
import urllib.request

proxies = urllib.request.getproxies()
print("Windows видит такие прокси:")
if not proxies:
    print("  (пусто — Happ «Системный прокси» не применился)")
else:
    for key, value in proxies.items():
        print(f"  {key}: {value}")
