# 楽天市場 在庫監視 + LINE通知システム

楽天市場の商品をキーワードで15分ごとに自動監視し、
「売り切れ → 在庫あり」に変わった瞬間にLINEへ通知するシステムです。

GitHub Actionsで完全自動・完全無料で運用できます。

---

## システム設計図

```
┌─────────────────────────────────────────────────────────┐
│  GitHub Actions (15分ごとに自動実行)                      │
│                                                         │
│  ┌───────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ config.yml│───▶│  monitor.py  │───▶│ state.json   │  │
│  │ キーワード │    │  メイン制御   │    │ 前回の状態    │  │
│  └───────────┘    └──────┬───────┘    └──────────────┘  │
│                          │                               │
│              ┌───────────┼───────────┐                   │
│              ▼           ▼           ▼                   │
│     ┌──────────────┐ ┌────────┐ ┌──────────────┐        │
│     │rakuten_api.py│ │比較処理│ │line_notify.py│        │
│     │楽天API検索   │ │0 → 1? │ │LINE通知送信  │        │
│     └──────┬───────┘ └────────┘ └──────┬───────┘        │
│            │                           │                 │
└────────────┼───────────────────────────┼─────────────────┘
             ▼                           ▼
    ┌─────────────────┐        ┌─────────────────┐
    │  楽天商品検索API  │        │ LINE Messaging  │
    │  (openapi.       │        │ API             │
    │   rakuten.co.jp) │        │ (api.line.me)   │
    └─────────────────┘        └────────┬────────┘
                                        ▼
                                  ┌───────────┐
                                  │  あなたの  │
                                  │  LINE      │
                                  └───────────┘
```

## 処理フロー

```
[15分ごとにcron起動]
        │
        ▼
config.yml からキーワード読み込み
        │
        ▼
┌─ キーワードごとにループ ──────────────────────────┐
│                                                  │
│  楽天商品検索API で検索 (availability=0: 全商品)   │
│        │                                         │
│        ▼                                         │
│  前回の state.json と比較                         │
│        │                                         │
│        ├─ 前回: 売切(0) → 今回: 在庫あり(1)       │
│        │     → 通知リストに追加                    │
│        │                                         │
│        ├─ 初回(None → 1): 通知しない（誤報防止）   │
│        │                                         │
│        └─ 変化なし: スキップ                      │
│                                                  │
│  state.json を更新                                │
└──────────────────────────────────────────────────┘
        │
        ▼
通知リストが空でなければ LINE に一括送信
        │
        ▼
state.json をGitにコミット（次回比較用に永続化）
```

---

## ファイル構成と役割

```
rakuten-stock-monitor/
├── .github/workflows/
│   └── monitor.yml        # GitHub Actions ワークフロー定義
├── monitor.py             # メインスクリプト（全体の制御）
├── rakuten_api.py         # 楽天商品検索APIクライアント
├── line_notify.py         # LINE Messaging API通知クライアント
├── state_manager.py       # 状態ファイル(JSON)の読み書き
├── config.yml             # 監視キーワード設定（ユーザーが編集）
├── state.json             # 前回の在庫状態（自動更新）
├── requirements.txt       # Python依存パッケージ
└── .gitignore
```

### 各ファイルの詳細

#### `monitor.py` - メインスクリプト
- エントリーポイント。全モジュールを組み合わせて監視処理を実行
- 環境変数から API キーを取得（`RAKUTEN_APP_ID`, `RAKUTEN_ACCESS_KEY`, `LINE_CHANNEL_ACCESS_TOKEN`, `LINE_USER_ID`）
- キーワードごとに楽天APIを検索し、前回状態と比較
- `availability: 0 → 1` の遷移を検出したらLINE通知
- 初回実行時（`None → 1`）は誤報防止のため通知しない

#### `rakuten_api.py` - 楽天APIクライアント
- **エンドポイント**: `https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601`（2026年新API）
- **認証**: `applicationId` + `accessKey` + `Origin`ヘッダー
- **レート制限**: 1リクエスト/秒を自動で守る
- **リトライ**: 最大3回、指数バックオフ（5秒→10秒→20秒）
- **429エラー**: レート制限時は10秒→20秒→30秒待機
- `availability=0` で売り切れ商品も含めて全件取得

#### `line_notify.py` - LINE通知クライアント
- **API**: LINE Messaging API（`POST https://api.line.me/v2/bot/message/push`）
- 複数商品を1通のメッセージにまとめて送信（月200通の無料枠を節約）
- 5000文字を超える場合は自動で分割送信
- 通知フォーマット:
  ```
  🔔 在庫復活アラート 🔔

  ✅ 商品名
     💰 1,039円
     🏪 ショップ名
     🔗 https://item.rakuten.co.jp/...
  ```

#### `state_manager.py` - 状態管理
- `state.json` の読み書きを担当
- 保存前にバックアップ（`.bak`）を作成、失敗時は自動復元
- 初回実行時は空の状態 `{"keywords": {}, "last_run": null}` を返す

#### `config.yml` - 監視設定
```yaml
monitor:
  api_delay: 1.5          # キーワード間の待機秒数

keywords:
  - keyword: "名探偵プリキュア シールバインダー"
    min_price: null        # 価格フィルタ（null=制限なし）
    max_price: null
```
- キーワード追加: `keywords` リストに項目を追加してpushするだけ
- `min_price` / `max_price` で価格帯を絞り込み可能

#### `state.json` - 在庫状態データ
```json
{
  "keywords": {
    "名探偵プリキュア シールバインダー": {
      "items": {
        "shop-code:item-id": {
          "item_name": "商品名",
          "item_url": "https://...",
          "item_price": 1039,
          "shop_name": "ショップ名",
          "availability": 0,       ← 0=売切, 1=在庫あり
          "last_seen": "2026-...",
          "last_changed": "2026-..."
        }
      }
    }
  },
  "last_run": "2026-02-28T..."
}
```

#### `.github/workflows/monitor.yml` - GitHub Actions
- **スケジュール**: `*/15 * * * *`（15分ごと）+ 手動実行対応
- **同時実行制御**: `concurrency` で重複実行を防止
- **タイムアウト**: 5分
- **状態永続化**: `stefanzweifel/git-auto-commit-action` で `state.json` を自動コミット
- **シークレット**: 4つの環境変数をGitHub Secretsから注入

---

## 外部サービス連携

### 楽天商品検索API（2026年新API）
| 項目 | 値 |
|------|---|
| エンドポイント | `https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20220601` |
| 認証 | `applicationId` + `accessKey`（クエリパラメータ）+ `Origin`ヘッダー |
| レート制限 | 1リクエスト/秒/applicationId |
| レスポンス構造 | `Items[].Item.availability`（0=売切, 1=在庫あり） |
| 管理画面 | https://webservice.rakuten.co.jp/ |

### LINE Messaging API
| 項目 | 値 |
|------|---|
| エンドポイント | `https://api.line.me/v2/bot/message/push` |
| 認証 | `Bearer {チャネルアクセストークン}` ヘッダー |
| 送信先 | `ユーザーID`（`U`で始まる文字列） |
| 無料枠 | 月200通 |
| 管理画面 | https://developers.line.biz/ |

### GitHub Actions
| 項目 | 値 |
|------|---|
| 実行頻度 | 15分ごと（cron） |
| 無料枠 | 公開リポジトリは無制限 |
| 注意 | 高負荷時は数分〜数十分の遅延あり |

---

## GitHub Secrets 一覧

リポジトリの Settings → Secrets and variables → Actions に設定:

| Secret名 | 説明 | 取得元 |
|----------|------|-------|
| `RAKUTEN_APP_ID` | 楽天 applicationId | [楽天ウェブサービス](https://webservice.rakuten.co.jp/) |
| `RAKUTEN_ACCESS_KEY` | 楽天アクセスキー | 同上（アプリ詳細画面） |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINEチャネルアクセストークン（長期） | [LINE Developers](https://developers.line.biz/) → Messaging API設定 |
| `LINE_USER_ID` | あなたのLINEユーザーID（`U`始まり） | LINE Developers → チャネル基本設定 |

---

## 運用コスト

すべて無料枠内で運用可能です。

| リソース | 制限 | 使用量目安 | 余裕 |
|---------|------|----------|------|
| GitHub Actions（公開リポ） | 無制限 | ~2,880回/月 | ✅ 問題なし |
| 楽天API | 1req/秒 | キーワード数 × 4回/時 | ✅ 十分 |
| LINE Messaging API | 200通/月 | 在庫変動時のみ（推定<20通） | ✅ 十分 |
| GitHubストレージ | 1GB | state.json 数KB | ✅ 十分 |

---

## よくある操作

### 監視キーワードを追加する
`config.yml` を編集してpush:
```yaml
keywords:
  - keyword: "名探偵プリキュア シールバインダー"
    min_price: null
    max_price: null

  - keyword: "追加したい商品名"    # ← 追加
    min_price: 1000               # 価格帯フィルタ（任意）
    max_price: 5000
```

### 手動で実行する
```bash
gh workflow run monitor.yml
```
またはGitHub → Actions → Stock Monitor → Run workflow

### 実行ログを確認する
```bash
gh run list --workflow=monitor.yml --limit=5
gh run view <run-id> --log
```

### 監視を一時停止する
GitHub → Actions → Stock Monitor → 右上「...」 → Disable workflow

### 監視を再開する
GitHub → Actions → Stock Monitor → Enable workflow

---

## トラブルシューティング

| 症状 | 原因 | 対処法 |
|------|------|-------|
| 403エラー（楽天API） | Originヘッダー不一致 or APIキー無効 | アプリ設定で許可ドメインに`github.com`を確認 |
| 429エラー（楽天API） | レート制限超過 | 自動リトライされる。頻発する場合は`api_delay`を増やす |
| LINE通知が届かない | 公式アカウント未追加 | QRコードから友だち追加 |
| LINE 401エラー | トークン失効 | LINE Developersでトークン再発行 → Secret更新 |
| state.jsonコミット失敗 | 権限不足 | ワークフローの`permissions: contents: write`を確認 |
| ワークフローが動かない | cron遅延 or 無効化 | Actionsタブで有効化を確認。手動実行で動作確認 |

---

## セットアップ手順（初回のみ）

### 1. 楽天デベロッパー登録（無料）
1. https://webservice.rakuten.co.jp/ にアクセス
2. 楽天IDでログイン → アプリ新規作成
3. アプリケーションタイプ: **Web Application**
4. アプリケーションURL: `https://github.com`
5. 許可するウェブサイト: `github.com`
6. APIアクセススコープ: **Rakuten Ichiba API** にチェック
7. `applicationId` と `accessKey` を控える

### 2. LINE Messaging API設定（無料）
1. https://developers.line.biz/ にログイン
2. プロバイダー作成 → 新規チャネル → **Messaging API**
3. 「Messaging API設定」タブ → **チャネルアクセストークン（長期）** を発行
4. 「チャネル基本設定」タブ → **あなたのユーザーID** を確認
5. QRコードからLINE公式アカウントを **友だち追加**

### 3. GitHub Secrets設定
```bash
gh secret set RAKUTEN_APP_ID --body "your-app-id"
gh secret set RAKUTEN_ACCESS_KEY --body "your-access-key"
gh secret set LINE_CHANNEL_ACCESS_TOKEN --body "your-token"
gh secret set LINE_USER_ID --body "your-user-id"
```

### 4. 動作確認
```bash
gh workflow run monitor.yml
gh run watch          # 実行完了を待つ
```
