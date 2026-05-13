"""
Streamlit Dashboard

功能：
- 策略选择
- 参数输入
- 运行回测
- 显示权益曲线（组合价值 vs 基准买入持有）
- 显示绩效指标表格
"""

import sys
from pathlib import Path

# 添加 src 目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, date

# 配置 matplotlib 中文字体（解决 Windows 上中文乱码问题）
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 尝试获取可用的中文字体
try:
    from matplotlib.font_manager import FontProperties
    # 查找中文字体
    for font_name in ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS']:
        try:
            font = FontProperties(fname='C:/Windows/Fonts/' + font_name + '.ttf')
            matplotlib.rcParams['font.family'] = font_name
            break
        except:
            continue
except:
    pass

# 导入项目模块
from data.fetcher import DataFetcher
from backtest.engine import BacktestEngine
from strategies import get_strategy, STRATEGIES
from analytics.metrics import calculate_all_metrics, print_metrics


# ============================================================
# 页面配置
# ============================================================

st.set_page_config(
    page_title="YFQuant 回测系统",
    page_icon="📈",
    layout="wide",
)


# ============================================================
# 辅助函数
# ============================================================

@st.cache_data(ttl=3600)
def load_data(tickers: list, start_date: str, end_date: str) -> dict:
    """
    加载数据（带缓存）
    
    Args:
        tickers: 股票代码列表
        start_date: 开始日期
        end_date: 结束日期
    
    Returns:
        {ticker: DataFrame} 字典
    """
    fetcher = DataFetcher()
    return fetcher.fetch_multiple(tickers, start_date, end_date)


def run_backtest(
    strategy_name: str,
    data: dict,
    initial_capital: float,
    **strategy_params,
) -> dict:
    """
    运行回测
    
    Args:
        strategy_name: 策略名称
        data: 数据字典
        initial_capital: 初始资金
        **strategy_params: 策略参数
    
    Returns:
        回测结果字典
    """
    # 合并数据
    df_list = []
    for ticker, df in data.items():
        df_copy = df.copy()
        df_copy["Ticker"] = ticker
        df_list.append(df_copy)
    
    # 获取第一个资产的价格作为主价格
    first_ticker = list(data.keys())[0]
    prices_df = data[first_ticker].copy()
    
    # 添加其他资产价格
    if len(data) > 1:
        for ticker in list(data.keys())[1:]:
            prices_df[ticker] = data[ticker]["Adj Close"].values
    
    # 生成信号
    strategy = get_strategy(strategy_name, **strategy_params)
    signals = strategy.generate_signals(prices_df)
    
    # 运行回测
    engine = BacktestEngine(
        initial_capital=initial_capital,
        commission_per_share=0.005,
        slippage_rate=0.0001,
        fractional_shares=True,
    )
    
    # 准备回测数据
    backtest_df = prices_df[["Date", "Adj Close"]].copy()
    backtest_df = backtest_df.rename(columns={"Adj Close": "Close"})
    
    # 运行回测
    results = engine.run_backtest(backtest_df, signals)
    
    # 添加基准收益
    results["Benchmark_Return"] = backtest_df["Close"].pct_change()
    results["Benchmark_Cumulative"] = (1 + results["Benchmark_Return"]).cumprod() - 1
    
    # 计算指标
    metrics = calculate_all_metrics(
        portfolio_value=results["Portfolio_Value"],
        returns=results["Strategy_Return"],
        trades=results["Trade_Value"] if "Trade_Value" in results.columns else None,
    )
    
    return {
        "results": results,
        "metrics": metrics,
        "strategy": strategy,
    }


# ============================================================
# 页面布局
# ============================================================

# 标题
st.title("📈 YFQuant 量化回测系统")
st.markdown("---")

# 侧边栏：参数配置
with st.sidebar:
    st.header("⚙️ 配置")
    
    # 策略选择
    strategy_name = st.selectbox(
        "选择策略",
        options=list(STRATEGIES.keys()),
        index=0,
    )
    
    st.markdown("### 策略参数")
    
    # 根据策略显示不同参数
    if strategy_name == "DualMomentum":
        momentum_period = st.slider("动量周期（月）", 1, 24, 12)
        risk_free_rate = st.slider("无风险利率（%）", 0.0, 10.0, 2.0) / 100
        strategy_params = {
            "momentum_period": momentum_period,
            "risk_free_rate": risk_free_rate,
        }
    elif strategy_name == "TrendFollowingMA":
        ma_window = st.slider("均线周期（日）", 50, 300, 200)
        strategy_params = {"ma_window": ma_window}
    elif strategy_name == "MeanReversionRSI":
        rsi_period = st.slider("RSI 周期", 5, 30, 14)
        oversold = st.slider("超卖阈值", 10, 40, 30)
        overbought = st.slider("超买阈值", 60, 90, 70)
        strategy_params = {
            "rsi_period": rsi_period,
            "oversold_threshold": oversold,
            "overbought_threshold": overbought,
        }
    
    st.markdown("### 回测参数")
    
    # 股票选择
    tickers_input = st.text_input(
        "股票代码（逗号分隔）",
        value="SPY,TLT",
        help="例如: SPY,TLT 或 AAPL,MSFT",
    )
    
    # 日期范围
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "开始日期",
            value=datetime(2015, 1, 1),
        )
    with col2:
        end_date = st.date_input(
            "结束日期",
            value=date.today(),
        )
    
    # 初始资金
    initial_capital = st.number_input(
        "初始资金（美元）",
        min_value=1000,
        max_value=10000000,
        value=10000,
        step=1000,
    )
    
    # 运行按钮
    run_button = st.button("🚀 运行回测", type="primary", use_container_width=True)

# 主内容区
if run_button:
    # 解析股票代码
    tickers = [t.strip().upper() for t in tickers_input.split(",")]
    
    # 转换日期
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = end_date.strftime("%Y-%m-%d")
    
    # 显示加载状态
    with st.spinner(f"正在加载 {tickers} 数据..."):
        try:
            data = load_data(tickers, start_str, end_str)
            
            if not data:
                st.error("数据加载失败，请检查网络连接和股票代码")
            else:
                with st.spinner("正在运行回测..."):
                    result = run_backtest(
                        strategy_name=strategy_name,
                        data=data,
                        initial_capital=initial_capital,
                        **strategy_params,
                    )
                
                # 显示结果
                st.success("回测完成！")
                
                # 绩效指标
                st.subheader("📊 绩效指标")
                
                metrics = result["metrics"]
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "总收益率",
                        f"{metrics['total_return']*100:.2f}%",
                    )
                with col2:
                    st.metric(
                        "年化收益率 (CAGR)",
                        f"{metrics['cagr']*100:.2f}%",
                    )
                with col3:
                    st.metric(
                        "夏普比率",
                        f"{metrics['sharpe_ratio']:.2f}",
                    )
                with col4:
                    st.metric(
                        "最大回撤",
                        f"{metrics['max_drawdown']*100:.2f}%",
                    )
                
                col5, col6, col7, col8 = st.columns(4)
                
                with col5:
                    st.metric(
                        "索提诺比率",
                        f"{metrics['sortino_ratio']:.2f}",
                    )
                with col6:
                    st.metric(
                        "Calmar 比率",
                        f"{metrics['calmar_ratio']:.2f}",
                    )
                with col7:
                    st.metric(
                        "胜率",
                        f"{metrics['win_rate']*100:.2f}%",
                    )
                with col8:
                    st.metric(
                        "年化换手率",
                        f"{metrics['turnover_rate']*100:.2f}%",
                    )
                
                st.markdown("---")
                
                # 权益曲线图
                st.subheader("📈 策略 vs 买入持有 对比图")
                
                results_df = result["results"]
                
                fig, ax = plt.subplots(figsize=(12, 6))
                
                # 转换日期
                if "Date" in results_df.columns:
                    dates = pd.to_datetime(results_df["Date"])
                else:
                    dates = results_df.index
                
                # 基准收益（买入持有）- 先画，因为是参考线
                ax.plot(
                    dates,
                    (1 + results_df["Benchmark_Cumulative"].fillna(0)) * 100,
                    label="Buy & Hold (Benchmark)",
                    linewidth=2,
                    color="gray",
                    linestyle="--",
                )
                
                # 策略收益
                ax.plot(
                    dates,
                    (1 + results_df["Strategy_Cumulative"].fillna(0)) * 100,
                    label=f"{strategy_name} Strategy",
                    linewidth=2,
                    color="blue",
                )
                
                ax.set_title(f"Portfolio Value Over Time: {strategy_name} vs Buy&Hold", fontsize=14, fontweight="bold")
                ax.set_xlabel("Date")
                ax.set_ylabel("Portfolio Value (Initial = 100)")
                ax.legend(loc="upper left", fontsize=10)
                ax.grid(True, alpha=0.3)
                
                # 格式化日期
                fig.autofmt_xdate()
                
                st.pyplot(fig)
                
                st.markdown("---")
                
                # 回撤图
                st.subheader("📉 Drawdown Analysis")
                
                fig2, ax2 = plt.subplots(figsize=(12, 4))
                
                # 确保数据长度一致，清理异常值
                drawdown_data = results_df["Drawdown"].fillna(0).clip(upper=0).abs() * 100
                
                # 数据验证：确保 dates 和 drawdown 长度一致
                if len(dates) != len(drawdown_data):
                    logger.warning(f"数据长度不一致: dates={len(dates)}, drawdown={len(drawdown_data)}")
                    min_len = min(len(dates), len(drawdown_data))
                    dates = dates[:min_len]
                    drawdown_data = drawdown_data[:min_len]
                
                # 策略回撤
                ax2.fill_between(
                    dates,
                    drawdown_data,
                    0,
                    alpha=0.4,
                    color="red",
                    label=f"{strategy_name} Drawdown",
                )
                
                # 标记最大回撤点
                if len(drawdown_data) > 0:
                    max_dd_idx = drawdown_data.idxmax() if hasattr(drawdown_data, 'idxmax') else drawdown_data.values.argmax()
                    max_dd_date = dates[max_dd_idx] if hasattr(dates, '__getitem__') else dates.iloc[max_dd_idx]
                    max_dd_value = drawdown_data.max()
                    
                    ax2.annotate(
                        f"Max Drawdown: {max_dd_value:.2f}%",
                        xy=(max_dd_date, max_dd_value),
                        xytext=(max_dd_date, max_dd_value + 5),
                        arrowprops=dict(arrowstyle="->", color="darkred"),
                        fontsize=9,
                        color="darkred",
                    )
                
                ax2.set_title("Strategy Drawdown Over Time", fontsize=14, fontweight="bold")
                ax2.set_xlabel("Date")
                ax2.set_ylabel("Drawdown (%)")
                ax2.legend(loc="lower left", fontsize=10)
                ax2.grid(True, alpha=0.3)
                ax2.set_ylim(bottom=0)  # 设置最小值为0
                
                fig2.autofmt_xdate()
                
                st.pyplot(fig2)
                
                st.markdown("---")
                
                # 详细数据表格
                st.subheader("📋 Daily Backtest Data")
                
                display_df = results_df[[
                    "Date", "Close", "Signal", "Portfolio_Value",
                    "Strategy_Return", "Strategy_Cumulative",
                    "Benchmark_Cumulative", "Drawdown"
                ]].copy()
                
                display_df = display_df.rename(columns={
                    "Date": "Date",
                    "Close": "Close",
                    "Signal": "Signal",
                    "Portfolio_Value": "Portfolio Value",
                    "Strategy_Return": "Daily Return",
                    "Strategy_Cumulative": "Strategy Return",
                    "Benchmark_Cumulative": "Benchmark Return",
                    "Drawdown": "Drawdown",
                })
                
                # 格式化显示
                st.dataframe(
                    display_df.style.format({
                        "Close": "${:.2f}",
                        "Portfolio Value": "${:.2f}",
                        "Daily Return": "{:.4f}",
                        "Strategy Return": "{:.4f}",
                        "Benchmark Return": "{:.4f}",
                        "Drawdown": "{:.4f}",
                    }),
                    height=400,
                )
                
        except Exception as e:
            st.error(f"回测失败: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

else:
    # 初始提示
    st.info("👈 Configure parameters on the left sidebar, then click **Run Backtest** to start")
    
    # 显示项目简介
    st.markdown("""
    ## Project Overview
    
    **YFQuant** is a quantitative trading strategy backtesting system supporting:
    
    ### Strategy Library
    - **DualMomentum**: Dual momentum strategy with monthly rebalancing based on relative and absolute momentum
    - **TrendFollowingMA**: Trend following strategy with daily/weekly rebalancing based on 200-day MA
    - **MeanReversionRSI**: Mean reversion strategy with monthly rebalancing based on RSI indicator
    
    ### Performance Metrics
    - **CAGR**: Compound Annual Growth Rate
    - **Sharpe Ratio**: Risk-adjusted return measure
    - **Sortino Ratio**: Downside risk-adjusted return
    - **Max Drawdown**: Maximum peak-to-trough decline
    - **Calmar Ratio**: CAGR / Max Drawdown
    - **Turnover Rate**: Annual portfolio turnover (important for small accounts)
    
    ### Data Sources
    - **Yahoo Finance**: International market data (US stocks, ETFs, etc.)
    - **AkShare**: China market backup (A-shares, futures, etc.)
    
    ### Backtest Engine Features
    - Vectorized computation with no look-ahead bias
    - Transaction cost model: $0.005/share commission + 0.01% slippage
    - Support for fractional and integer shares
    """)


# ============================================================
# 页脚
# ============================================================

st.markdown("---")
st.markdown(
    "📈 YFQuant 回测系统 | "
    "数据来源: Yahoo Finance, AkShare | "
    "仅供学习和研究使用，不构成投资建议"
)