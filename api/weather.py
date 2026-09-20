import os
import requests
from datetime import datetime, timedelta
from icalendar import Calendar, Event, vDate
from http.server import BaseHTTPRequestHandler

# 和风天气 API 配置
API_KEY = os.environ.get("QWEATHER_KEY", "")
LOCATION = os.environ.get("LOCATION_ID", "101210606")


def get_weather_data():
    url = f"https://devapi.qweather.com/v7/weather/7d?location={LOCATION}&key={API_KEY}"
    response = requests.get(url)
    res = response.json()
    
    # 如果 API 返回状态码不是 200，抛出明确错误
    code = res.get("code")
    if code != "200":
        raise Exception(f"和风天气 API 报错 [Code: {code}]: {res}")
        
    daily = res.get("daily", [])
    if not daily:
        raise Exception(f"和风天气返回的数据列表为空: {res}")
        
    return daily


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
            # 将具体错误直接输出在网页上方便排查
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"Weather Calendar Error: {str(e)}".encode('utf-8'))
