import json
import os
import hashlib

class AuthManager:
    def __init__(self, db_path="users.json"):
        self.db_path = db_path
        self.users = self._load_users()

    def _load_users(self):
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {"users": {}}
        return {"users": {}}

    def _save_users(self):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.users, f, ensure_ascii=False, indent=2)

    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def register(self, username, password, hint, hint_answer):
        if username in self.users.get("users", {}):
            return False, "用户名已存在"
        
        self.users.setdefault("users", {})[username] = {
            "password_hash": self._hash_password(password),
            "hint": hint,
            "hint_answer_hash": self._hash_password(hint_answer.lower())
        }
        self._save_users()
        return True, "注册成功"

    def login(self, username, password):
        user = self.users.get("users", {}).get(username)
        if not user:
            return False, "用户不存在"
        if user["password_hash"] != self._hash_password(password):
            return False, "密码错误"
        return True, "登录成功"

    def reset_password(self, username, hint_answer, new_password):
        user = self.users.get("users", {}).get(username)
        if not user:
            return False, "用户不存在"
        if user["hint_answer_hash"] != self._hash_password(hint_answer.lower()):
            return False, "安全问题答案错误"
        user["password_hash"] = self._hash_password(new_password)
        self._save_users()
        return True, "密码重置成功"

    def get_hint(self, username):
        user = self.users.get("users", {}).get(username)
        return user["hint"] if user else None
