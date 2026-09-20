import os
import requests
from datetime import datetime, timedelta
from icalendar import Calendar, Event, vDate
from http.server import BaseHTTPRequestHandler

# 和风天气 API 配置
API_KEY = os.environ.get("QWEATHER_KEY", "")
LOCATION = os.environ.get("LOCATION_ID", "101210606")


def get_weather_data():
    # 备选 API 域名列表：开发版域名 与 商业/通用版域名
    hosts = [
        "https://devapi.qweather.com",
        "https://api.qweather.com"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Encoding": "gzip"
    }

    last_exception = None

    for host in hosts:
        url = f"{host}/v7/weather/7d?location={LOCATION}&key={API_KEY}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            res = response.json()

            # 如果遇到 Host 错误，跳过并尝试下一个域名
            if "error" in res and res.get("error", {}).get("title") == "Invalid Host":
                continue

            code = res.get("code")
            if code == "200":
                daily = res.get("daily", [])
                if daily:
                    return daily
                raise Exception(f"和风天气返回的天气列表为空: {res}")
            else:
                raise Exception(f"和风天气 API 报错 [Code: {code}]: {res}")

        except Exception as e:
            last_exception = e

    raise Exception(f"请求和风天气失败，已尝试所有域名。详细错误: {last_exception}")


def generate_ics(daily_data):
    cal = Calendar()
    cal.add('prodid', '-//My Vercel Weather Calendar//CN')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', '每日天气')
    cal.add('x-wr-timezone', 'Asia/Shanghai')

    for day in daily_data:
        date_str = day['fxDate']  # 格式如 2026-09-20
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        text_day = day.get('textDay', '')
        temp_max = day.get('tempMax', '')
        temp_min = day.get('tempMin', '')
        precip = day.get('precip', '')
        wind_dir = day.get('windDirDay', '')

        summary = f"⛅ {text_day} {temp_min}°C ~ {temp_max}°C"
        description = (
            f"白天天气: {text_day}\n"
            f"夜间天气: {day.get('textNight', '')}\n"
            f"最高温度: {temp_max}°C / 最低温: {temp_min}°C\n"
            f"降水量: {precip} mm\n"
            f"风向风力: {wind_dir} {day.get('windScaleDay', '')}级\n"
            f"相对湿度: {day.get('humidity', '')}%"
        )

        event = Event()
        event.add('summary', summary)
        event.add('description', description)
        
        event.add('dtstart', vDate(event_date))
        event.add('dtend', vDate(event_date + timedelta(days=1)))
        event.add('transp', 'TRANSPARENT')

        cal.add_component(event)

    return cal.to_ical()


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            daily_data = get_weather_data()
            ics_content = generate_ics(daily_data)

            self.send_response(200)
            self.send_header('Content-Type', 'text/calendar; charset=utf-8')
            self.send_header('Cache-Control', 's-maxage=3600, stale-while-revalidate')
            self.end_headers()
            self.wfile.write(ics_content)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Weather Calendar Error: {str(e)}".encode('utf-8'))
