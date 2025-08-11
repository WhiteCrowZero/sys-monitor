import os
from hashlib import sha256

from jinja2 import Template
import time
from monitor.config import EMAIL_CONFIG, USE_THRESHOLD, CHART_OUTPUT_PATH, TEMPLATE_HTML_PATH, SECRET_KEY
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig
from typing import List, Dict, Optional
from monitor.utils.make_chart import generate_all_chart
from monitor.utils.os_info import get_os_info
import logging

# 配置日志
logger = logging.getLogger("monitor.mail")

# 配置邮件连接
conf = ConnectionConfig(
    MAIL_USERNAME=EMAIL_CONFIG.get("username"),
    MAIL_PASSWORD=EMAIL_CONFIG.get("password"),
    MAIL_FROM=EMAIL_CONFIG.get("from"),
    MAIL_PORT=EMAIL_CONFIG.get("port"),
    MAIL_SERVER=EMAIL_CONFIG.get("host"),
    # 关闭 STARTTLS，启用 SSL/TLS
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

# 初始化 FastMail 实例
fm = FastMail(conf)


async def send_report_email(
        subject: str,
        recipients: List[str],
        body_html: str,
        attachments: Optional[List[str]] = None,
        inline_images: Optional[Dict[str, str]] = None
) -> bool:
    attach_objs = []

    # 处理普通附件
    if attachments:
        for file_path in attachments:
            attach_objs.append({"file": file_path})

    # 处理内联图片
    if inline_images:
        for cid, img_path in inline_images.items():
            attach_objs.append({
                "file": img_path,
                "filename": os.path.basename(img_path),
                "content_id": cid,
                "disposition": "inline"
            })

    try:
        message = MessageSchema(
            subject=subject,
            recipients=recipients,
            body=body_html,
            subtype="html",
            attachments=attach_objs,
        )

        await fm.send_message(message)
        logger.info(f"邮件发送成功: {subject} -> {recipients}")
        return True
    except Exception as e:
        logger.error(f"邮件发送失败: {e}\n主题: {subject}\n收件人: {recipients}")
        return False


async def send_alert_email(
        recipients: List[str],
):
    data = get_os_info()
    context = {
        "cpu_usage": data["cpu"]["cpu_percent_overall"],
        "cpu_threshold": USE_THRESHOLD.get("cpu", "N/A"),
        "mem_usage": data["cpu"]["memory_percent"],
        "mem_threshold": USE_THRESHOLD.get("memory", "N/A"),
        "disk_alerts": [
            {
                "partition": part,
                "percent": info["percent"],
                "threshold": USE_THRESHOLD.get("disk", "N/A")
            }
            for part, info in data["disk"].items()
            if isinstance(info, dict) and info.get("percent", 0) >= USE_THRESHOLD.get("disk", "N/A")
        ],
        "report_time": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    subject = "系统警告报告 - " + context["report_time"]
    with open(os.path.join(TEMPLATE_HTML_PATH, "alert.html"), "r", encoding="utf-8") as f:
        tpl = Template(f.read())
    body_html = tpl.render(**context)
    await send_report_email(subject, recipients, body_html)


async def send_info_email(
        recipients: List[str],
):
    subject = "系统信息报告 - " + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    data = get_os_info()
    data["cpu"]["cpu_percent_per_core"] = data["cpu"]["cpu_percent_per_core"][:9]
    charts = generate_all_chart(data, CHART_OUTPUT_PATH)
    with open(os.path.join(TEMPLATE_HTML_PATH, "info.html"), "r", encoding="utf-8") as f:
        tpl = Template(f.read())
    body_html = tpl.render(**data)
    await send_report_email(subject, recipients, body_html, inline_images=charts)


def verify_signature(recipients: List[str], timestamp: int, signature: str) -> bool:
    """
    签名校验：signature = sha256(secret + recipients_str + timestamp)
    """
    recipients_str = ",".join(sorted(recipients))
    base = f"{SECRET_KEY}{recipients_str}{timestamp}"
    expected_signature = sha256(base.encode("utf-8")).hexdigest()
    # 时间戳不能过旧（防止重放攻击）
    if abs(time.time() - timestamp) > 300:
        return False
    return expected_signature == signature


def generate_email_request(
        recipients: List[str],
        secret_key: str
) -> Dict[str, object]:
    """
    返回一个 dict，包含 recipients、timestamp、signature，
    正好可以当作 POST /report/email 的 JSON 请求体。
    """
    # 1. 排序、拼接收件人
    recipients_str = ",".join(sorted(recipients))
    # 2. 当前时间戳（秒）
    timestamp = int(time.time())
    # 3. 计算签名
    raw = f"{secret_key}{recipients_str}{timestamp}"
    signature = sha256(raw.encode("utf-8")).hexdigest()
    # 4. 返回请求体
    return {
        "recipients": recipients,
        "timestamp": timestamp,
        "signature": signature
    }


if __name__ == '__main__':
    import requests

    payload = generate_email_request(["13820826029@163.com"], SECRET_KEY)
    resp = requests.post("http://127.0.0.1:8001/api/report/email", json=payload)
    print(resp)
    print(resp.text)
