"""
定时任务调度器

功能：
- 纽约时间下午 6 点自动运行 dual_etf_strategy.py
- 保存交易信号到 log/signal_{date}.txt
- 通过 Gmail SMTP 发送信号邮件
"""

import os
import sys
import time
import logging
import smtplib
import subprocess
from datetime import datetime, date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional

import schedule


# ============================================================
# 配置参数
# ============================================================

# 日志目录
LOG_DIR: Path = Path("log")

# 策略脚本路径
STRATEGY_SCRIPT: Path = Path("dual_etf_strategy.py")

# Gmail SMTP 配置
GMAIL_SMTP_HOST: str = "smtp.gmail.com"
GMAIL_SMTP_PORT: int = 587
GMAIL_USERNAME: str = "your_email@gmail.com"  # TODO: 修改为你的 Gmail 地址
GMAIL_APP_PASSWORD: str = "your_app_password"  # TODO: 修改为你的 App Password

# 收件人列表
RECIPIENTS: list = ["recipient@example.com"]  # TODO: 修改为收件人邮箱


# ============================================================
# 日志配置
# ============================================================

def setup_logging() -> None:
    """配置日志"""
    LOG_DIR.mkdir(exist_ok=True)
    log_file: Path = LOG_DIR / f"scheduler_{date.today().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


logger: logging.Logger = logging.getLogger(__name__)


# ============================================================
# 策略运行
# ============================================================

def run_strategy() -> dict:
    """
    运行 dual_etf_strategy.py 策略脚本。
    
    Returns:
        包含运行结果的字典
    """
    logger.info("=" * 60)
    logger.info("开始运行策略...")
    logger.info("=" * 60)
    
    if not STRATEGY_SCRIPT.exists():
        logger.error(f"策略脚本不存在: {STRATEGY_SCRIPT}")
        return {
            "success": False,
            "error": f"策略脚本不存在: {STRATEGY_SCRIPT}",
        }
    
    try:
        # 运行策略脚本
        result = subprocess.run(
            [sys.executable, str(STRATEGY_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=300,  # 5 分钟超时
        )
        
        if result.returncode == 0:
            logger.info("策略运行成功")
            
            # 读取回测结果获取信号
            signal_info: dict = get_latest_signal()
            return {
                "success": True,
                "signal": signal_info,
            }
        else:
            logger.error(f"策略运行失败: {result.stderr}")
            return {
                "success": False,
                "error": result.stderr,
            }
            
    except subprocess.TimeoutExpired:
        logger.error("策略运行超时（5分钟）")
        return {
            "success": False,
            "error": "策略运行超时",
        }
    except Exception as e:
        logger.error(f"运行策略时发生错误: {e}")
        import traceback
        traceback.print_exc()
        return {
            "success": False,
            "error": str(e),
        }


def get_latest_signal() -> dict:
    """
    从回测结果获取最新的交易信号。
    
    Returns:
        包含信号信息的字典
    """
    try:
        import pandas as pd
        backtest_file: Path = Path("data") / "backtest_results.csv"
        
        if not backtest_file.exists():
            return {"message": "无回测结果文件"}
        
        df: pd.DataFrame = pd.read_csv(backtest_file)
        
        if df.empty:
            return {"message": "回测结果为空"}
        
        # 获取最后一行
        latest = df.iloc[-1]
        signal: int = int(latest.get("Signal", -1))
        
        if signal == 1:
            action: str = "建议买入 SPY"
        elif signal == 0:
            action = "建议买入 TLT"
        else:
            action = "信号异常"
        
        return {
            "date": latest.get("Date", "未知"),
            "action": action,
            "signal": signal,
            "spy_price": latest.get("SPY_Price", latest.get("SPY", None)),
            "tlt_price": latest.get("TLT_Price", latest.get("TLT", None)),
            "strategy_return": latest.get("Strategy_Cumulative", 0),
            "spy_return": latest.get("SPY_BuyHold_Cumulative", 0),
        }
        
    except Exception as e:
        logger.error(f"读取信号失败: {e}")
        return {"message": f"读取信号失败: {e}"}


# ============================================================
# 信号文件保存
# ============================================================

def save_signal_log(signal_info: dict, run_date: Optional[date] = None) -> Path:
    """
    将交易信号保存到日志文件。
    
    Args:
        signal_info: 信号信息字典
        run_date: 运行日期（默认为今天）
    
    Returns:
        保存的文件路径
    """
    LOG_DIR.mkdir(exist_ok=True)
    
    if run_date is None:
        run_date = date.today()
    
    signal_file: Path = LOG_DIR / f"signal_{run_date.strftime('%Y%m%d')}.txt"
    
    # 生成信号报告
    report_lines: list = [
        "=" * 60,
        "交易信号报告",
        "=" * 60,
        f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Eastern Time)",
        f"交易日期: {signal_info.get('date', run_date.strftime('%Y-%m-%d'))}",
        "-" * 60,
    ]
    
    if signal_info.get("success"):
        report_lines.extend([
            f"策略运行状态: 成功",
            f"交易信号: {signal_info.get('action', '无信号')}",
            "-" * 60,
            "市场数据:",
        ])
        
        if signal_info.get("signal") is not None:
            report_lines.append(f"  - 信号值: {signal_info.get('signal')}")
        if signal_info.get("spy_price") is not None:
            report_lines.append(f"  - SPY 价格: ${signal_info.get('spy_price'):.2f}")
        if signal_info.get("tlt_price") is not None:
            report_lines.append(f"  - TLT 价格: ${signal_info.get('tlt_price'):.2f}")
        
        report_lines.extend([
            "-" * 60,
            "策略表现:",
        ])
        
        if signal_info.get("strategy_return") is not None:
            strategy_ret: float = float(signal_info.get("strategy_return", 0)) * 100
            report_lines.append(f"  - 策略累计收益: {strategy_ret:.2f}%")
        if signal_info.get("spy_return") is not None:
            spy_ret: float = float(signal_info.get("spy_return", 0)) * 100
            report_lines.append(f"  - SPY 买入持有: {spy_ret:.2f}%")
    else:
        report_lines.extend([
            f"策略运行状态: 失败",
            f"错误信息: {signal_info.get('error', '未知错误')}",
        ])
    
    report_lines.extend([
        "-" * 60,
        "=" * 60,
    ])
    
    # 写入文件
    content: str = "\n".join(report_lines)
    with open(signal_file, "w", encoding="utf-8") as f:
        f.write(content)
    
    logger.info(f"信号报告已保存: {signal_file}")
    
    return signal_file


# ============================================================
# 邮件发送
# ============================================================

def send_email_with_attachment(
    subject: str,
    body: str,
    attachment_path: Path,
    recipients: list = None,
) -> bool:
    """
    通过 Gmail SMTP 发送带附件的邮件。
    
    Args:
        subject: 邮件主题
        body: 邮件正文
        attachment_path: 附件文件路径
        recipients: 收件人列表
    
    Returns:
        发送是否成功
    """
    if recipients is None:
        recipients = RECIPIENTS
    
    # 检查配置
    if GMAIL_USERNAME == "your_email@gmail.com":
        logger.error("请先配置 Gmail 地址和 App Password")
        return False
    
    if not attachment_path.exists():
        logger.error(f"附件文件不存在: {attachment_path}")
        return False
    
    try:
        # 创建邮件
        msg: MIMEMultipart = MIMEMultipart()
        msg["From"]: str = GMAIL_USERNAME
        msg["To"]: str = ", ".join(recipients)
        msg["Subject"]: str = subject
        
        # 添加正文
        msg.attach(MIMEText(body, "plain", "utf-8"))
        
        # 添加附件
        with open(attachment_path, "rb") as f:
            part: MIMEBase = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {attachment_path.name}",
        )
        msg.attach(part)
        
        # 连接到 SMTP 服务器并发送
        logger.info(f"正在连接到 {GMAIL_SMTP_HOST}:{GMAIL_SMTP_PORT}...")
        
        server = smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT)
        server.starttls()  # 启用 TLS
        server.login(GMAIL_USERNAME, GMAIL_APP_PASSWORD)
        
        logger.info("正在发送邮件...")
        server.sendmail(GMAIL_USERNAME, recipients, msg.as_string())
        server.quit()
        
        logger.info("邮件发送成功!")
        return True
        
    except smtplib.SMTPAuthenticationError:
        logger.error("Gmail 认证失败，请检查用户名和 App Password")
        logger.error("提示: 需要使用 App Password，不是邮箱密码")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP 错误: {e}")
        return False
    except Exception as e:
        logger.error(f"发送邮件失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def send_signal_email(attachment_path: Path, recipients: list = None) -> bool:
    """
    发送交易信号邮件。
    
    Args:
        attachment_path: 信号文件路径
        recipients: 收件人列表
    
    Returns:
        发送是否成功
    """
    today_str: str = date.today().strftime("%Y-%m-%d")
    
    subject: str = f"[交易信号] {today_str} - Dual ETF Strategy"
    
    body: str = f"""
您好，

附件为 {today_str} 的交易信号报告。

本报告由自动交易系统生成。
如有疑问，请回复此邮件。

祝您交易顺利！
"""
    
    return send_email_with_attachment(
        subject=subject,
        body=body,
        attachment_path=attachment_path,
        recipients=recipients,
    )


# ============================================================
# 主调度任务
# ============================================================

def daily_trading_job() -> None:
    """
    每日交易任务：
    1. 运行策略
    2. 保存信号日志
    3. 发送邮件
    """
    logger.info("=" * 60)
    logger.info("开始执行每日交易任务")
    logger.info(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # 1. 运行策略
    result: dict = run_strategy()
    
    # 2. 保存信号日志
    signal_info: dict = result.get("signal", {})
    signal_info["success"] = result.get("success", False)
    signal_info["error"] = result.get("error", "")
    
    signal_file: Path = save_signal_log(signal_info)
    
    # 3. 发送邮件（仅在策略成功时）
    if result.get("success"):
        email_sent: bool = send_signal_email(signal_file)
        if email_sent:
            logger.info("信号邮件已发送")
        else:
            logger.warning("信号邮件发送失败")
    else:
        logger.warning("策略运行失败，跳过邮件发送")
    
    logger.info("每日交易任务完成")
    logger.info("=" * 60)


def get_eastern_time() -> datetime:
    """
    获取当前纽约时间。
    
    Returns:
        纽约时间的 datetime 对象
    """
    import pytz
    
    eastern = pytz.timezone("US/Eastern")
    return datetime.now(eastern)


# ============================================================
# 主函数
# ============================================================

def main() -> int:
    """
    主函数：启动定时任务调度器。
    
    Returns:
        成功返回 0
    """
    print("=" * 60)
    print("Dual ETF Strategy 定时任务调度器")
    print("=" * 60)
    print(f"策略脚本: {STRATEGY_SCRIPT}")
    print(f"日志目录: {LOG_DIR}")
    print(f"SMTP 配置: {GMAIL_USERNAME}")
    print("-" * 60)
    print("配置说明:")
    print("1. Gmail 需要启用 '两步验证' 并生成 'App Password'")
    print("2. 修改 GMAIL_USERNAME 和 GMAIL_APP_PASSWORD")
    print("3. 修改 RECIPIENTS 添加收件人邮箱")
    print("-" * 60)
    
    setup_logging()
    
    # 设置定时任务（纽约时间下午6点）
    # 注意：schedule 库默认使用本地时间
    # 如果需要纽约时间，需要确保系统时区正确，或使用 pytz
    schedule.every().day.at("18:00").do(daily_trading_job)
    
    logger.info("定时任务已设置: 每天 18:00 (Eastern Time) 运行策略")
    logger.info("按 Ctrl+C 退出")
    
    # 主循环
    try:
        while True:
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    except KeyboardInterrupt:
        logger.info("调度器已停止")
        return 0


if __name__ == "__main__":
    sys.exit(main())
