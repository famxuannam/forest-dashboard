"""Supabase giả và dữ liệu minh hoạ, chỉ dùng khi FOREST_LOCAL_DEV được bật."""

from datetime import date, timedelta


class _FakeResponse:
    def __init__(self, data=None):
        self.data = data or []


class _FakeTable:
    """Phần API Supabase tối thiểu app dùng, chỉ dành cho local development."""

    def __init__(self, store, name):
        self.store, self.name = store, name
        self._op, self._payload, self._filters, self._orders, self._span = "select", None, [], [], None

    def select(self, fields="*"):
        self._op, self._payload = "select", fields
        return self

    def insert(self, rows):
        self._op, self._payload = "insert", rows
        return self

    def upsert(self, rows, on_conflict=None, **_kwargs):
        self._op, self._payload, self._conflict = "upsert", rows, (on_conflict or "").split(",")
        return self

    def update(self, values):
        self._op, self._payload = "update", values
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, key, value):
        self._filters.append((key, "eq", value))
        return self

    def gte(self, key, value):
        self._filters.append((key, "gte", value))
        return self

    def lt(self, key, value):
        self._filters.append((key, "lt", value))
        return self

    @property
    def not_(self):
        return self

    def is_(self, key, value):
        self._filters.append((key, "not_null" if value == "null" else "eq", value))
        return self

    def order(self, key):
        self._orders.append(key)
        return self

    def range(self, start, end):
        self._span = (start, end)
        return self

    def _matches(self, row):
        for key, op, value in self._filters:
            actual = row.get(key)
            if (op == "eq" and actual != value) or (op == "gte" and (actual is None or actual < value)) \
                    or (op == "lt" and (actual is None or actual >= value)) or (op == "not_null" and actual is None):
                return False
        return True

    def execute(self):
        rows = self.store.setdefault(self.name, [])
        matched = [r for r in rows if self._matches(r)]
        if self._op == "delete":
            self.store[self.name] = [r for r in rows if not self._matches(r)]
            return _FakeResponse(matched)
        if self._op == "update":
            for row in matched:
                row.update(self._payload)
            return _FakeResponse(matched)
        if self._op in {"insert", "upsert"}:
            records = self._payload if isinstance(self._payload, list) else [self._payload]
            for record in records:
                record = dict(record)
                conflict = next((r for r in rows if self._conflict and all(r.get(k) == record.get(k) for k in self._conflict)), None) if self._op == "upsert" else None
                if conflict is not None:
                    conflict.update(record)
                else:
                    if self.name == "quick_notes" and "id" not in record:
                        record["id"] = max((r.get("id", 0) for r in rows), default=0) + 1
                    rows.append(record)
            return _FakeResponse(records)
        for key in reversed(self._orders):
            matched.sort(key=lambda r: (r.get(key) is None, str(r.get(key, ""))))
        if self._span:
            matched = matched[self._span[0]:self._span[1] + 1]
        if self._payload and self._payload != "*":
            keys = [key.strip() for key in self._payload.split(",")]
            matched = [{key: row.get(key) for key in keys} for row in matched]
        return _FakeResponse(matched)


class LocalDevSupabase:
    """Client Supabase trong bộ nhớ với dữ liệu minh hoạ cho chạy local."""

    def __init__(self):
        today = date.today()
        self.store = {
            "sessions": [
                {"id": i + 1, "start_time": f"{(today - timedelta(days=i)).isoformat()} {hour:02d}:00:00",
                 "end_time": f"{(today - timedelta(days=i)).isoformat()} {hour + 1:02d}:00:00",
                 "project": project, "duration_min": 60}
                for i, (hour, project) in enumerate([(9, "Deep work"), (14, "Reading"), (10, "Học tập"), (16, "Deep work"), (8, "Reading"), (13, "Học tập"), (9, "Deep work")])
            ] + [
                {"id": 8, "start_time": f"{today.isoformat()} 20:00:00", "end_time": f"{today.isoformat()} 20:45:00", "project": "Reading", "duration_min": 45},
                {"id": 9, "start_time": f"{(today - timedelta(days=2)).isoformat()} 21:00:00", "end_time": f"{(today - timedelta(days=2)).isoformat()} 21:30:00", "project": "Reading", "duration_min": 30},
                {"id": 10, "start_time": f"{(today - timedelta(days=3)).isoformat()} 19:00:00", "end_time": f"{(today - timedelta(days=3)).isoformat()} 20:15:00", "project": "Reading", "duration_min": 75},
            ],
            "mapping": [
                {"project": "Deep work", "category": "Công việc"},
                {"project": "Reading", "category": "Reading"},
                {"project": "Học tập", "category": "Phát triển"},
            ],
            "notes": [{"note_date": today.isoformat(), "note": "<p>Dữ liệu minh hoạ khi chạy local.</p>"}],
            "settings": [], "deleted_sessions": [], "quick_notes": [], "work_calendar": [],
            "reading_log": [
                {"uid": "demo-read-1", "completed_date": (today - timedelta(days=9)).isoformat(), "book": "Ursula K. Le Guin - The Dispossessed", "title": "Chương 1 · Anarres"},
                {"uid": "demo-read-2", "completed_date": (today - timedelta(days=6)).isoformat(), "book": "Ursula K. Le Guin - The Dispossessed", "title": "Chương 2 · Urras"},
                {"uid": "demo-read-3", "completed_date": (today - timedelta(days=4)).isoformat(), "book": "Ursula K. Le Guin - The Dispossessed", "title": "Chương 3 · Bức tường"},
                {"uid": "demo-read-4", "completed_date": (today - timedelta(days=3)).isoformat(), "book": "Toni Morrison - Beloved", "title": "Phần 1 · 124"},
                {"uid": "demo-read-5", "completed_date": (today - timedelta(days=1)).isoformat(), "book": "Toni Morrison - Beloved", "title": "Phần 2 · Sethe"},
                {"uid": "demo-read-6", "completed_date": today.isoformat(), "book": "Toni Morrison - Beloved", "title": "Phần 3 · Dấu vết"},
            ],
            "kindle_book_map": [
                {"kindle_title": "The Dispossessed", "project": "The Dispossessed", "label": "The Dispossessed"},
                {"kindle_title": "Beloved", "project": "Beloved", "label": "Beloved"},
            ],
            "kindle_highlights": [
                {"dedupe_hash": "demo-dispossessed-1", "kindle_title": "The Dispossessed", "author": "Ursula K. Le Guin", "kind": "highlight", "content": "You cannot buy the revolution. You cannot make the revolution.", "location": "45", "added_at": (today - timedelta(days=6)).isoformat(), "parent_hash": None, "is_favorite": True},
                {"dedupe_hash": "demo-dispossessed-2", "kindle_title": "The Dispossessed", "author": "Ursula K. Le Guin", "kind": "highlight", "content": "To be whole is to be part; true voyage is return.", "location": "88", "added_at": (today - timedelta(days=4)).isoformat(), "parent_hash": None, "is_favorite": False},
                {"dedupe_hash": "demo-dispossessed-note-1", "kindle_title": "The Dispossessed", "author": "Ursula K. Le Guin", "kind": "note", "content": "Đối chiếu với ý niệm tự do trong chương đầu.", "location": "88", "added_at": (today - timedelta(days=4)).isoformat(), "parent_hash": "demo-dispossessed-2", "is_favorite": False},
                {"dedupe_hash": "demo-beloved-1", "kindle_title": "Beloved", "author": "Toni Morrison", "kind": "highlight", "content": "Freeing yourself was one thing; claiming ownership of that freed self was another.", "location": "112", "added_at": (today - timedelta(days=1)).isoformat(), "parent_hash": None, "is_favorite": True},
                {"dedupe_hash": "demo-beloved-2", "kindle_title": "Beloved", "author": "Toni Morrison", "kind": "highlight", "content": "Anything dead coming back to life hurts.", "location": "137", "added_at": today.isoformat(), "parent_hash": None, "is_favorite": False},
            ],
            "deleted_kindle_highlights": [], "gundam_overrides": [], "book_overrides": [],
        }

    def table(self, name):
        return _FakeTable(self.store, name)
