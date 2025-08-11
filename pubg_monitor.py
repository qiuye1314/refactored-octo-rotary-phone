import urllib.request
import time
import os
import json
import re
from datetime import datetime
from packaging import version
from flask import Flask, jsonify
from flask_cors import CORS  # 解决跨域问题（关键）
from io import StringIO
import sys

# ======================== 配置参数 ========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BETA_64_PAGE = "https://web.gpubgm.com/m/download_android_1.html"
BETA_32_PAGE = "https://web.gpubgm.com/m/download_android.html"
HISTORY_FILE = os.path.join(BASE_DIR, "link_history.json")
LOG_FILE = os.path.join(BASE_DIR, "update_monitor.log")

# Telegram 配置（请替换为你的实际信息）
TELEGRAM_ENABLED = True
TELEGRAM_BOT_TOKEN = "7733195908:AAEQlMhtHt1pr9CnvSYYpBzPx-cYieb2jqA"  # 你的Bot Token
TELEGRAM_CHAT_ID = "@BETA_PUBGgx"  # 你的频道ID

APK_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://www.pubgmobile.com/HK/home.shtml",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1"
}

# ======================== 工具函数 ========================
def log_message(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as log:
        log.write(f"[{timestamp}] {message}\n")
    print(f"[{timestamp}] {message}")  # 供前端捕获输出

def log_error(message):
    log_message(f"ERROR: {message}")

def get_website_content(url):
    try:
        req = urllib.request.Request(url, headers=APK_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read()
    except Exception as e:
        log_error(f"请求网站失败: {str(e)}")
        return None

def extract_download_links(content):
    if not content:
        return []
    try:
        html_content = content.decode('utf-8', errors='ignore')
        links = re.findall(r'https?://[^\s"<>]+\.apk', html_content)
        return list(set(links))
    except Exception as e:
        log_error(f"解析链接失败: {str(e)}")
        return []

def extract_version_from_link(link):
    try:
        match = re.search(r'(\d+\.\d+\.\d+)(?:[-_b\.](\d+))?', link)
        if match:
            base_version = match.group(1)
            build_number = match.group(2) or "0"
            return f"{base_version}.{build_number}"
        match_short = re.search(r'(\d+\.\d+)(?:[-_b\.](\d+))?', link)
        if match_short:
            base_short = match_short.group(1)
            build_short = match_short.group(2) or "0"
            return f"{base_short}.0.{build_short}"
        return None
    except Exception as e:
        log_error(f"提取版本号出错: {str(e)}")
        return None

def find_highest_version_link(links):
    if not links:
        return None, None
    highest_version = version.parse("0.0.0")
    highest_link = None
    for link in links:
        ver_str = extract_version_from_link(link)
        if ver_str:
            try:
                ver = version.parse(ver_str)
                log_message(f"解析链接: {link} → 版本号: {ver_str}")
                if ver > highest_version:
                    highest_version = ver
                    highest_link = link
            except Exception as e:
                log_error(f"版本号解析失败 ({link}): {str(e)}")
                continue
    return highest_link, highest_version

def get_current_links():
    results = {
        "beta": {
            "64bit": {"links": [], "highest_link": None, "highest_version": None},
            "32bit": {"links": [], "highest_link": None, "highest_version": None}
        }
    }
    # 64位页面
    content_64 = get_website_content(BETA_64_PAGE)
    if content_64:
        links_64 = extract_download_links(content_64)
        results["beta"]["64bit"]["links"] = links_64
        highest_link, highest_ver = find_highest_version_link(links_64)
        results["beta"]["64bit"]["highest_link"] = highest_link
        results["beta"]["64bit"]["highest_version"] = str(highest_ver) if highest_ver else None
        log_message(f"64位: 找到 {len(links_64)} 个链接, 最高版本: {highest_ver}")
    # 32位页面
    content_32 = get_website_content(BETA_32_PAGE)
    if content_32:
        links_32 = extract_download_links(content_32)
        results["beta"]["32bit"]["links"] = links_32
        highest_link, highest_ver = find_highest_version_link(links_32)
        results["beta"]["32bit"]["highest_link"] = highest_link
        results["beta"]["32bit"]["highest_version"] = str(highest_ver) if highest_ver else None
        log_message(f"32位: 找到 {len(links_32)} 个链接, 最高版本: {highest_ver}")
    return results

def save_links(links):
    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(links, f, indent=2)
    except Exception as e:
        log_error(f"保存链接失败: {str(e)}")

def load_links():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except:
            return None
    return None

def version_increased(current, last):
    if last is None:
        return True
    has_increased = False
    # 64位对比
    if current["beta"]["64bit"]["highest_version"] and last["beta"]["64bit"]["highest_version"]:
        cur_ver_64 = version.parse(current["beta"]["64bit"]["highest_version"])
        last_ver_64 = version.parse(last["beta"]["64bit"]["highest_version"])
        log_message(f"64位版本对比: 当前 {cur_ver_64} vs 历史 {last_ver_64}")
        if cur_ver_64 > last_ver_64:
            has_increased = True
    # 32位对比
    if current["beta"]["32bit"]["highest_version"] and last["beta"]["32bit"]["highest_version"]:
        cur_ver_32 = version.parse(current["beta"]["32bit"]["highest_version"])
        last_ver_32 = version.parse(last["beta"]["32bit"]["highest_version"])
        log_message(f"32位版本对比: 当前 {cur_ver_32} vs 历史 {last_ver_32}")
        if cur_ver_32 > last_ver_32:
            has_increased = True
    return has_increased

def send_telegram_notification(links, is_update=True):
    if not TELEGRAM_ENABLED:
        return
    message = "🚨 PUBG Mobile BETA 更新通知 🚨\n\n" if is_update else "🔧 PUBG Mobile BETA 链接测试 🔧\n\n"
    message += f"⏰ 检测时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    # 64位链接
    if links["beta"]["64bit"]["highest_link"]:
        ver = links["beta"]["64bit"]["highest_version"]
        message += f"🔹 64位最新版本: {ver}\n{links['beta']['64bit']['highest_link']}\n\n"
    # 32位链接
    if links["beta"]["32bit"]["highest_link"]:
        ver = links["beta"]["32bit"]["highest_version"]
        message += f"🔸 32位最新版本: {ver}\n{links['beta']['32bit']['highest_link']}\n\n"
    # 无链接提示
    if not links["beta"]["64bit"]["highest_link"] and not links["beta"]["32bit"]["highest_link"]:
        message += "⚠️ 未检测到下载链接\n\n"
    # 结尾提示
    message += "📢 提示：复制链接到浏览器下载\n#PUBG #BETA #测试版" if is_update else "这是链接提取测试结果"
    # 发送请求
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": False
    }
    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            response_data = json.loads(response.read().decode('utf-8'))
            if response_data.get('ok'):
                log_message("Telegram 通知已发送")
            else:
                log_error(f"Telegram 发送失败: {response_data.get('description')}")
    except Exception as e:
        log_error(f"发送通知失败: {str(e)}")

# ======================== 核心功能 ========================
def test_link_extraction():
    print("=" * 60)
    print("PUBG Mobile BETA 链接提取测试")
    print("=" * 60)
    current_links = get_current_links()
    print("\n发送测试通知到Telegram...")
    send_telegram_notification(current_links, is_update=False)
    print("\n测试完成")

def check_version():
    log_message("开始单次检查 PUBG Mobile BETA 版本...")
    last_links = load_links()
    current_links = get_current_links()
    if version_increased(current_links, last_links):
        log_message("检测到新版本!")
        send_telegram_notification(current_links)
        save_links(current_links)
        log_message("新链接状态已保存")
    else:
        if last_links:
            log_message(f"版本未更新 (64位: {current_links['beta']['64bit']['highest_version']} vs {last_links['beta']['64bit']['highest_version']}, 32位: {current_links['beta']['32bit']['highest_version']} vs {last_links['beta']['32bit']['highest_version']})")
        else:
            log_message("首次运行，未检测到更新")

# ======================== Flask 配置 ========================
def capture_output(func):
    def wrapper(*args, **kwargs):
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()
        try:
            func(*args, **kwargs)
        finally:
            sys.stdout = old_stdout
        return captured_output.getvalue()
    return wrapper

app = Flask(__name__)
CORS(app)  # 允许所有域名跨域访问（生产环境可限制域名）

@app.route('/test', methods=['POST'])
def run_test():
    output = capture_output(test_link_extraction)()
    return jsonify({"output": output})

@app.route('/check', methods=['POST'])
def run_check():
    output = capture_output(check_version)()
    return jsonify({"output": output})

# ======================== 初始化 ========================
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w") as f:
        pass
if not os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "w") as f:
        pass

# ======================== 启动服务 ========================
if __name__ == "__main__":
    # 适配云平台端口（Render等平台会自动设置PORT环境变量）
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
