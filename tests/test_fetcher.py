"""
数据获取器测试

测试 DataFetcher 类的功能：
- 从 yfinance 获取数据
- 缓存功能
- 增量更新
- 错误处理
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data.fetcher import DataFetcher


class TestDataFetcher:
    """DataFetcher 测试类"""
    
    @pytest.fixture
    def fetcher(self, tmp_path):
        """创建测试用的 DataFetcher 实例"""
        return DataFetcher(cache_dir=tmp_path)
    
    @pytest.fixture
    def sample_data(self):
        """创建样本数据"""
        dates = pd.date_range("2020-01-01", periods=100, freq="B")
        return pd.DataFrame({
            "Date": dates.strftime("%Y-%m-%d"),
            "Open": 100 + np.random.randn(100).cumsum(),
            "High": 105 + np.random.randn(100).cumsum(),
            "Low": 95 + np.random.randn(100).cumsum(),
            "Close": 100 + np.random.randn(100).cumsum(),
            "Adj Close": 100 + np.random.randn(100).cumsum(),
            "Volume": np.random.randint(1000000, 10000000, 100),
        })
    
    def test_init(self, tmp_path):
        """测试初始化"""
        fetcher = DataFetcher(cache_dir=tmp_path)
        assert fetcher.CACHE_DIR == tmp_path
        assert tmp_path.exists()
    
    def test_get_cache_path(self, fetcher):
        """测试缓存路径生成"""
        path = fetcher._get_cache_path("SPY", "csv")
        assert path == fetcher.CACHE_DIR / "SPY.csv"
        
        path = fetcher._get_cache_path("AAPL", "parquet")
        assert path == fetcher.CACHE_DIR / "AAPL.parquet"
    
    def test_save_and_load_cache(self, fetcher, sample_data):
        """测试缓存保存和加载"""
        ticker = "TEST"
        
        # 保存到缓存
        fetcher._save_to_cache(sample_data, ticker)
        
        # 从缓存加载
        loaded_data = fetcher._load_from_cache(ticker)
        
        assert loaded_data is not None
        assert len(loaded_data) == len(sample_data)
        assert "Date" in loaded_data.columns
    
    def test_load_nonexistent_cache(self, fetcher):
        """测试加载不存在的缓存"""
        result = fetcher._load_from_cache("NONEXISTENT")
        assert result is None
    
    def test_save_to_cache_creates_directory(self, tmp_path):
        """测试保存缓存时自动创建目录"""
        cache_dir = tmp_path / "nested" / "dir"
        fetcher = DataFetcher(cache_dir=cache_dir)
        
        assert not cache_dir.exists()
        
        sample_data = pd.DataFrame({
            "Date": ["2020-01-01"],
            "Open": [100],
            "High": [105],
            "Low": [95],
            "Close": [100],
            "Adj Close": [100],
            "Volume": [1000000],
        })
        
        fetcher._save_to_cache(sample_data, "TEST")
        
        assert cache_dir.exists()
        assert (cache_dir / "TEST.csv").exists()
    
    @patch("yfinance.download")
    def test_fetch_from_yfinance_success(self, mock_download, fetcher):
        """测试 yfinance 成功获取数据"""
        # 模拟 yfinance 返回的数据
        dates = pd.date_range("2020-01-01", periods=10, freq="B")
        mock_df = pd.DataFrame({
            "Date": dates,
            "Open": [100] * 10,
            "High": [105] * 10,
            "Low": [95] * 10,
            "Close": [100] * 10,
            "Adj Close": [100] * 10,
            "Volume": [1000000] * 10,
        })
        mock_download.return_value = mock_df
        
        result = fetcher._fetch_from_yfinance("TEST", "2020-01-01", "2020-01-31")
        
        assert result is not None
        assert len(result) == 10
        assert "Date" in result.columns
    
    @patch("yfinance.download")
    def test_fetch_from_yfinance_empty(self, mock_download, fetcher):
        """测试 yfinance 返回空数据"""
        mock_download.return_value = pd.DataFrame()
        
        result = fetcher._fetch_from_yfinance("TEST", "2020-01-01", "2020-01-31")
        
        assert result is None
    
    @patch("yfinance.download")
    def test_fetch_from_yfinance_error(self, mock_download, fetcher):
        """测试 yfinance 获取错误"""
        mock_download.side_effect = Exception("Network error")
        
        result = fetcher._fetch_from_yfinance("TEST", "2020-01-01", "2020-01-31", max_retries=1)
        
        assert result is None
    
    def test_fetch_incremental(self, fetcher, sample_data):
        """测试增量获取数据"""
        ticker = "TEST"
        
        # 保存初始数据
        fetcher._save_to_cache(sample_data, ticker)
        
        # 模拟新数据（从第100天开始）
        new_dates = pd.date_range("2020-05-01", periods=10, freq="B")
        new_data = pd.DataFrame({
            "Date": new_dates.strftime("%Y-%m-%d"),
            "Open": 100 + np.random.randn(10).cumsum(),
            "High": 105 + np.random.randn(10).cumsum(),
            "Low": 95 + np.random.randn(10).cumsum(),
            "Close": 100 + np.random.randn(10).cumsum(),
            "Adj Close": 100 + np.random.randn(10).cumsum(),
            "Volume": np.random.randint(1000000, 10000000, 10),
        })
        
        with patch.object(fetcher, "_fetch_from_yfinance", return_value=new_data):
            result = fetcher._fetch_incremental(
                ticker,
                sample_data["Date"].iloc[-1],
                "2020-05-31"
            )
        
        assert result is not None
        assert len(result) > 0
    
    def test_fetch_multiple(self, fetcher):
        """测试获取多个股票数据"""
        tickers = ["SPY", "TLT"]
        
        with patch.object(fetcher, "fetch") as mock_fetch:
            mock_fetch.side_effect = lambda t, **kwargs: pd.DataFrame({
                "Date": ["2020-01-01"],
                "Open": [100],
                "High": [105],
                "Low": [95],
                "Close": [100],
                "Adj Close": [100],
                "Volume": [1000000],
            })
            
            result = fetcher.fetch_multiple(tickers)
        
        assert len(result) == len(tickers)


class TestDataFetcherIntegration:
    """DataFetcher 集成测试（需要网络连接）"""
    
    @pytest.fixture
    def fetcher(self, tmp_path):
        return DataFetcher(cache_dir=tmp_path)
    
    @pytest.mark.integration
    def test_fetch_real_data(self, fetcher):
        """测试获取真实数据（如果网络可用）"""
        # 这个测试可能失败，如果网络不可用
        result = fetcher.fetch("SPY", "2020-01-01", "2020-01-31")
        
        # 如果成功，数据应该不为空
        if result is not None:
            assert len(result) > 0
            assert "Date" in result.columns
            assert "Adj Close" in result.columns
    
    @pytest.mark.integration
    def test_cache_roundtrip(self, tmp_path):
        """测试缓存往返"""
        fetcher = DataFetcher(cache_dir=tmp_path)
        
        # 获取数据
        result = fetcher.fetch("SPY", "2020-01-01", "2020-01-31")
        
        if result is not None:
            # 检查缓存文件是否存在
            cache_path = tmp_path / "SPY.csv"
            assert cache_path.exists()
            
            # 从缓存加载
            cached = fetcher._load_from_cache("SPY")
            assert cached is not None
            assert len(cached) == len(result)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])