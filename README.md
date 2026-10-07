# Padly iPadOS 遅延アップデート早見

Appleが公式に提供するRSS・APIを使い、iPadOSのリリース履歴と（ベータ中の）予定を取得して、
**MDMでソフトウェアアップデートを「N日遅延」しているiPadがいつ更新できるか**を表示する静的Webサイトです。
iPad Safariで開けます。メジャーバージョンごとにグループ化し、各版のリリース情報・リリースノートへのリンクと対応モデルを表示します。デザインは Material Design 3（primary = Apple Blue `#007AFF`（ダークは同色相の `#679CFF`）、その他のカラーロールは公式 material-color-utilities の Tonal Spot で生成、表示切替は独立した2つのトグルボタン（ボタングループ）、タイプスケール／シェイプ／state layer／Material Symbols を各仕様どおりに実装。ライト／ダークはOS設定に自動追従）。

画面上部に **現在入れれる iPadOS**（入手可能日〜）と **次に入れれる iPadOS**（入手可能日〜 / リリース日）を分けて表示し、ページ最下部に `最終更新 YYYY年M月D日 HH:mm (JST)`（`data/releases.json` の `updated`＝サーバー側の最終取得時刻）を表示します。

## 設計（取得場所と取得方法）

| 項目 | 決定 | 理由 |
|---|---|---|
| 取得場所 | **サーバー側**（GitHub Actionsが毎日実行）。iPadは同一サイトの `data/releases.json` を読むだけ | Apple側のCORS許可は確認できておらず、ブラウザ直接取得を前提にできない（要確認）。RSSは直近分しか載らないため、履歴を蓄積するには保存先が必要。AppleはGDMFの確認を1日1回程度までとしている |
| 主データ源 | Apple Developer Releases RSS `https://developer.apple.com/news/releases/rss/releases.rss` | 正確な公開日時（pubDate）とビルド番号。`iPadOS x.y (ビルド)` = 正式版、`beta`/`RC` 付き = ベータ |
| 補助データ源 | Apple Software Lookup Service (GDMF) `https://gdmf.apple.com/v2/pmv` | 配信終了日（ExpirationDate）のみ利用。取得失敗時はRSSのみで続行 |
| 更新タイミング | ①デプロイ（mainへのpush）時に1回 ②以降は毎日 18:15 UTC（03:15 JST）＝Appleの公開時刻（太平洋時間10:00が通例）の後 | Actionsの定期実行は遅延することがあります |
| 対応モデル | Apple security releases `https://support.apple.com/en-us/100100` の「Available for」（製品名表記）を更新ごとに保存。デバイス識別子は使わない | 更新ごとの対応機種を公式が製品名で載せている。HTML構造は未検証のため初回実行ログで確認（要確認） |
| 端末側の保存 | 遅延日数・モデル・メジャーを `localStorage` に保存し、データもキャッシュして開いた直後に自分用の結果を表示 | 長期間未訪問だとSafariが保存を消す場合あり（要確認） |
| 履歴 | 毎回 `data/releases.json` にマージしてGitへコミット | RSS・GDMFとも過去分が消えるため |
| 遅延の計算 | iPad側（JavaScript）で `公開日 + 遅延日数` | Apple仕様: 監視対象（supervised）端末で、公開日から1〜90日後に更新が提示される |

「予定」について: Appleは正式版の公開日を事前公表しません。本サイトの「予定」は、RSSに載ったベータ／RC中のバージョンと、
入力した**仮の公開日**からの計算値です。

## ファイル構成

```
index.html                      画面（HTML/CSS/JS 1ファイル）
data/releases.json              取得済みデータ（Actionsが自動更新。初期値は2026-09-24時点の実データ）
scripts/fetch_releases.py       RSS/GDMF取得・マージスクリプト（標準ライブラリのみ）
.github/workflows/update.yml    毎日の取得 → コミット → GitHub Pagesデプロイ
```

## 必要環境

- Git、GitHubアカウント（無料でOK）
- ローカル確認する場合のみ Python 3.9以降（外部パッケージ不要）
- APIキー・`.env`・外部サービスの登録は**不要**

## ローカルで確認する

```bash
python3 scripts/fetch_releases.py   # データ更新（任意。Appleへ接続できる環境で）
python3 -m http.server 8000         # http://localhost:8000 を開く
```

## GitHubへアップロードして公開する

1. GitHubで **New repository** を作成（例: `Padly`、Public、README等の追加は不要）
2. このフォルダで以下を実行（`<USER>` は自分のGitHubユーザー名）
   ```bash
   git init
   git add .
   git commit -m "first commit"
   git branch -M main
   git remote add origin https://github.com/<USER>/Padly.git
   git push -u origin main
   ```
3. リポジトリの **Settings** → **Pages** → **Build and deployment** → **Source** を **GitHub Actions** に変更
4. **Settings** → **Actions** → **General** → **Workflow permissions** を **Read and write permissions** にして **Save**（データ自動コミットに必要。項目名は要確認）
5. **Actions** タブ → **update-data-and-deploy** → **Run workflow** で初回実行
6. 成功後、`https://<USER>.github.io/Padly/` をiPadのSafariで開く

補足:
- Actionsで `GITHUB_TOKEN` によりpushしたコミットは、ブランチ公開方式のPagesビルドを起動しないと公式ドキュメントに記載があるため、本リポジトリはPagesを**Actions方式**でデプロイしています。
- 使用しているアクションのバージョン（`checkout@v4` 等）は新しい版が出ている可能性があります（要確認）。
- 長期間リポジトリに動きがないとスケジュール実行が停止する場合があります（要確認）。その際は **Run workflow** で再開してください。

## 既知の制約・要確認事項

- GDMFのJSON構造（`PublicAssetSets` 配下の `SupportedDevices`）は公式ドキュメントの記載に基づく実装ですが、初回Actions実行のログで取得件数を確認してください。GDMFの証明書がランナーで検証できない場合は警告のみでRSSのみで動作します。
- 遅延の時刻境界（公開時刻から起算か、日付単位か）はAppleが明記しておらず、表示は日付の目安です。
- 「〇〇 and later」表記の判定にはコード内の機種カタログ（`index.html` の `CAT`）を使います。新機種が出たら追記してください。範囲表記（例: 3rd - 5th generation）は判定できず表示のみです。
- 日付の食い違い: RSSのiPadOS 26.7は9/9、security releasesでは9/14公開と表記が異なります。遅延計算はRSS日時を使用（要確認）。
- Slack/メール通知は未実装です。
