import flet as ft
from datetime import datetime

class HistoryManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.history_key = "tenji_pfab_history_v1"
        self.config_key = "tenji_pfab_config_v1"
        
        # エラー時のフォールバック用メモリキャッシュ
        # (ストレージが使えない環境でも、アプリ終了までは設定を保持します)
        self._mem_config = {}
        self._mem_history = []
        self._storage_failed = False

    def _safe_get(self, key, default_value):
        """ストレージから安全に値を取得する"""
        if self._storage_failed:
            if key == self.config_key: return self._mem_config or default_value
            if key == self.history_key: return self._mem_history or default_value
            return default_value

        try:
            if self.page.client_storage.contains_key(key):
                return self.page.client_storage.get(key)
            return default_value
        except Exception as e:
            print(f"Storage READ Error ({key}): {e}")
            # エラーが出たら以降はメモリ運用に切り替え（クラッシュ防止）
            self._storage_failed = True
            return default_value

    def _safe_set(self, key, value):
        """ストレージへ安全に値を保存する"""
        # 常にメモリにも同期しておく
        if key == self.config_key: self._mem_config = value
        if key == self.history_key: self._mem_history = value

        if self._storage_failed:
            return

        try:
            self.page.client_storage.set(key, value)
        except Exception as e:
            print(f"Storage WRITE Error ({key}): {e}")
            self._storage_failed = True

    # --- 履歴関連 ---

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
        
        # 重複排除（先頭と同じなら日時更新のみ）
        if history:
            last = history[0]
            if (last.get("text") == text and 
                last.get("max_chars_per_line") == entry["max_chars_per_line"] and
                last.get("max_lines_per_plate") == entry["max_lines_per_plate"]):
                last["timestamp"] = entry["timestamp"]
                self._safe_set(self.history_key, history)
                return

        # 先頭に追加
        history.insert(0, entry)
        
        # 件数制限
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

    # --- 設定関連 ---

    def load_settings(self):
        data = self._safe_get(self.config_key, {})
        if not isinstance(data, dict): return {}
        return data

    def save_settings(self, new_settings):
        config = self.load_settings()
        config.update(new_settings)
        self._safe_set(self.config_key, config)