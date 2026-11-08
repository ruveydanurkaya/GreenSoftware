"""Depolama: her aday tek bir küçük JSON dosyası (birkaç yüz bayt).
Bellekte bir 'ters indeks' tutulur: yetenek -> {aday id'leri} (Set).
Böylece 'bu yeteneğe sahip adaylar kimler?' sorusu ortalama O(1) ile cevaplanır."""
import json
import threading
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent / "data"
JOBS_FILE = BASE / "ilanlar.json"


def dumps(rec: dict) -> str:
    # Boşluksuz, UTF-8 kompakt JSON: gereksiz bayt yok.
    return json.dumps(rec, ensure_ascii=False, separators=(",", ":"))


def load_jobs() -> list[dict]:
    return json.loads(JOBS_FILE.read_text("utf-8"))


class Index:
    """Sadece bellek: aday kayıtları + yetenek kümeleri + ters indeks."""

    def __init__(self):
        self.candidates: dict[str, dict] = {}
        self.skillsets: dict[str, frozenset] = {}
        self.skill_index: dict[str, set] = defaultdict(set)

    def add_to_memory(self, rec: dict) -> None:
        cid = rec["id"]
        self.candidates[cid] = rec
        self.skillsets[cid] = frozenset(rec["yetenekler"])
        for s in rec["yetenekler"]:
            self.skill_index[s].add(cid)


class Store(Index):
    """Index + diske yazma/okuma."""

    def __init__(self, base: Path | None = None):
        super().__init__()
        self.base = Path(base) if base else BASE
        self.dir = self.base / "adaylar"      # aday başına küçük JSON
        self.cv_dir = self.base / "cv"        # yalnızca elemeyi geçenlerin CV'si
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cv_dir.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        for p in sorted(self.dir.glob("*.json")):
            self.add_to_memory(json.loads(p.read_text("utf-8")))

    def _write(self, rec: dict) -> int:
        payload = dumps(rec).encode("utf-8")
        (self.dir / f"{rec['id']}.json").write_bytes(payload)
        return len(payload)

    def add(self, rec: dict) -> int:
        with self.lock:
            size = self._write(rec)
            self.add_to_memory(rec)
            return size

    def set_status(self, cid: str, status: str) -> None:
        with self.lock:
            rec = self.candidates[cid]
            rec["durum"] = status
            self._write(rec)

    def size_of(self, cid: str) -> int:
        return len(dumps(self.candidates[cid]).encode("utf-8"))

    def cv_path(self, cid: str) -> Path:
        return self.cv_dir / f"{cid}.pdf"

    def save_cv(self, cid: str, data: bytes) -> None:
        with self.lock:
            self.cv_path(cid).write_bytes(data)
            rec = self.candidates[cid]
            rec["durum"] = "cv_geldi"
            self._write(rec)
