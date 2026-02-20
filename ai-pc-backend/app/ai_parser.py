import re


class AICommandParser:
    def __init__(self):
        self.command_patterns = self._build_patterns()

    def _build_patterns(self) -> list[dict]:
        return [
            {
                "patterns": [
                    r"(?:マウス|カーソル).*?(?:座標|位置)?\s*[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?\s*(?:に|へ)?.*?(?:移動|動か|move)",
                    r"(?:move|移動|動か).*?(?:マウス|カーソル|mouse).*?(\d+)\s*[,、]\s*(\d+)",
                    r"(?:マウス|カーソル).*?(\d+)\s*[,、]\s*(\d+).*?(?:移動|動か)",
                    r"(\d+)\s*[,、]\s*(\d+)\s*(?:に|へ).*?(?:移動|動か|move)",
                ],
                "builder": lambda m: {"action": "move_mouse", "x": int(m.group(1)), "y": int(m.group(2))},
            },
            {
                "patterns": [
                    r"(?:右|みぎ).*?(\d+).*?(?:px|ピクセル)?.*?(?:移動|動か)",
                    r"(?:move|移動|動か).*?(?:right|右).*?(\d+)",
                ],
                "builder": lambda m: {"action": "move_mouse", "x": int(m.group(1)), "y": 0, "relative": True},
            },
            {
                "patterns": [
                    r"(?:左|ひだり).*?(\d+).*?(?:px|ピクセル)?.*?(?:移動|動か)",
                    r"(?:move|移動|動か).*?(?:left|左).*?(\d+)",
                ],
                "builder": lambda m: {"action": "move_mouse", "x": -int(m.group(1)), "y": 0, "relative": True},
            },
            {
                "patterns": [
                    r"(?:上|うえ).*?(\d+).*?(?:px|ピクセル)?.*?(?:移動|動か)",
                    r"(?:move|移動|動か).*?(?:up|上).*?(\d+)",
                ],
                "builder": lambda m: {"action": "move_mouse", "x": 0, "y": -int(m.group(1)), "relative": True},
            },
            {
                "patterns": [
                    r"(?:下|した).*?(\d+).*?(?:px|ピクセル)?.*?(?:移動|動か)",
                    r"(?:move|移動|動か).*?(?:down|下).*?(\d+)",
                ],
                "builder": lambda m: {"action": "move_mouse", "x": 0, "y": int(m.group(1)), "relative": True},
            },
            {
                "patterns": [
                    r"(?:画面|スクリーン).*?(?:中央|真ん中|センター|center).*?(?:クリック|click)",
                    r"(?:中央|真ん中|センター|center).*?(?:クリック|click)",
                    r"(?:クリック|click).*?(?:中央|真ん中|センター|center)",
                ],
                "builder": lambda m: {"action": "click", "x": 640, "y": 360},
            },
            {
                "patterns": [
                    r"(?:ダブルクリック|double\s*click).*?[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?",
                    r"[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?\s*(?:を|で|に)?\s*(?:ダブルクリック|double\s*click)",
                ],
                "builder": lambda m: {"action": "double_click", "x": int(m.group(1)), "y": int(m.group(2))},
            },
            {
                "patterns": [
                    r"(?:ダブルクリック|double\s*click)(?!.*\d+\s*[,、]\s*\d+)",
                ],
                "builder": lambda m: {"action": "double_click"},
            },
            {
                "patterns": [
                    r"(?:右クリック|right\s*click).*?[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?",
                    r"[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?\s*(?:を|で|に)?\s*(?:右クリック|right\s*click)",
                ],
                "builder": lambda m: {"action": "right_click", "x": int(m.group(1)), "y": int(m.group(2))},
            },
            {
                "patterns": [
                    r"(?:右クリック|right\s*click)(?!.*\d+\s*[,、]\s*\d+)",
                ],
                "builder": lambda m: {"action": "right_click"},
            },
            {
                "patterns": [
                    r"(?:クリック|click).*?[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?",
                    r"[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?\s*(?:を|で|に)?\s*(?:クリック|click)",
                ],
                "builder": lambda m: {"action": "click", "x": int(m.group(1)), "y": int(m.group(2))},
            },
            {
                "patterns": [
                    r"(?:クリック|click)(?!.*\d+\s*[,、]\s*\d+)",
                ],
                "builder": lambda m: {"action": "click"},
            },
            {
                "patterns": [
                    r"[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?\s*(?:から|from).*?[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?\s*(?:まで|へ|に|to)?\s*(?:ドラッグ|drag)",
                    r"(?:ドラッグ|drag).*?[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?\s*(?:から|from).*?[\(（]?\s*(\d+)\s*[,、]\s*(\d+)\s*[\)）]?",
                ],
                "builder": lambda m: {"action": "drag", "start_x": int(m.group(1)), "start_y": int(m.group(2)), "end_x": int(m.group(3)), "end_y": int(m.group(4))},
            },
            {
                "patterns": [
                    r"[「『\"'](.+?)[」』\"']\s*(?:と|って)?\s*(?:入力|タイプ|打って?|type|input)",
                    r"(?:入力|タイプ|打って?|type|input)\s*[「『\"'](.+?)[」』\"']",
                    r"(.+?)(?:と|って)\s*(?:入力|タイプ|打って)\s*(?:して|ください|て)?",
                    r"(?:入力|タイプ|打って|type|input)\s*[:：]\s*(.+?)$",
                ],
                "builder": lambda m: {"action": "type_text", "text": next(g for g in m.groups() if g is not None)},
            },
            {
                "patterns": [
                    r"(?:Ctrl|ctrl|コントロール)\s*[+＋]\s*([A-Za-z])",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": f"ctrl+{m.group(1).lower()}"},
            },
            {
                "patterns": [
                    r"(?:Alt|alt|オルト)\s*[+＋]\s*([A-Za-z])",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": f"alt+{m.group(1).lower()}"},
            },
            {
                "patterns": [
                    r"(?:Ctrl|ctrl|コントロール)\s*[+＋]\s*(?:Shift|shift|シフト)\s*[+＋]\s*([A-Za-z])",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": f"ctrl+shift+{m.group(1).lower()}"},
            },
            {
                "patterns": [
                    r"(?:Alt|alt)\s*[+＋]\s*(?:F4|f4)",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": "alt+F4"},
            },
            {
                "patterns": [
                    r"(?:Enter|エンター|改行|リターン).*?(?:押|press|キー)",
                    r"(?:押|press).*?(?:Enter|エンター|改行|リターン)",
                ],
                "builder": lambda m: {"action": "key_press", "keys": "Return"},
            },
            {
                "patterns": [
                    r"(?:Escape|ESC|エスケープ).*?(?:押|press|キー)",
                    r"(?:押|press).*?(?:Escape|ESC|エスケープ)",
                ],
                "builder": lambda m: {"action": "key_press", "keys": "Escape"},
            },
            {
                "patterns": [
                    r"(?:Tab|タブ).*?(?:押|press|キー)",
                    r"(?:押|press).*?(?:Tab|タブ)",
                ],
                "builder": lambda m: {"action": "key_press", "keys": "Tab"},
            },
            {
                "patterns": [
                    r"(?:BackSpace|バックスペース|Backspace).*?(?:押|press|キー)",
                    r"(?:押|press).*?(?:BackSpace|バックスペース|Backspace)",
                    r"(?:一文字|1文字).*?(?:消|削除)",
                ],
                "builder": lambda m: {"action": "key_press", "keys": "BackSpace"},
            },
            {
                "patterns": [
                    r"(?:Delete|デリート|削除キー).*?(?:押|press|キー)",
                    r"(?:押|press).*?(?:Delete|デリート|削除キー)",
                ],
                "builder": lambda m: {"action": "key_press", "keys": "Delete"},
            },
            {
                "patterns": [
                    r"(?:スクロール|scroll).*?(?:上|アップ|up)",
                    r"(?:上|アップ|up).*?(?:スクロール|scroll)",
                ],
                "builder": lambda m: {"action": "scroll", "direction": "up", "amount": 3},
            },
            {
                "patterns": [
                    r"(?:スクロール|scroll).*?(?:下|ダウン|down)",
                    r"(?:下|ダウン|down).*?(?:スクロール|scroll)",
                ],
                "builder": lambda m: {"action": "scroll", "direction": "down", "amount": 3},
            },
            {
                "patterns": [
                    r"(?:全選択|全て選択|すべて選択|select\s*all)",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": "ctrl+a"},
            },
            {
                "patterns": [
                    r"(?:コピー|copy)(?!.*ペースト|.*paste)",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": "ctrl+c"},
            },
            {
                "patterns": [
                    r"(?:ペースト|貼り付け|paste)",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": "ctrl+v"},
            },
            {
                "patterns": [
                    r"(?:切り取り|カット|cut)",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": "ctrl+x"},
            },
            {
                "patterns": [
                    r"(?:元に戻す|アンドゥ|undo|取り消)",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": "ctrl+z"},
            },
            {
                "patterns": [
                    r"(?:やり直し|リドゥ|redo)",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": "ctrl+y"},
            },
            {
                "patterns": [
                    r"(?:保存|セーブ|save)",
                ],
                "builder": lambda m: {"action": "shortcut", "keys": "ctrl+s"},
            },
            {
                "patterns": [
                    r"(?:マウス|カーソル).*?(?:位置|場所|どこ|where)",
                    r"(?:位置|場所).*?(?:教え|確認|取得)",
                ],
                "builder": lambda m: {"action": "get_mouse_position"},
            },
            {
                "patterns": [
                    r"(?:YouTube|ユーチューブ|youtube).*?(?:開|起動|launch|open|立ち上|見)",
                    r"(?:開|起動|launch|open|立ち上).*?(?:YouTube|ユーチューブ|youtube)",
                ],
                "builder": lambda m: {"action": "open_url", "url": "https://www.youtube.com"},
            },
            {
                "patterns": [
                    r"(?:Google|グーグル|google).*?(?:開|起動|launch|open|立ち上)",
                    r"(?:開|起動|launch|open|立ち上).*?(?:Google|グーグル|google)",
                ],
                "builder": lambda m: {"action": "open_url", "url": "https://www.google.com"},
            },
            {
                "patterns": [
                    r"(?:Twitter|ツイッター|twitter|X).*?(?:開|起動|launch|open|立ち上)",
                    r"(?:開|起動|launch|open|立ち上).*?(?:Twitter|ツイッター|twitter)",
                ],
                "builder": lambda m: {"action": "open_url", "url": "https://x.com"},
            },
            {
                "patterns": [
                    r"(?:Chrome|クローム|chrome|ブラウザ|browser).*?(?:開|起動|launch|open|立ち上)",
                    r"(?:開|起動|launch|open|立ち上).*?(?:Chrome|クローム|chrome|ブラウザ|browser)",
                ],
                "builder": lambda m: {"action": "open_app", "app_name": "chrome"},
            },
            {
                "patterns": [
                    r"(?:Firefox|ファイアフォックス|firefox).*?(?:開|起動|launch|open|立ち上)",
                    r"(?:開|起動|launch|open|立ち上).*?(?:Firefox|ファイアフォックス|firefox)",
                ],
                "builder": lambda m: {"action": "open_app", "app_name": "firefox"},
            },
            {
                "patterns": [
                    r"(?:ターミナル|terminal|端末).*?(?:開|起動|launch|open|立ち上)",
                    r"(?:開|起動|launch|open|立ち上).*?(?:ターミナル|terminal|端末)",
                ],
                "builder": lambda m: {"action": "open_app", "app_name": "terminal"},
            },
            {
                "patterns": [
                    r"(?:メモ帳|テキストエディタ|editor|エディタ|gedit|nano).*?(?:開|起動|launch|open|立ち上)",
                    r"(?:開|起動|launch|open|立ち上).*?(?:メモ帳|テキストエディタ|editor|エディタ|gedit|nano)",
                ],
                "builder": lambda m: {"action": "open_app", "app_name": "notepad"},
            },
        ]

    def parse(self, message: str) -> list[dict]:
        message = message.strip()
        if not message:
            return []

        for pattern_group in self.command_patterns:
            for pattern in pattern_group["patterns"]:
                match = re.search(pattern, message, re.IGNORECASE)
                if match:
                    cmd = pattern_group["builder"](match)
                    return [cmd]

        if any(word in message for word in ["クリック", "click"]):
            return [{"action": "click"}]
        if any(word in message for word in ["入力", "タイプ", "type", "打"]):
            text = re.sub(r"^.*?(?:入力|タイプ|type|打って?)\s*", "", message)
            if text:
                return [{"action": "type_text", "text": text}]

        return [{"action": "type_text", "text": message}]

    def generate_reply(self, user_message: str, results: list[dict]) -> str:
        if not results:
            return "コマンドを理解できませんでした。もう一度お試しください。"

        all_success = all(r.get("success", False) for r in results)
        descriptions = [r.get("description", "") for r in results if r.get("description")]

        if all_success:
            action_text = "、".join(descriptions)
            return f"実行完了: {action_text}"
        else:
            failed = [r.get("description", r.get("error", "unknown")) for r in results if not r.get("success")]
            return f"一部のアクションが失敗しました: {', '.join(failed)}"
