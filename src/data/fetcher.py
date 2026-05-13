"""
数据获取模块

功能：
- 从 Yahoo Finance (yfinance) 获取数据
- 失败时自动切换到其他备用源
- 数据清洗和本地缓存
- 支持增量更新
- 添加请求延迟避免 rate limit
"""

import logging
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Tuple

import pandas as pd
import numpy as np

logger: logging.Logger = logging.getLogger(__name__)


class DataFetcher:
    """
    数据获取器类
    
    主要功能：
    - 从多个数据源获取历史数据
    - 自动切换到备用源
    - 计算并使用调整后价格 (Adj Close)
    - 本地 CSV 缓存
    - 增量更新数据
    """
    
    # 数据缓存目录
    CACHE_DIR: Path = Path("data")
    
    # 需要的列
    REQUIRED_COLUMNS: list = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    
    # 请求间隔（秒），避免 rate limit
    REQUEST_DELAY: float = 2.0
    
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
        
        # yfinance Ticker 对象缓存
        self._tickers_cache: dict = {}
    
    def _get_cache_path(self, ticker: str, ext: str = "csv") -> Path:
        """获取缓存文件路径"""
        return self.CACHE_DIR / f"{ticker}.{ext}"
    
    def _load_from_cache(self, ticker: str) -> Optional[pd.DataFrame]:
        """从本地缓存加载数据"""
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
        """保存数据到本地缓存"""
        cache_path = self._get_cache_path(ticker, "csv")
        df.to_csv(cache_path, index=False)
        logger.info(f"数据已缓存: {cache_path}")
    
    def _wait_before_request(self, attempt: int = 0) -> None:
        """请求前等待，指数退避"""
        delay = self.REQUEST_DELAY * (2 ** attempt)
        max_delay = 60
        delay = min(delay, max_delay)
        logger.info(f"等待 {delay:.1f} 秒后重试...")
        time.sleep(delay)
    
    def _fetch_from_yfinance(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        max_retries: int = 5,
    ) -> Optional[pd.DataFrame]:
        """从 yfinance 获取数据"""
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self._wait_before_request(attempt)
                
                logger.info(f"正在从 yfinance 下载 {ticker} (尝试 {attempt + 1}/{max_retries})...")
                
                import yfinance as yf
                
                # 使用 history 方法而不是 download（更稳定）
                ticker_obj = yf.Ticker(ticker)
                df: pd.DataFrame = ticker_obj.history(
                    start=start_date,
                    end=end_date,
                    auto_adjust=False,
                )
                
                if df.empty:
                    logger.warning(f"yfinance 返回空数据: {ticker}")
                    if attempt < max_retries - 1:
                        continue
                    return None
                
                # 重置索引
                df = df.reset_index()
                
                # 处理 Date 列
                if "Date" not in df.columns:
                    if "DatetimeIndex" in str(type(df.index)):
                        df["Date"] = df.index
                
                if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
                    df["Date"] = pd.to_datetime(df["Date"])
                
                df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
                
                # 添加缺失列
                for col in self.REQUIRED_COLUMNS:
                    if col not in df.columns:
                        if col == "Volume":
                            df[col] = 0
                        else:
                            df[col] = df.get("Close", 0)
                
                df = df[["Date"] + self.REQUIRED_COLUMNS]
                
                logger.info(f"yfinance 下载成功: {ticker}, {len(df)} 条记录")
                return df
                
            except Exception as e:
                error_str = str(e)
                if "Rate limited" in error_str or "429" in error_str:
                    logger.warning(f"yfinance rate limit (尝试 {attempt + 1}/{max_retries})")
                else:
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
        """从 akshare 获取数据"""
        try:
            import akshare as ak
            
            logger.info(f"正在从 akshare 下载 {ticker}...")
            
            # A股
            if ticker.startswith(("60", "00", "30", "68")):
                symbol = f"{ticker}.SH" if ticker.startswith(("60", "68")) else f"{ticker}.SZ"
                df: pd.DataFrame = ak.stock_zh_a_hist(
                    symbol=symbol,
                    start_date=start_date.replace("-", "") if start_date else None,
                    end_date=end_date.replace("-", "") if end_date else None,
                    adjust="qfq",
                )
            else:
                # 尝试 ETF
                try:
                    df = ak.fund_etf_hist_sina(symbol=ticker)
                except Exception:
                    logger.warning(f"akshare 暂不支持 {ticker}")
                    return None
            
            if df is None or df.empty:
                return None
            
            # 重命名列
            column_map = {
                "日期": "Date", "开盘": "Open", "收盘": "Close",
                "最高": "High", "最低": "Low", "成交量": "Volume",
            }
            df = df.rename(columns=column_map)
            
            if "Adj Close" not in df.columns:
                df["Adj Close"] = df["Close"]
            
            if pd.api.types.is_datetime64_any_dtype(df["日期"]):
                df["Date"] = df["日期"].dt.strftime("%Y-%m-%d")
            else:
                df["Date"] = pd.to_datetime(df["日期"]).dt.strftime("%Y-%m-%d")
            
            df = df[["Date"] + self.REQUIRED_COLUMNS]
            
            logger.info(f"akshare 下载成功: {ticker}, {len(df)} 条记录")
            return df
            
        except ImportError:
            logger.error("akshare 未安装")
            return None
        except Exception as e:
            logger.error(f"akshare 下载失败: {e}")
            return None
    
    def _fetch_from_pandas_datareader(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """从 pandas_datareader 获取数据（备用源）"""
        try:
            from pandas_datareader import data as pdr
            
            logger.info(f"正在从 pandas_datareader 下载 {ticker}...")
            
            start = pd.to_datetime(start_date) if start_date else pd.Timestamp("2015-01-01")
            end = pd.to_datetime(end_date) if end_date else date.today()
            
            df = pdr.get_data_yahoo(ticker, start=start, end=end)
            
            if df.empty:
                return None
            
            df = df.reset_index()
            
            # 标准化列名
            column_map = {
                "Date": "Date", "Open": "Open", "High": "High",
                "Low": "Low", "Close": "Close", "Adj Close": "Adj Close",
                "Volume": "Volume",
            }
            
            for col in df.columns:
                if col in column_map:
                    df = df.rename(columns={col: column_map[col]})
            
            if "Adj Close" not in df.columns:
                df["Adj Close"] = df["Close"]
            
            if not pd.api.types.is_datetime64_any_dtype(df["Date"]):
                df["Date"] = pd.to_datetime(df["Date"])
            
            df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
            
            for col in self.REQUIRED_COLUMNS:
                if col not in df.columns:
                    if col == "Volume":
                        df[col] = 0
                    else:
                        df[col] = df.get("Close", 0)
            
            df = df[["Date"] + self.REQUIRED_COLUMNS]
            
            logger.info(f"pandas_datareader 下载成功: {ticker}, {len(df)} 条记录")
            return df
            
        except ImportError:
            logger.error("pandas_datareader 未安装")
            return None
        except Exception as e:
            logger.error(f"pandas_datareader 下载失败: {e}")
            return None
    
    def _generate_sample_data(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        生成示例数据（当所有数据源都失败时使用）。
        用于测试和演示目的。
        """
        logger.warning(f"所有数据源失败，为 {ticker} 生成示例数据（仅供测试）")
        
        if start_date is None:
            start_date = "2015-01-01"
        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")
        
        # 生成日期范围
        dates = pd.date_range(start=start_date, end=end_date, freq="B")
        
        if len(dates) == 0:
            return None
        
        # 生成模拟价格数据
        np.random.seed(42 if ticker == "SPY" else 43)
        
        # SPY: 大概从 200 涨到 400
        # TLT: 大概从 100 涨到 130
        if ticker == "SPY":
            initial_price = 200
            drift = 0.0003
        elif ticker == "TLT":
            initial_price = 100
            drift = 0.0001
        else:
            initial_price = 100
            drift = 0.0002
        
        prices = [initial_price]
        for _ in range(len(dates) - 1):
            change = np.random.randn() * initial_price * 0.01 + drift * initial_price
            prices.append(max(prices[-1] + change, 1))
        
        df = pd.DataFrame({
            "Date": dates.strftime("%Y-%m-%d"),
            "Open": prices,
            "High": [p * (1 + abs(np.random.randn() * 0.005)) for p in prices],
            "Low": [p * (1 - abs(np.random.randn() * 0.005)) for p in prices],
            "Close": prices,
            "Adj Close": prices,
            "Volume": np.random.randint(50000000, 100000000, len(dates)),
        })
        
        logger.info(f"已生成 {ticker} 示例数据: {len(df)} 条记录")
        return df
    
    def fetch(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_update: bool = False,
        use_sample_on_failure: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        获取数据，多个数据源依次尝试。
        
        Args:
            ticker: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            force_update: 是否强制更新（忽略缓存）
            use_sample_on_failure: 所有源都失败时是否生成示例数据
        
        Returns:
            数据DataFrame，失败返回 None
        """
        if start_date is None:
            start_date = "2015-01-01"
        if end_date is None:
            end_date = date.today().strftime("%Y-%m-%d")
        
        # 尝试从缓存加载
        if not force_update:
            cached_df = self._load_from_cache(ticker)
            if cached_df is not None and len(cached_df) > 0:
                last_date = cached_df["Date"].max()
                # 确保类型一致：统一转为字符串比较
                if isinstance(last_date, pd.Timestamp):
                    last_date_str = last_date.strftime("%Y-%m-%d")
                else:
                    last_date_str = str(last_date)
                
                if last_date_str < end_date:
                    logger.info(f"缓存数据最新到 {last_date}，进行增量更新...")
                    incremental_df = self._fetch_incremental(ticker, last_date, end_date)
                    if incremental_df is not None and not incremental_df.empty:
                        cached_df = pd.concat([cached_df, incremental_df], ignore_index=True)
                        cached_df = cached_df.drop_duplicates(subset=["Date"], keep="last")
                        cached_df = cached_df.sort_values("Date").reset_index(drop=True)
                        self._save_to_cache(cached_df, ticker)
                        logger.info(f"增量更新完成: {ticker}, 共 {len(cached_df)} 条记录")
                return cached_df
        
        # 依次尝试各个数据源
        sources = [
            ("yfinance", self._fetch_from_yfinance),
            ("akshare", self._fetch_from_akshare),
            ("pandas_datareader", self._fetch_from_pandas_datareader),
        ]
        
        df = None
        for source_name, fetch_func in sources:
            df = fetch_func(ticker, start_date, end_date)
            if df is not None and not df.empty:
                break
        
        # 所有源都失败
        if df is None or df.empty:
            if use_sample_on_failure:
                df = self._generate_sample_data(ticker, start_date, end_date)
            else:
                logger.error(f"获取 {ticker} 数据失败")
                return None
        
        if df is not None and not df.empty:
            self._save_to_cache(df, ticker)
        
        return df
    
    def _fetch_incremental(
        self,
        ticker: str,
        last_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """增量获取数据"""
        last_dt = pd.to_datetime(last_date)
        next_day = (last_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        
        end_dt = pd.to_datetime(end_date)
        if (end_dt - last_dt).days > 7:
            next_day = (end_dt - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
        
        logger.info(f"增量获取: {ticker} 从 {next_day} 到 {end_date}")
        
        # 只尝试 yfinance（最常用）
        df = self._fetch_from_yfinance(ticker, next_day, end_date)
        
        if df is not None and not df.empty:
            df = df[df["Date"] > last_date]
        
        return df
    
    def fetch_multiple(
        self,
        tickers: list,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """获取多个股票数据"""
        results = {}
        
        for i, ticker in enumerate(tickers):
            if i > 0:
                logger.info(f"等待 {self.REQUEST_DELAY} 秒后继续...")
                time.sleep(self.REQUEST_DELAY)
            
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
    
    print("\n测试获取 SPY 数据...")
    spy_df = fetcher.fetch("SPY")
    if spy_df is not None:
        print(f"SPY 数据: {len(spy_df)} 条记录")
        print(f"时间范围: {spy_df['Date'].min()} ~ {spy_df['Date'].max()}")
        print(spy_df.tail())
    else:
        print("SPY 数据获取失败")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())