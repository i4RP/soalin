# AI PC Agent

MacBook Pro上で実行するエージェント。AI PC Controllerからリモートでマウス・キーボード操作が可能になります。

## セットアップ (macOS)

### 1. Python 3.10+ をインストール
```bash
brew install python@3.12
```

### 2. エージェントをインストール
```bash
pip install -r requirements.txt
```

### 3. macOS権限を許可
- **システム設定 > プライバシーとセキュリティ > アクセシビリティ** → ターミナルを許可
- **システム設定 > プライバシーとセキュリティ > 画面収録** → ターミナルを許可

### 4. 接続コードを取得
1. スマホで https://ai-chat-control-app-dy7elgjp.devinapps.com にアクセス
2. Settings > Create Session で接続コードを取得

### 5. エージェントを実行
```bash
python -m ai_pc_agent --server https://app-dltbojca.fly.dev --code ABC123
```

## オプション
- `--fps 3` - 画面キャプチャのFPSを変更（デフォルト: 2）
- `-s` / `--server` - サーバーURL
- `-c` / `--code` - 接続コード
