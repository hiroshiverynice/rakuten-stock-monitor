# 楽天市場 在庫監視システム

楽天市場の商品をキーワードで定期監視し、「売り切れ → 在庫あり」に変わったらLINEに通知するシステムです。

GitHub Actionsで15分ごとに自動実行されます（完全無料）。

## セットアップ手順

### 1. 楽天デベロッパー登録（無料）

1. [楽天ウェブサービス](https://webservice.rakuten.co.jp/) にアクセス
2. アカウント作成 → アプリ登録
3. **applicationId** を控える

### 2. LINE Messaging API 設定（無料）

1. [LINE Developers](https://developers.line.biz/) にログイン
2. 新規プロバイダー → 新規チャネル → **Messaging API** を選択
3. チャネル設定画面で:
   - 「Messaging API設定」→ **チャネルアクセストークン** を発行（長期）
   - 「チャネル基本設定」→ **あなたのユーザーID** を確認
4. LINE公式アカウントを友だち追加する（QRコードから）

> 無料プランは月200通まで。在庫変動時のみ通知するので十分です。

### 3. GitHubリポジトリ作成

1. このリポジトリをGitHubにpush（**公開リポジトリ推奨** → Actions無制限）
2. リポジトリの Settings → Secrets and variables → Actions で以下を追加:

| Secret名 | 値 |
|----------|---|
| `RAKUTEN_APP_ID` | 楽天の applicationId |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINEのチャネルアクセストークン |
| `LINE_USER_ID` | あなたのLINEユーザーID（`U`で始まる） |

### 4. 監視キーワード設定

`config.yml` を編集して監視したい商品のキーワードを追加:

```yaml
keywords:
  - keyword: "PS5 本体"
    min_price: 40000
    max_price: 80000

  - keyword: "Nintendo Switch 有機EL"
    min_price: 30000
    max_price: 50000
```

### 5. 動作確認

- GitHub Actions → Stock Monitor → Run workflow（手動実行）
- 正常に動けば `state.json` が自動更新される

## 仕組み

```
15分ごと（GitHub Actions cron）
    ↓
楽天商品検索API でキーワード検索
    ↓
前回の state.json と比較
    ↓
「売り切れ(0) → 在庫あり(1)」を検出
    ↓
LINE Messaging API で通知
    ↓
state.json を更新・コミット
```

## コスト

すべて無料枠内で運用可能です。

| リソース | 制限 | 使用量目安 |
|---------|------|----------|
| GitHub Actions（公開リポ） | 無制限 | ~2,880回/月 |
| 楽天API | 1req/秒 | 数回/15分 |
| LINE Messaging API | 200通/月 | 在庫変動時のみ |
