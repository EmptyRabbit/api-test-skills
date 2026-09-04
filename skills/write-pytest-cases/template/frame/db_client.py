import pymysql
from .config import get_db_config


class DBClient:
    """数据库客户端，支持通过 db 名 + SQL 语句执行操作"""

    def __init__(self, db_name):
        """
        Args:
            db_name: config.yaml 中配置的数据库名称
        """
        self.db_name = db_name
        self.config = get_db_config(db_name)

    def _get_connection(self):
        return pymysql.connect(
            host=self.config['host'],
            port=self.config['port'],
            user=self.config['user'],
            password=self.config['password'],
            database=self.config['database'],
            charset=self.config.get('charset', 'utf8mb4'),
            cursorclass=pymysql.cursors.DictCursor
        )

    def query(self, sql, params=None):
        """执行 SELECT 查询，返回所有结果行（list of dict）"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchall()
        finally:
            conn.close()

    def query_one(self, sql, params=None):
        """执行 SELECT 查询，返回第一条结果行（dict），无结果时返回 None"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                return cursor.fetchone()
        finally:
            conn.close()

    def execute(self, sql, params=None):
        """执行 SQL 语句（INSERT/UPDATE/DELETE），返回受影响行数"""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                affected_rows = cursor.execute(sql, params)
                conn.commit()
                return affected_rows
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
