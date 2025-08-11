import asyncio
import os, sys
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import uvicorn
from fastapi import FastAPI, Query, HTTPException, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import pytz

# 确保能 import 上级 monitor 包
current_dir = os.path.dirname(os.path.abspath(__file__))
monitor_dir = os.path.dirname(current_dir)
sys.path.insert(0, monitor_dir)

from monitor.collector.cpu import CPUCollector
from monitor.collector.disk import DiskCollector
from monitor.collector.network import NetworkCollector
from monitor.collector import system_command, log_reader
from monitor.collector.senior import SeniorCollector
from monitor.config import USE_THRESHOLD, EMAIL_REPORT_TIME, RECIPIENTS
from monitor.utils.send_mail import send_alert_email, send_info_email, verify_signature
from monitor.utils.os_info import get_os_info

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
async def check_and_alert():
    global _last_alert_time
    now = time.time()
    # 如果上一次发送时间距今不到 30 分钟，跳过
    if now - _last_alert_time < 30 * 60:
        return

    data = get_os_info()
    cpu_data = data['cpu']["cpu_percent_overall"]
    cpu_flag = cpu_data > USE_THRESHOLD["cpu"]

    memory_data = data['cpu']["memory_percent"]
    memory_flag = memory_data > USE_THRESHOLD["memory"]

    disk_data = data['disk']
    disk_flag = False
    for item in disk_data.values():
        if item.get("percent", 0) > USE_THRESHOLD["disk"]:
            disk_flag = True
            break

    if cpu_flag or memory_flag or disk_flag:
        # 更新上次发送时间
        await send_alert_email(recipients=RECIPIENTS)
        _last_alert_time = now
        # 发送警告邮件
        await send_alert_email(
            recipients=RECIPIENTS,
        )
        print(f"[!] 发送邮件警告: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}", flush=True)


async def daily_info_report():
    # 获取全量监控
    await send_info_email(
        recipients=RECIPIENTS,
    )
    print(f"[*] 发送日报: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}", flush=True)


# —— Lifespan：启动/关闭调度器 —— #
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 在创建调度器时显式设置时区
    scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Shanghai'))  # 使用上海时区（UTC+8）

    # 告警，每分钟跑一次，若错过可容忍 30 分钟误差
    scheduler.add_job(
        check_and_alert,
        trigger=IntervalTrigger(
            seconds=60,
            timezone=pytz.timezone('Asia/Shanghai')  # 显式设置时区
        ),
        id="check_alert_job",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60
    )
    # 日报，每天固定时刻
    hour, minute = map(int, EMAIL_REPORT_TIME.split(":"))
    scheduler.add_job(
        daily_info_report,
        trigger=CronTrigger(
            hour=hour,
            minute=minute,
            timezone=pytz.timezone('Asia/Shanghai')  # 显式设置时区
        ),
        id="daily_report_job",
        replace_existing=True
    )
    scheduler.start()
    yield
    scheduler.shutdown()


# —— 创建应用 —— #
app = FastAPI(
    title="System Monitor with Alerts & Daily Report",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# =============== 对外邮件接口 ===============

# 请求体模型
class EmailRequest(BaseModel):
    recipients: List[EmailStr]
    timestamp: int
    signature: str


# —— 路由 —— #
router = APIRouter()


@router.post("/report/email")
async def send_email(req: EmailRequest):
    """发送定时报告邮件，含验签"""
    if not verify_signature(req.recipients, req.timestamp, req.signature):
        raise HTTPException(status_code=403, detail="签名验证失败")

    await send_info_email(recipients=req.recipients)
    return {"message": "邮件发送成功"}


app.include_router(router, prefix="/api")


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


"""
运行命令：
uvicorn monitor.exporter.rest_api:app --host 0.0.0.0 --port 8000
访问：http://127.0.0.1:8000/metrics
文档：http://127.0.0.1:8000/metrics/docs
"""

if __name__ == '__main__':
    uvicorn.run(app, host="0.0.0.0", port=8002)
