from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from platformdirs import user_data_dir

APP_NAME = "OSReview"
APP_AUTHOR = "OpenAI"


class HistoryStore:
    def __init__(self) -> None:
        self.base_dir = Path(user_data_dir(APP_NAME, APP_AUTHOR))
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.file = self.base_dir / "history.json"
        if not self.file.exists():
            self.file.write_text(json.dumps({"records": []}, ensure_ascii=False, indent=2), encoding="utf-8")

    def load(self) -> List[Dict[str, Any]]:
        data = json.loads(self.file.read_text(encoding="utf-8"))
        return data.get("records", [])

    def append(self, record: Dict[str, Any]) -> None:
        payload = {"records": self.load()}
        payload["records"].append(record)
        payload["records"] = payload["records"][-200:]
        self.file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def export_path(self) -> str:
        return str(self.file)
