import flet as ft
from datetime import datetime

class HistoryManager:
    def __init__(self, page: ft.Page):
        self.page = page
        self.history_key = "tenji_pfab_history_v1"
        self.config_key = "tenji_pfab_config_v1"
        
    def get_history(self):
        """履歴リストを取得"""
        if self.page.client_storage.contains_key(self.history_key):
            return self.page.client_storage.get(self.history_key)
        return []

    def add_entry(self, text, current_settings):
        """履歴を追加"""
        history = self.get_history()
        limit = self.get_history_limit()
        
        # 新しいエントリーを作成
        entry = {
            "text": text,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            # その時の設定のスナップショットを保存
            "max_chars_per_line": current_settings["max_chars_per_line"],
            "max_lines_per_plate": current_settings["max_lines_per_plate"],
            "plate_thickness": current_settings["plate_thickness"],
            # 将来的な拡張用
            "scale": current_settings.get("scale", 1.0)
        }
        
        # 重複チェック（直近と同じ内容なら日時だけ更新して先頭へ）
        if history and history[0]["text"] == text and \
           history[0]["max_chars_per_line"] == entry["max_chars_per_line"] and \
           history[0]["max_lines_per_plate"] == entry["max_lines_per_plate"]:
            history.pop(0)
        
        # 先頭に追加
        history.insert(0, entry)
        
        # 制限を超えたら古いものを削除
        if len(history) > limit:
            history = history[:limit]
            
        self.page.client_storage.set(self.history_key, history)

    def clear_history(self):
        """履歴を全削除"""
        self.page.client_storage.remove(self.history_key)

    def get_history_limit(self):
        """履歴の最大保存件数を取得"""
        if self.page.client_storage.contains_key(self.config_key):
            config = self.page.client_storage.get(self.config_key)
            return config.get("history_limit", 20)
        return 20

    def set_history_limit(self, limit):
        """履歴の最大保存件数を設定"""
        config = {}
        if self.page.client_storage.contains_key(self.config_key):
            config = self.page.client_storage.get(self.config_key)
        
        config["history_limit"] = int(limit)
        self.page.client_storage.set(self.config_key, config)
