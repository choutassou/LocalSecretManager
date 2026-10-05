# LocalSecretManager

ローカルで動くパスワード管理Webアプリ。

## 起動
```
pip install cryptography
python server.py [port]   # http://127.0.0.1:8000
```
パスワードは `data/secret.key` の鍵でFernet暗号化され `data/secrets.db`(SQLite)に保存されます。鍵ファイルは大切に保管してください。

## 検索
条件A〜Eに文字列を入力し、論理式をC言語スタイルで指定します(例: `A&&(B||C)`、`!` も可)。サイト名またはキーワードに条件文字列が含まれるとTrueです(大文字小文字は区別しません)。

## テスト
`python -m unittest discover -s tests`
