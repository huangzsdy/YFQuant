"""
数据库管理模块

功能：
- 创建和管理 quant.db SQLite 数据库
- 将 data/ 目录下的 CSV 文件导入到数据库表
- 提供日期范围查询功能
"""

import os
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Any

import pandas as pd


# ============================================================
# 配置参数
# ============================================================

# 数据库路径
DATABASE_PATH: Path = Path("quant.db")

# 数据目录
DATA_DIR: Path = Path("data")

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger: logging.Logger = logging.getLogger(__name__)


# ============================================================
# 数据库连接管理
# ============================================================

class QuantDatabase:
    """
    量化数据库管理类
    
    提供数据库创建、CSV 导入、数据查询等功能。
    """
    
    def __init__(self, db_path: Path = DATABASE_PATH) -> None:
        """
        初始化数据库连接。
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path: Path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
    
    def _connect(self) -> None:
        """建立数据库连接"""
        self.conn = sqlite3.connect(self.db_path)
        logger.info(f"已连接到数据库: {self.db_path.absolute()}")
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("数据库连接已关闭")
    
    def __enter__(self) -> "QuantDatabase":
        """上下文管理器入口"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """上下文管理器出口"""
        self.close()
    
    # ============================================================
    # 数据库操作
    # ============================================================
    
    def create_table_from_csv(
        self,
        csv_path: Path,
        table_name: Optional[str] = None,
        if_exists: str = "replace",
    ) -> int:
        """
        从 CSV 文件创建数据库表。
        
        Args:
            csv_path: CSV 文件路径
            table_name: 表名（默认为 CSV 文件名不含扩展名）
            if_exists: 如果表已存在的处理方式 ('replace', 'append', 'fail')
        
        Returns:
            导入的行数
        """
        if table_name is None:
            table_name = csv_path.stem
        
        # 验证文件存在
        if not csv_path.exists():
            raise FileNotFoundError(f"CSV 文件不存在: {csv_path}")
        
        # 读取 CSV 文件
        df: pd.DataFrame = pd.read_csv(csv_path, parse_dates=["Date"])
        
        # 导入到数据库
        df.to_sql(
            name=table_name,
            con=self.conn,
            if_exists=if_exists,
            index=False,
        )
        
        row_count: int = len(df)
        logger.info(f"已导入 {table_name}: {row_count} 行")
        
        return row_count
    
    def import_all_csv(self, data_dir: Path = DATA_DIR) -> dict:
        """
        将数据目录下所有 CSV 文件导入到数据库。
        
        Args:
            data_dir: 数据目录路径
        
        Returns:
            导入统计字典 {表名: 行数}
        """
        if not data_dir.exists():
            raise FileNotFoundError(f"数据目录不存在: {data_dir}")
        
        # 获取所有 CSV 文件
        csv_files: List[Path] = list(data_dir.glob("*.csv"))
        
        if not csv_files:
            logger.warning(f"数据目录为空: {data_dir}")
            return {}
        
        logger.info(f"找到 {len(csv_files)} 个 CSV 文件")
        
        # 导入每个 CSV 文件
        results: dict = {}
        for csv_file in csv_files:
            try:
                row_count: int = self.create_table_from_csv(csv_file)
                results[csv_file.stem] = row_count
            except Exception as e:
                logger.error(f"导入 {csv_file.name} 失败: {e}")
                results[csv_file.stem] = -1
        
        return results
    
    def get_table_names(self) -> List[str]:
        """
        获取所有表名。
        
        Returns:
            表名列表
        """
        cursor: sqlite3.Cursor = self.conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables: List[Tuple[str]] = cursor.fetchall()
        return [table[0] for table in tables]
    
    def get_table_info(self, table_name: str) -> List[dict]:
        """
        获取表结构信息。
        
        Args:
            table_name: 表名
        
        Returns:
            列信息列表
        """
        cursor: sqlite3.Cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns: List[Tuple] = cursor.fetchall()
        return [
            {
                "cid": col[0],
                "name": col[1],
                "type": col[2],
                "notnull": col[3],
                "default": col[4],
                "pk": col[5],
            }
            for col in columns
        ]
    
    # ============================================================
    # 数据查询
    # ============================================================
    
    def query(
        self,
        sql: str,
        params: Optional[Tuple[Any, ...]] = None,
    ) -> pd.DataFrame:
        """
        执行 SQL 查询。
        
        Args:
            sql: SQL 查询语句
            params: 查询参数（元组）
        
        Returns:
            查询结果 DataFrame
        """
        if params:
            df: pd.DataFrame = pd.read_sql_query(sql, self.conn, params=params)
        else:
            df = pd.read_sql_query(sql, self.conn)
        
        logger.debug(f"查询返回 {len(df)} 行")
        return df
    
    def query_by_date_range(
        self,
        table_name: str,
        start_date: str,
        end_date: str,
        columns: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        查询指定日期范围内的数据。
        
        Args:
            table_name: 表名
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            columns: 要查询的列（None 表示所有列）
        
        Returns:
            查询结果 DataFrame
        """
        if columns:
            cols_str: str = ", ".join(columns)
        else:
            cols_str = "*"
        
        sql: str = f"""
            SELECT {cols_str}
            FROM {table_name}
            WHERE Date >= ? AND Date <= ?
            ORDER BY Date
        """
        
        df: pd.DataFrame = pd.read_sql_query(
            sql,
            self.conn,
            params=(start_date, end_date),
        )
        
        logger.info(
            f"查询 {table_name}: {start_date} ~ {end_date}, "
            f"返回 {len(df)} 行"
        )
        
        return df
    
    def query_latest(self, table_name: str, n: int = 1) -> pd.DataFrame:
        """
        查询最新的 n 条记录。
        
        Args:
            table_name: 表名
            n: 返回记录数
        
        Returns:
            查询结果 DataFrame
        """
        sql: str = f"""
            SELECT *
            FROM {table_name}
            ORDER BY Date DESC
            LIMIT ?
        """
        
        df: pd.DataFrame = pd.read_sql_query(sql, self.conn, params=(n,))
        return df
    
    def query_signal(self, date: str) -> dict:
        """
        查询指定日期的交易信号（从回测结果表）。
        
        Args:
            date: 日期 (YYYY-MM-DD)
        
        Returns:
            包含日期和信号的字典
        """
        try:
            df: pd.DataFrame = self.query_by_date_range(
                "backtest_results",
                date,
                date,
            )
            
            if df.empty:
                return {"date": date, "signal": None, "message": "无数据"}
            
            # 获取当日信号
            signal: int = int(df["Signal"].iloc[0])
            spy_price: float = df["SPY_Price"].iloc[0]
            tlt_price: float = df["TLT_Price"].iloc[0]
            
            if signal == 1:
                action: str = "买入 SPY"
            else:
                action = "买入 TLT"
            
            return {
                "date": date,
                "signal": signal,
                "action": action,
                "spy_price": spy_price,
                "tlt_price": tlt_price,
                "message": f"建议{action}",
            }
        except Exception as e:
            logger.error(f"查询信号失败: {e}")
            return {"date": date, "signal": None, "message": str(e)}


# ============================================================
# 主函数
# ============================================================

def main() -> int:
    """
    主函数：导入所有 CSV 到数据库。
    
    Returns:
        成功返回 0，失败返回 1
    """
    logger.info("=" * 60)
    logger.info("量化数据库导入工具")
    logger.info("=" * 60)
    
    try:
        with QuantDatabase() as db:
            # 导入所有 CSV
            results: dict = db.import_all_csv()
            
            # 打印统计
            logger.info("-" * 60)
            logger.info("导入统计:")
            for table_name, row_count in results.items():
                status: str = "成功" if row_count > 0 else "失败"
                logger.info(f"  {table_name}: {row_count} 行 ({status})")
            
            # 显示所有表
            tables: List[str] = db.get_table_names()
            logger.info(f"\n数据库中共 {len(tables)} 个表: {tables}")
        
        logger.info("=" * 60)
        logger.info("导入完成!")
        logger.info("=" * 60)
        
        return 0
        
    except Exception as e:
        logger.error(f"导入失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
