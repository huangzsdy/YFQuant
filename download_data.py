"""
SPY 和 TLT 历史数据下载脚本

功能：下载 SPY 和 TLT 从 2015年1月1日到今天的所有历史日线数据，并保存为 CSV 文件。
字段：Date, Open, High, Low, Close, Adj Close, Volume

符合 PEP8 规范，包含完整的类型注解、错误处理和详细日志。
"""

import os
import sys
import logging
from datetime import date
from pathlib import Path
from typing import List, Optional

import yfinance as yf
import pandas as pd


# ============================================================
# 配置参数
# ============================================================

# 要下载的股票代码列表
TICKERS: List[str] = ["SPY", "TLT"]

# 数据下载时间范围
START_DATE: str = "2015-01-01"
END_DATE: str = date.today().strftime("%Y-%m-%d")

# 数据存储目录
DATA_DIR: Path = Path("data")

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: logging.Logger = logging.getLogger(__name__)


# ============================================================
# 工具函数
# ============================================================

def ensure_data_directory(data_dir: Path) -> None:
    """
    确保数据存储目录存在，如果不存在则创建。
    
    Args:
        data_dir: 数据目录路径
    """
    if not data_dir.exists():
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"已创建数据目录: {data_dir.absolute()}")
    else:
        logger.info(f"数据目录已存在: {data_dir.absolute()}")


def download_ticker_data(
    ticker: str,
    start_date: str,
    end_date: str,
    output_dir: Path,
) -> Optional[pd.DataFrame]:
    """
    下载单个股票的历史数据并保存为 CSV 文件。
    
    Args:
        ticker: 股票代码（如 "SPY", "TLT"）
        start_date: 开始日期，格式 YYYY-MM-DD
        end_date: 结束日期，格式 YYYY-MM-DD
        output_dir: CSV 文件输出目录
    
    Returns:
        下载成功返回 DataFrame，失败返回 None
    """
    logger.info(f"开始下载 {ticker} 数据，时间范围: {start_date} ~ {end_date}")
    
    try:
        # 下载数据，auto_adjust=False 保留 Adj Close 字段
        df: pd.DataFrame = yf.download(
            ticker,
            start=start_date,
            end=end_date,
            auto_adjust=False,
            progress=True,
        )
    except Exception as e:
        logger.error(f"下载 {ticker} 数据时发生网络错误: {e}")
        return None
    
    # 检查是否获取到数据
    if df.empty:
        logger.warning(f"{ticker} 在指定时间范围内没有数据")
        return None
    
    # 处理 MultiIndex 列问题
    # yfinance.download() 返回的 DataFrame 通常有多层列索引
    # 例如：('SPY', 'Open'), ('SPY', 'High') 或 ('Close', 'SPY') 等
    if isinstance(df.columns, pd.MultiIndex):
        # 如果是多层索引，取第一个级别的列名
        # yfinance 通常使用 (Ticker, Field) 或 (Field, Ticker) 结构
        if df.columns.nlevels == 2:
            # 尝试展平列名
            if df.columns.get_level_values(0).duplicated().any():
                # 格式为 (Ticker, Field)，取第二层作为字段名
                df.columns = [col[1] for col in df.columns]
            else:
                # 格式为 (Field, Ticker)，取第一层作为字段名
                df.columns = [col[0] for col in df.columns]
            logger.debug(f"已处理 MultiIndex 列: {list(df.columns)}")
    
    # 确保必要的字段存在
    required_columns: List[str] = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    missing_columns: List[str] = [col for col in required_columns if col not in df.columns]
    
    if missing_columns:
        logger.error(f"{ticker} 数据缺少必要字段: {missing_columns}")
        logger.error(f"实际列名: {list(df.columns)}")
        return None
    
    # 重置索引，将 Date 变为普通列
    df = df.reset_index()
    
    # 确保 Date 列为 datetime 类型
    if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
        df["Date"] = pd.to_datetime(df["Date"])
    
    # 格式化 Date 列为日期字符串 (YYYY-MM-DD)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    
    # 选择并排序列
    columns_order: List[str] = ["Date", "Open", "High", "Low", "Close", "Adj Close", "Volume"]
    df = df[columns_order]
    
    # 保存为 CSV
    output_path: Path = output_dir / f"{ticker}.csv"
    try:
        df.to_csv(output_path, index=False)
        logger.info(
            f"{ticker} 数据已保存至 {output_path}，"
            f"共 {len(df)} 条记录，"
            f"时间范围: {df['Date'].iloc[0]} ~ {df['Date'].iloc[-1]}"
        )
    except Exception as e:
        logger.error(f"保存 {ticker} 数据到 CSV 文件时发生错误: {e}")
        return None
    
    return df


# ============================================================
# 主函数
# ============================================================

def main() -> int:
    """
    主函数：下载所有股票数据。
    
    Returns:
        成功返回 0，失败返回 1
    """
    logger.info("=" * 60)
    logger.info("SPY 和 TLT 历史数据下载脚本")
    logger.info("=" * 60)
    logger.info(f"下载时间范围: {START_DATE} 至 {END_DATE}")
    logger.info(f"股票列表: {TICKERS}")
    logger.info("-" * 60)
    
    # 确保数据目录存在
    ensure_data_directory(DATA_DIR)
    
    # 下载每个股票的数据
    success_count: int = 0
    failure_count: int = 0
    
    for ticker in TICKERS:
        df: Optional[pd.DataFrame] = download_ticker_data(
            ticker=ticker,
            start_date=START_DATE,
            end_date=END_DATE,
            output_dir=DATA_DIR,
        )
        
        if df is not None:
            success_count += 1
        else:
            failure_count += 1
    
    # 输出统计信息
    logger.info("-" * 60)
    logger.info(f"数据下载完成！成功: {success_count}/{len(TICKERS)}，失败: {failure_count}/{len(TICKERS)}")
    logger.info(f"数据文件保存位置: {DATA_DIR.absolute()}")
    logger.info("=" * 60)
    
    # 如果有任何失败，返回非零退出码
    return 0 if failure_count == 0 else 1


if __name__ == "__main__":
    # 使用 sys.exit 确保返回正确的退出码
    sys.exit(main())
