import flet as ft
import json
import os
from datetime import datetime

class HistoryManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.history_key = "tenji_pfab_history_v1"
        self.config_key = "tenji_pfab_config_v1"
        
        # エラー時のフォールバック用メモリキャッシュ
        self._mem_config = {}
        self._mem_history = []
        
        # 動作モード: 'client', 'file', 'memory'
        # 初期状態は 'client' だが、エラー発生時に自動的にダウングレードする
        self._storage_mode = 'client' 
        self._local_file_path = os.path.join(os.path.expanduser("~"), ".tenji_pfab_data.json")

    # --- 内部メソッド ---

    def _load_from_file(self):
        """ローカルファイルからJSONを読み込む"""
        try:
            if os.path.exists(self._local_file_path):
                with open(self._local_file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except:
            pass
        return {}

    def _save_to_file(self, data):
        """ローカルファイルへJSONを書き込む"""
        try:
            with open(self._local_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            return True
        except:
            return False

    def _switch_to_fallback(self):
        """Client Storage失敗時のフォールバック処理"""
        # まずファイル保存を試す
        test_data = {"config": self._mem_config, "history": self._mem_history}
        if self._save_to_file(test_data):
            self._storage_mode = 'file'
            print("Switched to Local File storage.")
        else:
            self._storage_mode = 'memory'
            print("Switched to Memory-only storage.")

    def _safe_get(self, key, default_value):
        """安全な値の取得（モードに応じた取得）"""
        
        # 1. Memory Mode (最低限動作)
        if self._storage_mode == 'memory':
            if key == self.config_key: return self._mem_config or default_value
            if key == self.history_key: return self._mem_history or default_value

        # 2. Local File Mode
        if self._storage_mode == 'file':
            data = self._load_from_file()
            return data.get(key, default_value)

        # 3. Client Storage Mode (Default)
        try:
            if self.page.client_storage.contains_key(key):
                val = self.page.client_storage.get(key)
                # メモリキャッシュも更新しておく
                if key == self.config_key: self._mem_config = val
                if key == self.history_key: self._mem_history = val
                return val
            return default_value
        except Exception as e:
            print(f"Client Storage READ Error ({key}): {e}, switching mode.")
            self._switch_to_fallback()
            # 再帰的に呼び出してフォールバック後の値を取得
            return self._safe_get(key, default_value)

    def _safe_set(self, key, value):
        """安全な値の保存（モードに応じた保存）"""
        
        # 常にメモリキャッシュは更新
        if key == self.config_key: self._mem_config = value
        if key == self.history_key: self._mem_history = value

        if self._storage_mode == 'memory':
            return

        if self._storage_mode == 'file':
            # ファイルモード時は全データをマージして保存
            current_data = self._load_from_file()
            current_data[key] = value
            if not self._save_to_file(current_data):
                print("File Save Error, switching to memory mode.")
                self._storage_mode = 'memory'
            return

        try:
            self.page.client_storage.set(key, value)
        except Exception as e:
            print(f"Client Storage WRITE Error ({key}): {e}, switching mode.")
            self._switch_to_fallback()
            # フォールバック先に保存を試みる
            self._safe_set(key, value)

    # --- 公開メソッド（履歴） ---

    def get_history(self):
        data = self._safe_get(self.history_key, [])
        if not isinstance(data, list): return []
        return data

    def add_entry(self, text, current_settings):
        history = self.get_history()
        limit = self.get_history_limit()
        
        entry = {
            "text": text,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "max_chars_per_line": current_settings.get("max_chars_per_line", 10),
            "max_lines_per_plate": current_settings.get("max_lines_per_plate", 3),
            "plate_thickness": current_settings.get("plate_thickness", 1.0),
        }
        
        # 重複排除
        if history:
            last = history[0]
            if (last.get("text") == text and 
                last.get("max_chars_per_line") == entry["max_chars_per_line"] and
                last.get("max_lines_per_plate") == entry["max_lines_per_plate"]):
                last["timestamp"] = entry["timestamp"]
                self._safe_set(self.history_key, history)
                return

        history.insert(0, entry)
        if len(history) > limit:
            history = history[:limit]
            
        self._safe_set(self.history_key, history)

    def clear_history(self):
        self._safe_set(self.history_key, [])

    def get_history_limit(self):
        config = self.load_settings()
        return config.get("history_limit", 20)

    def set_history_limit(self, limit):
        self.save_settings({"history_limit": int(limit)})

    # --- 公開メソッド（設定） ---

    def load_settings(self):
        data = self._safe_get(self.config_key, {})
        if not isinstance(data, dict): return {}
        return data

    def save_settings(self, new_settings):
        config = self.load_settings()
        config.update(new_settings)
        self._safe_set(self.config_key, config)