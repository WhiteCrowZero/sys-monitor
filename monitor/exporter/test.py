import os

os.environ['TZ'] = 'Asia/Shanghai'  # 设置时区环境变量

import time

if hasattr(time, 'tzset'):
    time.tzset()  # Unix系统重置时区

import os, sys
import time
import json
import logging  # 添加日志模块
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import FastAPI, Query, HTTPException, APIRouter
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("monitor")

# 确保能 import 上级 monitor 包
current_dir = os.path.dirname(os.path.abspath(__file__))
monitor_dir = os.path.dirname(current_dir)
sys.path.insert(0, monitor_dir)

from monitor.collector.cpu import CPUCollector
from monitor.collector.disk import DiskCollector
from monitor.collector.network import NetworkCollector
from monitor.collector import system_command, log_reader
from monitor.collector.senior import SeniorCollector
from monitor.utils.send_mail import send_alert_email, send_info_email, verify_signature, get_default_config
from monitor.utils.os_info import get_os_info

import os
from pydantic import BaseModel, EmailStr
from fastapi.middleware.cors import CORSMiddleware

# 配置文件路径 - 确保与实际路径一致
CONFIG_PATH = "/root/shared-nvme/TZB2025/sys_monitor/monitor/config.json"
# CONFIG_PATH = r"D:\ComputerScience\Python\temp\system-monitor\monitor\config.json"

# 创建应用和路由器
app = FastAPI()
router = APIRouter()

# 添加CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# —— 初始化监控收集器 —— #
cpu = CPUCollector()
disk = DiskCollector()
net = NetworkCollector()
senior = SeniorCollector()

# —— CORS 设置 —— #
origins = ["*"]

# ================= 邮件警告 =================
# 全局变量，记录上次发送的时间戳
_last_alert_time: float = 0.0


# —— 定时任务函数 —— #
async def check_and_alert(thresholds, recipients):
    global _last_alert_time
    now = time.time()
    # 如果上一次发送时间距今不到 30 分钟，跳过
    if now - _last_alert_time < 30 * 60:
        return

    data = get_os_info()
    cpu_data = data['cpu']["cpu_percent_overall"]
    cpu_flag = cpu_data > thresholds["cpu"]

    memory_data = data['cpu']["memory_percent"]
    memory_flag = memory_data > thresholds["memory"]

    disk_data = data['disk']
    disk_flag = False
    for item in disk_data.values():
        if item.get("percent", 0) > thresholds["disk"]:
            disk_flag = True
            break

    if cpu_flag or memory_flag or disk_flag:
        # 更新上次发送时间
        _last_alert_time = now
        # 发送警告邮件
        await send_alert_email(
            recipients=recipients,
        )
        logger.info(f"发送邮件警告: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")


async def daily_info_report(recipients, content_filter):
    # 获取全量监控
    await send_info_email(
        recipients=recipients,
    )
    logger.info(f"发送日报: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}")


# —— Lifespan：启动/关闭调度器 —— #
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 修改后的调度器创建方式
    scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')

    # 确保配置文件存在
    ensure_config_exists()

    # 加载配置
    config = get_default_config()

    # 使用 alert_recipients 替换 recipients
    scheduler.add_job(
        check_and_alert,
        trigger=IntervalTrigger(seconds=60),
        kwargs={"thresholds": config["thresholds"],
                "recipients": config["alert_recipients"]}
    )

    # 动态设置报告时间
    hour, minute = map(int, config["report_time"].split(":"))
    scheduler.add_job(
        daily_info_report,
        trigger=CronTrigger(hour=hour, minute=minute),
        kwargs={"recipients": config["report_recipients"],
                "content_filter": config["report_content"]}
    )
    scheduler.start()
    yield
    scheduler.shutdown()


# =============== 对外邮件接口 ===============
class EmailRequest(BaseModel):
    recipients: List[EmailStr]
    timestamp: int
    signature: str


@router.post("/report/email")
async def send_email(req: EmailRequest):
    """发送定时报告邮件，含验签"""
    if not verify_signature(req.recipients, req.timestamp, req.signature):
        raise HTTPException(status_code=403, detail="签名验证失败")

    await send_info_email(recipients=req.recipients)
    return {"message": "邮件发送成功"}


# =============== 配置管理接口 ===============
# 配置更新模型
class ConfigUpdate(BaseModel):
    alert_recipients: List[EmailStr]
    report_recipients: List[EmailStr]
    thresholds: Dict[str, float]
    report_time: str
    report_content: Dict[str, bool]


def ensure_config_exists():
    """确保配置文件存在"""
    if not os.path.exists(CONFIG_PATH):
        logger.warning(f"配置文件不存在，创建默认配置: {CONFIG_PATH}")
        with open(CONFIG_PATH, 'w') as f:
            default_config = get_default_config()
            json.dump(default_config, f, indent=4)
        # 设置文件权限
        os.chmod(CONFIG_PATH, 0o644)


@router.post("/api/config/load")
async def get_config():
    """获取当前系统配置（前端兼容格式）"""
    try:
        logger.info(f"加载配置文件: {CONFIG_PATH}")
        ensure_config_exists()

        with open(CONFIG_PATH, 'r') as f:
            raw_config = json.load(f)

        # 转换字段名匹配前端结构 - 修复邮箱地址字段名问题
        config_data = {
            # 关键修复：使用正确的字段名映射
            "alert_recipients": raw_config.get("RECIPIENTS", []),
            "report_recipients": raw_config.get("REPORT_RECIPIENTS", []),
            "thresholds": raw_config.get("USE_THRESHOLD", {"cpu": 80, "memory": 85, "disk": 90}),
            "report_time": raw_config.get("EMAIL_REPORT_TIME", "08:00"),
            "report_content": raw_config.get("REPORT_CONTENT", {
                "cpu": True,
                "memory": True,
                "disk": True,
                "network": False,
                "processes": False
            })
        }

        # 记录调试信息
        logger.debug(f"配置加载成功")
        logger.debug(
            f"邮箱地址信息: \nalert_recipients={config_data['alert_recipients']},\n report_recipients={config_data['report_recipients']}")

        return config_data

    except Exception as e:
        logger.error(f"配置加载失败: {str(e)}")
        # 返回默认配置防止前端出错
        return get_default_config()


@router.post("/api/config")
async def update_config(config: ConfigUpdate):
    """更新系统配置"""
    try:
        ensure_config_exists()

        logger.info("更新系统配置")
        logger.debug(
            f"更新配置数据: alert_recipients={config.alert_recipients}, report_recipients={config.report_recipients}")

        # 读取现有配置
        try:
            with open(CONFIG_PATH, 'r') as f:
                raw_config = json.load(f)
        except Exception as e:
            logger.error(f"读取现有配置失败: {str(e)}")
            raw_config = {}

        # 更新字段映射 - 修复邮箱地址字段名问题
        raw_config.update({
            # 关键修复：使用正确的字段名映射
            "RECIPIENTS": config.alert_recipients,
            "REPORT_RECIPIENTS": config.report_recipients,
            "USE_THRESHOLD": config.thresholds,
            "EMAIL_REPORT_TIME": config.report_time,
            "REPORT_CONTENT": config.report_content
        })

        # 保存配置
        with open(CONFIG_PATH, 'w') as f:
            json.dump(raw_config, f, indent=4)

        logger.info("配置更新成功")
        logger.debug(f"更新后配置内容: {json.dumps(raw_config, indent=2)}")

        return {"message": "配置更新成功"}

    except Exception as e:
        logger.error(f"配置更新失败: {str(e)}")
        raise HTTPException(500, detail=f"配置更新失败: {str(e)}")


@router.post("/api/report/test")
async def send_email():
    with open(CONFIG_PATH, 'r') as f:
        raw_config = json.load(f)
    await send_info_email(recipients=raw_config.get("REPORT_RECIPIENTS", []))
    return {"message": "邮件发送成功"}


# 将路由器挂载到应用
app.include_router(router)


# =============== 基础监控接口 ===============

@app.post("/metrics")
async def metrics():
    """综合 CPU、磁盘、网络监控数据"""
    return get_os_info()


# =============== CPU 监控接口 ===============

@app.post("/metrics/cpu/top")
async def cpu_top(n: int = Query(5, ge=1, le=100)) -> List[Dict[str, Any]]:
    """返回占用 CPU 最高的 n 个进程"""
    return cpu.top(n)


@app.post("/metrics/cpu/recent")
async def cpu_recent(n: int = Query(5, ge=1, le=100)) -> List[Dict[str, Any]]:
    """返回最近创建的 n 个进程"""
    return cpu.recent(n)


# =============== 磁盘监控接口 ===============

@app.post("/metrics/disk/top")
async def disk_top(
        n: int = Query(5, ge=1, le=100),
        path: str = Query('/', min_length=1)
) -> List[Dict[str, Any]]:
    """返回指定路径下最大的 n 个文件"""
    return disk.top(n, path)


@app.post("/metrics/disk/recent")
async def disk_recent(
        n: int = Query(5, ge=1, le=100),
        path: str = Query('/', min_length=1)
) -> List[Dict[str, Any]]:
    """返回指定路径下最近创建的 n 个文件"""
    return disk.recent(n, path)


# =============== 网络监控接口 ===============

@app.post("/metrics/network/top")
async def network_top(n: int = Query(5, ge=1, le=100)) -> List[Dict[str, Any]]:
    """返回网络 I/O 最多的 n 个进程"""
    return net.top(n)


@app.post("/metrics/network/recent")
async def network_recent(n: int = Query(5, ge=1, le=100)) -> List[Dict[str, Any]]:
    """返回最近建立的 n 条 TCP 连接"""
    return net.recent(n)


# =============== 系统命令执行接口 ===============

@app.post("/metrics/command/top")
async def get_top():
    """获取 top 命令输出"""
    return {"output": system_command.collect_top()}


@app.post("/metrics/command/vmstat")
async def get_vmstat():
    """获取 vmstat 命令输出"""
    return {"output": system_command.collect_vmstat()}


@app.post("/metrics/command/pidstat")
async def get_pidstat():
    """获取 pidstat 命令输出"""
    return {"output": system_command.collect_pidstat()}


@app.post("/metrics/command/free")
async def get_free():
    """获取 free 命令输出"""
    return {"output": system_command.collect_free()}


@app.post("/metrics/command/df")
async def get_df():
    """获取 df 命令输出"""
    return {"output": system_command.collect_df()}


@app.post("/metrics/command/iostat")
async def get_iostat():
    """获取 iostat 命令输出"""
    return {"output": system_command.collect_iostat()}


@app.post("/metrics/command/ethtool")
async def get_ethtool(interface: str = Query("eth0")):
    """获取指定网卡的 ethtool 信息"""
    return {"output": system_command.collect_ethtool(interface)}


# =============== 日志读取接口 ===============

@app.post("/metrics/logs/system")
async def get_system_log(lines: int = Query(100, ge=1, le=1000)):
    """获取最近 lines 条系统日志（journalctl）"""
    return {"output": log_reader.collect_system_log(lines)}


@app.post("/metrics/logs/kernel")
async def get_kernel_log(lines: int = Query(100, ge=1, le=1000)):
    """获取最近 lines 条内核日志（dmesg）"""
    return {"output": log_reader.collect_kernel_log(lines)}


@app.post("/metrics/logs/app")
async def get_app_log(
        path: str = Query(..., min_length=1),
        lines: int = Query(100, ge=1, le=1000)
):
    """获取指定应用日志最后 lines 行"""
    return {"output": log_reader.collect_app_log(path, lines)}


# =============== 高级监控接口 ===============

@app.post("/metrics/senior/package")
async def package_status(pkg: str = Query(..., min_length=1)) -> Dict[str, Any]:
    """查询软件包安装状态及版本信息"""
    return senior.get_package_status(pkg)


@app.post("/metrics/senior/stack/native")
async def native_stack(pid: int = Query(..., ge=1)) -> Dict[str, Any]:
    """获取指定进程的原生（用户态）调用栈"""
    output = senior.get_native_stack(pid)
    if "Error" in output:
        raise HTTPException(status_code=400, detail=output)
    return {"pid": pid, "stack": output}


@app.post("/metrics/senior/stack/kernel")
async def kernel_stack(pid: int = Query(..., ge=1)) -> Dict[int, List[str]]:
    """获取指定进程所有线程的内核态调用栈"""
    stacks = senior.get_kernel_stack(pid)
    if not stacks:
        raise HTTPException(status_code=404, detail=f"Cannot read kernel stack for PID {pid}")
    return stacks


@app.post("/")
async def root():
    """根路径：运行状态提示"""
    return {"message": "System Monitor is running. Try GET /metrics"}


# ================= 启动服务 =================

if __name__ == '__main__':
    # 确保配置文件存在
    ensure_config_exists()

    # 修复配置文件权限
    try:
        os.chmod(CONFIG_PATH, 0o644)
        logger.info(f"设置配置文件权限: {CONFIG_PATH}")
    except Exception as e:
        logger.error(f"权限设置失败: {str(e)}")

    uvicorn.run(app, host="0.0.0.0", port=8003, log_config=None)
