#!/usr/bin/env python3
"""
楽天市場 在庫監視スクリプト

キーワードで楽天市場を検索し、「売り切れ→在庫あり」の変化を検出してLINE通知を送る。
GitHub Actionsで15分間隔で自動実行される。
"""
import os
import sys
import time
import yaml
from datetime import datetime, timezone

from rakuten_api import RakutenClient
from line_notify import LineNotifier
from state_manager import StateManager


def main():
    # 設定ファイル読み込み
    config_path = os.path.join(os.path.dirname(__file__), "config.yml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 環境変数からAPI キー取得
    rakuten_app_id = os.environ.get("RAKUTEN_APP_ID", "")
    rakuten_access_key = os.environ.get("RAKUTEN_ACCESS_KEY", "")
    line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
    line_user_id = os.environ.get("LINE_USER_ID", "")

    if not rakuten_app_id or not rakuten_access_key:
        print("[エラー] RAKUTEN_APP_ID または RAKUTEN_ACCESS_KEY が設定されていません")
        sys.exit(1)

    # コンポーネント初期化
    rakuten = RakutenClient(application_id=rakuten_app_id, access_key=rakuten_access_key)
    notifier = LineNotifier(
        channel_access_token=line_token,
        user_id=line_user_id,
    )
    state_mgr = StateManager(
        os.path.join(os.path.dirname(__file__), "state.json")
    )
    state = state_mgr.load()

    now = datetime.now(timezone.utc).isoformat()
    transitions = []
    api_delay = config.get("monitor", {}).get("api_delay", 1.5)

    for kw_config in config.get("keywords", []):
        keyword = kw_config["keyword"]
        print(f"[検索] キーワード: {keyword}")

        try:
            items = rakuten.search_with_retry(
                keyword=keyword,
                availability=0,  # 売り切れ含む全商品
                min_price=kw_config.get("min_price"),
                max_price=kw_config.get("max_price"),
            )
        except Exception as e:
            print(f"[エラー] {keyword} の検索に失敗: {e}")
            continue

        print(f"  → {len(items)}件の商品を取得")

        prev_items = state.get("keywords", {}).get(keyword, {}).get("items", {})

        for item in items:
            item_code = item["itemCode"]
            current_avail = item["availability"]
            prev_data = prev_items.get(item_code, {})
            prev_avail = prev_data.get("availability")

            # 「売り切れ(0) → 在庫あり(1)」の遷移を検出
            # 初回(None→1)は通知しない
            if prev_avail == 0 and current_avail == 1:
                transitions.append({
                    "keyword": keyword,
                    "item_name": item["itemName"],
                    "item_price": item["itemPrice"],
                    "item_url": item["itemUrl"],
                    "shop_name": item["shopName"],
                })
                print(f"  ✅ 在庫復活: {item['itemName']}")

            # 状態更新
            state.setdefault("keywords", {}).setdefault(keyword, {}).setdefault("items", {})
            state["keywords"][keyword]["items"][item_code] = {
                "item_name": item["itemName"],
                "item_url": item["itemUrl"],
                "item_price": item["itemPrice"],
                "shop_name": item["shopName"],
                "availability": current_avail,
                "last_seen": now,
                "last_changed": (
                    now if prev_avail != current_avail
                    else prev_data.get("last_changed", now)
                ),
            }

        # キーワード間のAPI遅延
        time.sleep(api_delay)

    # 通知送信
    if transitions:
        sent = notifier.send_stock_alerts(transitions)
        print(f"\n[通知] {len(transitions)}件の在庫復活を検出、{sent}通のLINE通知を送信")
    else:
        print("\n[結果] 在庫変動なし")

    # 状態保存
    state["last_run"] = now
    state_mgr.save(state)


if __name__ == "__main__":
    main()
