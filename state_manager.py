"""在庫監視の状態管理（JSON読み書き）"""
import json
import os
import shutil


class StateManager:
    def __init__(self, filepath: str):
        self.filepath = filepath

    def load(self) -> dict:
        """前回の状態をJSONファイルから読み込む"""
        if not os.path.exists(self.filepath):
            return {"keywords": {}, "last_run": None}

        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[状態] {self.filepath} 読み込み失敗: {e}")
            return {"keywords": {}, "last_run": None}

    def save(self, state: dict) -> None:
        """現在の状態をJSONファイルに保存（バックアップ付き）"""
        backup_path = self.filepath + ".bak"

        # バックアップ作成
        if os.path.exists(self.filepath):
            shutil.copy2(self.filepath, backup_path)

        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            print(f"[状態] {self.filepath} に保存完了")
        except Exception:
            # 失敗時はバックアップから復元
            if os.path.exists(backup_path):
                shutil.copy2(backup_path, self.filepath)
            raise
