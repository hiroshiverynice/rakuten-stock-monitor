"""LINE Messaging API プッシュ通知クライアント"""
import requests


class LineNotifier:
    PUSH_URL = "https://api.line.me/v2/bot/message/push"

    def __init__(self, channel_access_token: str, user_id: str):
        self.token = channel_access_token
        self.user_id = user_id
        self.enabled = bool(channel_access_token and user_id)

    def _send_push(self, text: str) -> bool:
        """LINE Messaging APIでプッシュメッセージを送信"""
        if not self.enabled:
            print("[LINE] 未設定のためスキップ")
            return False

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }
        body = {
            "to": self.user_id,
            "messages": [{"type": "text", "text": text}],
        }

        try:
            resp = requests.post(
                self.PUSH_URL, json=body, headers=headers, timeout=30
            )
            resp.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"[LINE] 送信失敗: {e}")
            return False

    def send_stock_alerts(self, transitions: list[dict]) -> int:
        """
        在庫復活通知を送信。
        月200通の無料枠を節約するため、複数商品を1通にまとめる。

        Returns:
            送信したメッセージ数
        """
        if not transitions:
            return 0

        lines = ["🔔 在庫復活アラート 🔔\n"]
        for t in transitions:
            lines.append(
                f"✅ {t['item_name']}\n"
                f"   💰 {t['item_price']:,}円\n"
                f"   🏪 {t['shop_name']}\n"
                f"   🔗 {t['item_url']}\n"
            )

        message = "\n".join(lines)

        # LINEメッセージは5000文字制限
        if len(message) > 4900:
            sent = 0
            chunk = ""
            for line in lines:
                if len(chunk) + len(line) > 4900:
                    if self._send_push(chunk):
                        sent += 1
                    chunk = line
                else:
                    chunk += line
            if chunk and self._send_push(chunk):
                sent += 1
            return sent
        else:
            return 1 if self._send_push(message) else 0
