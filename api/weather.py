import os
import json
import urllib.request
from datetime import datetime, timedelta
from icalendar import Calendar, Event, vDate
from http.server import BaseHTTPRequestHandler

# 从 Vercel 环境变量获取配置（避免将私密 Key 写入代码中）
API_KEY = os.environ.get("QWEATHER_KEY", "")
LOCATION = os.environ.get("LOCATION_ID", "101210606")  # 默认杭州，可自定


def get_weather_data():
    if not API_KEY:
        raise Exception("未检测到环境变量 QWEATHER_KEY，请先在 Vercel 中配置你的 API Key。")

    # 兼容免费开发版域名与商业版/全功能凭据域名
    hosts = [
        "https://devapi.qweather.com",
        "https://api.qweather.com"
    ]
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    last_error = ""

    for host in hosts:
        url = f"{host}/v7/weather/7d?location={LOCATION}&key={API_KEY}"
        req = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode('utf-8')
                res = json.loads(data)

                # 如果遇到域名不匹配报错，自动尝试下一个域名
                if "error" in res and res.get("error", {}).get("title") == "Invalid Host":
                    last_error = f"域名 {host} 不适用该凭据"
                    continue

                code = res.get("code")
                if code == "200":
                    daily = res.get("daily", [])
                    if daily:
                        return daily
                    raise Exception("和风天气 API 返回的数据列表为空")
                else:
                    raise Exception(f"和风天气 API 返回错误码 [{code}]: {data}")

        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8')
            last_error = f"HTTP {e.code}: {err_body}"
        except Exception as e:
            last_error = str(e)

    raise Exception(f"无法获取天气数据，请检查 Key 或权限。详细报错: {last_error}")


def generate_ics(daily_data):
    cal = Calendar()
    cal.add('prodid', '-//My Vercel Weather Calendar//CN')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', '每日天气')
    cal.add('x-wr-timezone', 'Asia/Shanghai')

    for day in daily_data:
        date_str = day['fxDate']  # 格式如：2026-09-20
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()

        text_day = day.get('textDay', '')
        text_night = day.get('textNight', '')
        temp_max = day.get('tempMax', '')
        temp_min = day.get('tempMin', '')
        precip = day.get('precip', '')
        wind_dir = day.get('windDirDay', '')
        wind_scale = day.get('windScaleDay', '')
        humidity = day.get('humidity', '')

        summary = f"⛅ {text_day} {temp_min}°C ~ {temp_max}°C"
        description = (
            f"白天天气: {text_day}\n"
            f"夜间天气: {text_night}\n"
            f"最高温度: {temp_max}°C / 最低温: {temp_min}°C\n"
            f"降水量: {precip} mm\n"
            f"风向风力: {wind_dir} {wind_scale}级\n"
            f"相对湿度: {humidity}%"
        )

        event = Event()
        event.add('summary', summary)
        event.add('description', description)
        
        # 针对全天日程，使用 vDate 包装
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
