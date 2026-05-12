"""
数据获取模块

功能：
- 从 Yahoo Finance (yfinance) 获取数据
- 失败时自动切换到 akshare（中文镜像源）
- 数据清洗和本地缓存
- 支持增量更新
"""

import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import yfinance as yf

logger: logging.Logger = logging.getLogger(__name__)


class DataFetcher:
    """
    数据获取器类
    
    主要功能：
    - 从 yfinance 下载历史数据
    - 失败时自动切换到 akshare
    - 计算并使用调整后价格 (Adj Close)
    - 本地 CSV/Parquet 缓存
    - 增量更新数据
    """
    
    # 数据缓存目录
    CACHE_DIR: Path = Path("data")
    
    # 需要的列
    REQUIRED_COLUMNS: list = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    
    def __init__(self, cache_dir: Optional[Path] = None) -> None:
        """
        初始化数据获取器。
        
        Args:
            cache_dir: 缓存目录路径，默认为 data/
        """
        if cache_dir is not None:
            self.CACHE_DIR = cache_dir
        
        # 确保缓存目录存在
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"数据缓存目录: {self.CACHE_DIR.absolute()}")
    
    def _get_cache_path(self, ticker: str, ext: str = "csv") -> Path:
        """
        获取缓存文件路径。
        
        Args:
            ticker: 股票代码
            ext: 文件扩展名 ('csv' 或 'parquet')
        
        Returns:
            缓存文件路径
        """
        return self.CACHE_DIR / f"{ticker}.{ext}"
    
    def _load_from_cache(self, ticker: str) -> Optional[pd.DataFrame]:
        """
        从本地缓存加载数据。
        
        Args:
            ticker: 股票代码
        
        Returns:
            缓存的数据，如果不存在返回 None
        """
        cache_path = self._get_cache_path(ticker, "csv")
        
        if not cache_path.exists():
            return None
        
        try:
            df: pd.DataFrame = pd.read_csv(cache_path, parse_dates=["Date"])
            df = df.sort_values("Date").reset_index(drop=True)
            logger.info(f"已从缓存加载 {ticker}: {len(df)} 条记录")
            return df
        except Exception as e:
            logger.warning(f"读取缓存失败 {ticker}: {e}")
            return None
    
    def _save_to_cache(self, df: pd.DataFrame, ticker: str) -> None:
        """
        保存数据到本地缓存。
        
        Args:
            df: 数据DataFrame
            ticker: 股票代码
        """
        cache_path = self._get_cache_path(ticker, "csv")
        df.to_csv(cache_path, index=False)
        logger.info(f"数据已缓存: {cache_path}")
    
    def _fetch_from_yfinance(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_retries: int = 3,
    ) -> Optional[pd.DataFrame]:
        """
        从 yfinance 获取数据。
        
        Args:
            ticker: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            max_retries: 最大重试次数
        
        Returns:
            数据DataFrame，失败返回 None
        """
        for attempt in range(max_retries):
            try:
                logger.info(f"正在从 yfinance 下载 {ticker}...")
                
                df: pd.DataFrame = yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    auto_adjust=False,
                    progress=False,
                )
                
                if df.empty:
                    logger.warning(f"yfinance 返回空数据: {ticker}")
                    if attempt < max_retries - 1:
                        continue
                    return None
                
                # 处理 MultiIndex 列名
                if isinstance(df.columns, pd.MultiIndex):
                    if df.columns.get_level_values(0).duplicated().any():
                        df.columns = [col[1] for col in df.columns]
                    else:
                        df.columns = [col[0] for col in df.columns]
                
                # 确保必要列存在
                missing = set(self.REQUIRED_COLUMNS) - set(df.columns)
                if missing:
                    logger.error(f"yfinance 数据缺少列: {missing}")
                    return None
                
                # 重置索引，将 Date 变为普通列
                df = df.reset_index()
                
                # 确保 Date 列为 datetime 类型
                if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
                    df["Date"] = pd.to_datetime(df["Date"])
                
                # 格式化日期
                df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
                
                # 排序列
                df = df[["Date"] + self.REQUIRED_COLUMNS]
                
                logger.info(f"yfinance 下载成功: {ticker}, {len(df)} 条记录")
                return df
                
            except Exception as e:
                logger.warning(f"yfinance 下载失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    continue
        
        return None
    
    def _fetch_from_akshare(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        从 akshare 获取数据（中文镜像源）。
        
        Args:
            ticker: 股票代码
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            数据DataFrame，失败返回 None
        """
        try:
            import akshare as ak
            
            logger.info(f"正在从 akshare 下载 {ticker}...")
            
            # akshare 股票数据接口
            if ticker.startswith(("60", "00", "30")):
                # A股
                symbol = f"{ticker}.SH" if ticker.startswith("6") else f"{ticker}.SZ"
                df: pd.DataFrame = ak.stock_zh_a_hist(
                    symbol=symbol,
                    start_date=start_date.replace("-", "") if start_date else None,
                    end_date=end_date.replace("-", "") if end_date else None,
                    adjust="qfq",
                )
            else:
                # ETF 或美股，使用 yfinance 格式
                logger.warning(f"akshare 暂不支持 {ticker}，使用 yfinance")
                return None
            
            if df is None or df.empty:
                logger.warning(f"akshare 返回空数据: {ticker}")
                return None
            
            # 重命名列
            column_map = {
                "日期": "Date",
                "开盘": "Open",
                "收盘": "Close",
                "最高": "High",
                "最低": "Low",
                "成交量": "Volume",
                "成交额": "Amount",
            }
            df = df.rename(columns=column_map)
            
            # 计算 Adj Close（使用收盘价）
            df["Adj Close"] = df["Close"]
            
            # 格式化日期
            if pd.api.types.is_datetime64_any_dtype(df["日期"]):
                df["Date"] = df["日期"].dt.strftime("%Y-%m-%d")
            else:
                df["Date"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
            
            # 选择并排序列
            df = df[["Date"] + self.REQUIRED_COLUMNS]
            
            logger.info(f"akshare 下载成功: {ticker}, {len(df)} 条记录")
            return df
            
        except ImportError:
            logger.error("akshare 未安装，跳过")
            return None
        except Exception as e:
            logger.error(f"akshare 下载失败: {e}")
            return None
    
    def fetch(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_update: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        获取数据，优先使用 yfinance，失败时使用 akshare。
        
        Args:
            ticker: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)，默认为 2015-01-01
            end_date: 结束日期 (YYYY-MM-DD)，默认为今天
            force_update: 是否强制更新（忽略缓存）
        
        Returns:
            数据DataFrame，失败返回 None
        """
        if start_date is None:
            start_date = "2015-01-01"
        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")
        
        # 尝试从缓存加载（除非强制更新）
        if not force_update:
            cached_df = self._load_from_cache(ticker)
            if cached_df is not None:
                # 检查缓存数据是否需要增量更新
                last_date = cached_df["Date"].max()
                if last_date < end_date:
                    logger.info(f"缓存数据最新到 {last_date}，进行增量更新...")
                    incremental_df = self._fetch_incremental(ticker, last_date, end_date)
                    if incremental_df is not None and not incremental_df.empty:
                        # 合并新数据
                        cached_df = pd.concat([cached_df, incremental_df], ignore_index=True)
                        cached_df = cached_df.drop_duplicates(subset=["Date"], keep="last")
                        cached_df = cached_df.sort_values("Date").reset_index(drop=True)
                        self._save_to_cache(cached_df, ticker)
                        logger.info(f"增量更新完成: {ticker}, 共 {len(cached_df)} 条记录")
                return cached_df
        
        # 首先尝试 yfinance
        df = self._fetch_from_yfinance(ticker, start_date, end_date)
        
        if df is None:
            logger.warning(f"yfinance 失败，尝试 akshare 作为备用源...")
            df = self._fetch_from_akshare(ticker, start_date, end_date)
        
        if df is not None and not df.empty:
            self._save_to_cache(df, ticker)
        
        return df
    
    def _fetch_incremental(
        self,
        ticker: str,
        last_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """
        增量获取数据（仅获取最后一个交易日）。
        
        Args:
            ticker: 股票代码
            last_date: 缓存中最后日期
            end_date: 目标结束日期
        
        Returns:
            新数据DataFrame
        """
        # 从 last_date 的下一个工作日开始获取
        last_dt = pd.to_datetime(last_date)
        next_day = (last_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        
        # 如果距离今天超过7天，获取最近7天数据
        end_dt = pd.to_datetime(end_date)
        if (end_dt - last_dt).days > 7:
            next_day = (end_dt - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        
        logger.info(f"增量获取: {ticker} 从 {next_day} 到 {end_date}")
        
        df = self._fetch_from_yfinance(ticker, next_day, end_date)
        
        if df is not None and not df.empty:
            # 过滤掉已存在的日期
            df = df[df["Date"] > last_date]
        
        return df
    
    def fetch_multiple(
        self,
        tickers: list,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """
        获取多个股票数据。
        
        Args:
            tickers: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            {ticker: DataFrame} 字典
        """
        results = {}
        
        for ticker in tickers:
            df = self.fetch(ticker, start_date, end_date)
            if df is not None:
                results[ticker] = df
            else:
                logger.error(f"获取 {ticker} 数据失败")
        
        return results


# ============================================================
# 主函数
# ============================================================

def main() -> int:
    """主函数：测试数据获取"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    
    fetcher = DataFetcher()
    
    # 测试获取单个股票
    print("\n测试获取 SPY 数据...")
    spy_df = fetcher.fetch("SPY")
    if spy_df is not None:
        print(f"SPY 数据: {len(spy_df)} 条记录")
        print(f"时间范围: {spy_df['Date'].min()} ~ {spy_df['Date'].max()}")
        print(spy_df.tail())
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())