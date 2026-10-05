# LocalSecretManager

ローカルで動くパスワード管理Webアプリ。

## 起動
```
pip install cryptography
python server.py [port]   # http://127.0.0.1:8000
```
パスワードは `data/secret.key` の鍵でFernet暗号化され `data/secrets.db`(SQLite)に保存されます。鍵ファイルは大切に保管してください。

## 画面
- **一覧**: 登録済みパスワードを全件表示(パスワードは既定でマスク、👁で表示、コピー/編集/削除可)。絞り込み入力あり
- **高度検索**: 下記のA〜E条件 + 論理式
- **生成**: 文字種・長さを指定してパスワード生成
- **新規登録**: 右上のボタン。ダイアログ内でも自動生成できます

## フロントエンド開発
UIは React + TypeScript (Vite) で `frontend/` にあり、ビルド結果は `static/` に出力され `server.py` が配信します(ビルド済みを同梱しているので通常はNode不要)。
```
cd frontend
npm install
npm run dev     # 開発サーバー(/api は 127.0.0.1:8000 へプロキシ)
npm run build   # static/ を更新
```

## 検索
条件A〜Eに文字列を入力し、論理式をC言語スタイルで指定します(例: `A&&(B||C)`、`!` も可)。サイト名またはキーワードに条件文字列が含まれるとTrueです(大文字小文字は区別しません)。

## 主キー
レコードは「サイト/アプリ名 + ユーザー名」で一意です。ユーザー名は空でもよく、`msn.co.jp`+`user01` と `msn.co.jp`+(空) は別レコードです。旧版のDB(サイト名のみ主キー)は起動時に自動で移行されます。

## テスト
```
python -m unittest discover -s tests      # コア/APIの自動テスト (62件)
cd frontend && npm run test:e2e           # 画面E2E (Playwright + インストール済みChrome, 43件)
```
E2Eは実サーバーを一時データディレクトリ(`frontend/.e2e-data`)で起動し、ビルド済みUIを操作します。
