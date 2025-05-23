import sqlite3
import json
import os
from datetime import datetime, timedelta
import hashlib
import threading
import time
import shutil
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path="ai_grading.db", pool_size=5, timeout=30):
        self.db_path = db_path
        self.pool_size = pool_size
        self.timeout = timeout
        self._connection_pool = []
        self._lock = threading.Lock()
        self._thread_local = threading.local()
        self._init_db()
        self._init_connection_pool()

    def _init_connection_pool(self):
        """初始化数据库连接池"""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(self.db_path, timeout=self.timeout)
            conn.row_factory = sqlite3.Row
            self._connection_pool.append(conn)

    def _get_connection(self):
        """从连接池获取连接，使用线程本地存储"""
        if not hasattr(self._thread_local, 'connection'):
            with self._lock:
                if not self._connection_pool:
                    # 如果连接池为空，创建新连接
                    conn = sqlite3.connect(self.db_path, timeout=self.timeout)
                    conn.row_factory = sqlite3.Row
                else:
                    conn = self._connection_pool.pop()
            self._thread_local.connection = conn
        return self._thread_local.connection

    def _return_connection(self, conn):
        """归还连接到连接池"""
        if hasattr(self._thread_local, 'connection'):
            with self._lock:
                if len(self._connection_pool) < self.pool_size:
                    self._connection_pool.append(conn)
                else:
                    conn.close()
            delattr(self._thread_local, 'connection')

    def backup_database(self, backup_path=None):
        """备份数据库"""
        try:
            if backup_path is None:
                # 创建备份目录
                backup_dir = Path("backups")
                backup_dir.mkdir(exist_ok=True)
                # 生成备份文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"ai_grading_{timestamp}.db"
            
            # 创建备份
            shutil.copy2(self.db_path, backup_path)
            return True, f"数据库备份成功: {backup_path}"
        except Exception as e:
            return False, f"数据库备份失败: {str(e)}"

    def restore_database(self, backup_path):
        """从备份恢复数据库"""
        try:
            if not os.path.exists(backup_path):
                return False, "备份文件不存在"
            
            # 关闭所有连接
            with self._lock:
                for conn in self._connection_pool:
                    conn.close()
                self._connection_pool.clear()
            
            # 恢复数据库
            shutil.copy2(backup_path, self.db_path)
            
            # 重新初始化连接池
            self._init_connection_pool()
            return True, "数据库恢复成功"
        except Exception as e:
            return False, f"数据库恢复失败: {str(e)}"

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()

            # 创建用户表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                hint TEXT NOT NULL,
                hint_answer_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            ''')

            # 创建项目表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                project_name TEXT NOT NULL,
                project_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (username) REFERENCES users(username),
                UNIQUE(username, project_name)
            )
            ''')

            # 创建会话表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                FOREIGN KEY (username) REFERENCES users(username)
            )
            ''')

            conn.commit()
        finally:
            self._return_connection(conn)

    def _hash_password(self, password):
        """哈希密码"""
        return hashlib.sha256(password.encode()).hexdigest()

    def register_user(self, username, password, hint, hint_answer):
        """注册新用户"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # 检查用户名是否已存在
            cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return False, "用户名已存在"

            # 插入新用户
            cursor.execute(
                "INSERT INTO users (username, password_hash, hint, hint_answer_hash) VALUES (?, ?, ?, ?)",
                (username, self._hash_password(password), hint, self._hash_password(hint_answer.lower()))
            )
            
            conn.commit()
            return True, "注册成功"
        except Exception as e:
            return False, f"注册失败: {str(e)}"
        finally:
            self._return_connection(conn)

    def verify_user(self, username, password):
        """验证用户登录"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT password_hash FROM users WHERE username = ?",
                (username,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False, "用户不存在"
            
            if result[0] != self._hash_password(password):
                return False, "密码错误"
            
            return True, "登录成功"
        finally:
            self._return_connection(conn)

    def get_hint(self, username):
        """获取用户的安全问题"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("SELECT hint FROM users WHERE username = ?", (username,))
            result = cursor.fetchone()
            
            return result[0] if result else None
        finally:
            self._return_connection(conn)

    def verify_hint_answer(self, username, hint_answer):
        """验证安全问题答案"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT hint_answer_hash FROM users WHERE username = ?",
                (username,)
            )
            result = cursor.fetchone()
            
            if not result:
                return False
            
            return result[0] == self._hash_password(hint_answer.lower())
        finally:
            self._return_connection(conn)

    def reset_password(self, username, new_password):
        """重置用户密码"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (self._hash_password(new_password), username)
            )
            
            conn.commit()
            return True, "密码重置成功"
        except Exception as e:
            return False, f"密码重置失败: {str(e)}"
        finally:
            self._return_connection(conn)

    def save_project(self, username, project_name, project_data):
        """保存项目数据"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # 将项目数据转换为JSON字符串
            project_json = json.dumps(project_data, ensure_ascii=False)
            
            # 检查项目是否已存在
            cursor.execute(
                "SELECT id FROM projects WHERE username = ? AND project_name = ?",
                (username, project_name)
            )
            existing_project = cursor.fetchone()
            
            if existing_project:
                # 更新现有项目
                cursor.execute(
                    """
                    UPDATE projects 
                    SET project_data = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE username = ? AND project_name = ?
                    """,
                    (project_json, username, project_name)
                )
            else:
                # 创建新项目
                cursor.execute(
                    """
                    INSERT INTO projects (username, project_name, project_data)
                    VALUES (?, ?, ?)
                    """,
                    (username, project_name, project_json)
                )
            
            conn.commit()
            return True, "项目保存成功"
        except Exception as e:
            return False, f"项目保存失败: {str(e)}"
        finally:
            self._return_connection(conn)

    def get_project(self, username, project_name):
        """获取项目数据"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT project_data FROM projects WHERE username = ? AND project_name = ?",
                (username, project_name)
            )
            result = cursor.fetchone()
            
            if result:
                return json.loads(result[0])
            return None
        finally:
            self._return_connection(conn)

    def get_user_projects(self, username):
        """获取用户的所有项目"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT project_name, project_data FROM projects WHERE username = ?",
                (username,)
            )
            results = cursor.fetchall()
            
            return {name: json.loads(data) for name, data in results}
        finally:
            self._return_connection(conn)

    def delete_project(self, username, project_name):
        """删除项目"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute(
                "DELETE FROM projects WHERE username = ? AND project_name = ?",
                (username, project_name)
            )
            
            conn.commit()
            return True, "项目删除成功"
        except Exception as e:
            return False, f"项目删除失败: {str(e)}"
        finally:
            self._return_connection(conn)

    def create_session(self, username, session_id, expires_in_days=7):
        """创建用户会话"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            # 删除该用户的旧会话
            cursor.execute("DELETE FROM sessions WHERE username = ?", (username,))
            
            # 创建新会话
            expires_at = datetime.now() + timedelta(days=expires_in_days)
            cursor.execute(
                "INSERT INTO sessions (session_id, username, expires_at) VALUES (?, ?, ?)",
                (session_id, username, expires_at)
            )
            
            conn.commit()
            return True
        finally:
            self._return_connection(conn)

    def verify_session(self, session_id):
        """验证会话是否有效"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute(
                """
                SELECT username FROM sessions 
                WHERE session_id = ? AND expires_at > CURRENT_TIMESTAMP
                """,
                (session_id,)
            )
            result = cursor.fetchone()
            
            return result[0] if result else None
        finally:
            self._return_connection(conn)

    def delete_session(self, session_id):
        """删除会话"""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
            conn.commit()
        finally:
            self._return_connection(conn)

    def __del__(self):
        """清理所有连接"""
        with self._lock:
            for conn in self._connection_pool:
                try:
                    conn.close()
                except:
                    pass
            self._connection_pool.clear()
            if hasattr(self._thread_local, 'connection'):
                try:
                    self._thread_local.connection.close()
                except:
                    pass

# 创建数据库管理器实例
db = DatabaseManager(pool_size=10, timeout=60)  # 自定义连接池大小和超时时间

# 备份数据库
success, message = db.backup_database()
print(message)

# 从备份恢复
success, message = db.restore_database("backups/ai_grading_20240321_123456.db")
print(message)
