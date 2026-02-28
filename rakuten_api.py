"""楽天市場商品検索APIクライアント（2026年新API対応）"""
from __future__ import annotations

import time
import requests

API_ENDPOINT = (
    "https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601"
)


class RakutenClient:
    def __init__(self, application_id: str, access_key: str):
        self.application_id = application_id
        self.access_key = access_key
        self._last_request_time = 0.0

    def _rate_limit(self):
        """1リクエスト/秒のレート制限を守る"""
        elapsed = time.time() - self._last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        self._last_request_time = time.time()

    def search(
        self,
        keyword: str,
        availability: int = 0,
        min_price: int | None = None,
        max_price: int | None = None,
        hits: int = 30,
        page: int = 1,
    ) -> list[dict]:
        """
        楽天市場で商品を検索する。

        Args:
            keyword: 検索キーワード（UTF-8）
            availability: 0=全商品（売り切れ含む）, 1=在庫ありのみ
            min_price: 最低価格フィルタ
            max_price: 最高価格フィルタ
            hits: 1ページの結果数（最大30）
            page: ページ番号

        Returns:
            商品情報の辞書リスト
        """
        self._rate_limit()

        params = {
            "applicationId": self.application_id,
            "accessKey": self.access_key,
            "keyword": keyword,
            "availability": availability,
            "hits": hits,
            "page": page,
            "format": "json",
        }
        if min_price is not None:
            params["minPrice"] = min_price
        if max_price is not None:
            params["maxPrice"] = max_price

        headers = {"Origin": "https://github.com"}
        response = requests.get(API_ENDPOINT, params=params, headers=headers, timeout=30)
        response.raise_for_status()

        data = response.json()
        items = []
        for item_wrapper in data.get("Items", []):
            items.append(item_wrapper["Item"])
        return items

    def search_with_retry(
        self, keyword: str, max_retries: int = 3, **kwargs
    ) -> list[dict]:
        """リトライ付き検索（指数バックオフ）"""
        for attempt in range(max_retries):
            try:
                return self.search(keyword=keyword, **kwargs)
            except (requests.ConnectionError, requests.Timeout) as e:
                if attempt < max_retries - 1:
                    wait = 5 * (2 ** attempt)
                    print(f"[リトライ] {keyword}: {attempt + 1}回目失敗 ({e}), {wait}秒後に再試行")
                    time.sleep(wait)
                else:
                    print(f"[エラー] {keyword}: リトライ上限到達")
                    raise
            except requests.HTTPError as e:
                status = e.response.status_code if e.response is not None else 0
                if status == 429:
                    wait = 10 * (attempt + 1)
                    print(f"[レート制限] {wait}秒待機中")
                    time.sleep(wait)
                elif status >= 500:
                    time.sleep(5 * (2 ** attempt))
                else:
                    raise
        return []
