"""Tầng ghi dữ liệu: lỗi mạng giữa chừng KHÔNG được làm mất dữ liệu đã có."""
import time

import pandas as pd
import pytest

from local_dev_data import LocalDevSupabase, _FakeTable
from tests._extract import CacheStub, load_functions


class FlakySupabase(LocalDevSupabase):
    """Supabase giả, ném lỗi ở lần GHI thứ fail_on (insert/upsert/delete) để mô phỏng mất mạng."""

    def __init__(self, fail_on=None):
        super().__init__()
        self.fail_on, self.writes = fail_on, 0
        outer = self

        class _T(_FakeTable):
            def execute(self):
                if self._op in {"insert", "upsert", "delete"}:
                    outer.writes += 1
                    if outer.fail_on is not None and outer.writes == outer.fail_on:
                        raise ConnectionError("521 Web server is down")
                return super().execute()

        self._T = _T

    def table(self, name):
        return self._T(self.store, name)


def make_ns(sb):
    ns = {"pd": pd, "time": time, "_get_supabase": lambda: sb}
    load_functions(["_fmt_ts", "_sb_retry", "_sb_select_all", "_sb_delete_all", "_merge_forest_into_db",
                    "delete_sessions", "save_mapping", "save_reading_log_bulk", "save_db"], ns)
    ns["_SB_PAGE_SIZE"] = 1000
    ns["time"] = type("T", (), {"sleep": staticmethod(lambda s: None), "time": staticmethod(time.time)})

    def load_db():
        rows = sb.store["sessions"]
        return pd.DataFrame([{"Thời gian bắt đầu": r["start_time"], "Thời gian kết thúc": r["end_time"],
                              "Dự án": r["project"], "Thời lượng (Phút)": r["duration_min"]} for r in rows],
                            columns=["Thời gian bắt đầu", "Thời gian kết thúc", "Dự án", "Thời lượng (Phút)"])
    for name in ["load_db", "prep_analysis_data", "load_mapping", "load_reading_log"]:
        ns[name] = CacheStub(load_db if name == "load_db" else None)
    return ns


def new_sessions(n, day="2030-01-01"):
    return pd.DataFrame([{"Thời gian bắt đầu": f"{day} {h:02d}:00:00.123", "Thời gian kết thúc": f"{day} {h:02d}:30:00",
                          "Dự án": "X", "Thời lượng (Phút)": 30} for h in range(n)])


def test_merge_only_inserts_new_and_skips_existing():
    sb = FlakySupabase(); ns = make_ns(sb)
    before = len(sb.store["sessions"])
    existing = sb.store["sessions"][0]
    dup = pd.DataFrame([{"Thời gian bắt đầu": existing["start_time"], "Thời gian kết thúc": existing["end_time"],
                         "Dự án": "KHÁC", "Thời lượng (Phút)": 1}])
    added = ns["_merge_forest_into_db"](pd.concat([new_sessions(3), dup, new_sessions(1)]))
    assert added == 3
    assert len(sb.store["sessions"]) == before + 3
    assert existing["project"] != "KHÁC"  # phiên đã có giữ nguyên bản cũ
    assert ns["load_db"].cleared and ns["prep_analysis_data"].cleared


def test_merge_failure_keeps_existing_sessions():
    sb = FlakySupabase(fail_on=1); ns = make_ns(sb)
    before = [dict(r) for r in sb.store["sessions"]]
    with pytest.raises(ConnectionError):
        ns["_merge_forest_into_db"](new_sessions(5))
    assert sb.store["sessions"] == before


def test_delete_sessions_removes_only_selected():
    sb = FlakySupabase(); ns = make_ns(sb)
    target = sb.store["sessions"][2]
    before = len(sb.store["sessions"])
    ns["delete_sessions"](pd.DataFrame([{"Thời gian bắt đầu": target["start_time"], "Thời gian kết thúc": target["end_time"]}]))
    assert len(sb.store["sessions"]) == before - 1
    assert target not in sb.store["sessions"]


def test_save_mapping_upserts_then_prunes():
    sb = FlakySupabase(); ns = make_ns(sb)
    ns["save_mapping"](pd.DataFrame([{"Dự án": "Deep work", "Nhóm": "Mới"}, {"Dự án": "Z", "Nhóm": "Khác"}]))
    got = {r["project"]: r["category"] for r in sb.store["mapping"]}
    assert got == {"Deep work": "Mới", "Z": "Khác"}


def test_save_mapping_failure_never_empties_table():
    sb = FlakySupabase(fail_on=2); ns = make_ns(sb)  # upsert ok, lần xoá dòng thừa lỗi
    with pytest.raises(ConnectionError):
        ns["save_mapping"](pd.DataFrame([{"Dự án": "Deep work", "Nhóm": "Mới"}]))
    assert sb.store["mapping"]


def rl_df(n):
    return pd.DataFrame([{"Ngày hoàn thành": "2030-01-01", "Sách (gốc)": "A - B", "Tiêu đề phần": f"P{i}"} for i in range(n)])


def test_reading_log_replaces_all_rows():
    sb = FlakySupabase(); ns = make_ns(sb)
    ns["save_reading_log_bulk"](rl_df(3))
    assert [r["title"] for r in sb.store["reading_log"]] == ["P0", "P1", "P2"]
    assert all(r["uid"].split("-")[-1].isdigit() for r in sb.store["reading_log"])


def test_reading_log_insert_failure_keeps_old_rows():
    sb = FlakySupabase(fail_on=1); ns = make_ns(sb)
    before = [dict(r) for r in sb.store["reading_log"]]
    with pytest.raises(ConnectionError):
        ns["save_reading_log_bulk"](rl_df(3))
    assert sb.store["reading_log"] == before


def test_select_all_retries_transient_errors():
    calls = {"n": 0}

    class Q:
        def range(self, a, b):
            return self

        def execute(self):
            calls["n"] += 1
            if calls["n"] < 3:
                raise ConnectionError("521")
            return type("R", (), {"data": [{"a": 1}]})()

    ns = make_ns(FlakySupabase())
    assert ns["_sb_select_all"](lambda: Q()) == [{"a": 1}]
    assert calls["n"] == 3


def test_notes_markdown_export():
    from ui_catalog import VN_DAYS
    import re
    from html import unescape as html_unescape
    ns = {"pd": pd, "re": re, "html_unescape": html_unescape, "VN_DAYS": VN_DAYS}
    load_functions(["_note_html_to_markdown", "_notes_to_markdown"], ns)
    notes = pd.DataFrame([
        {"Ngày": "2026-11-16", "Ghi chú": '<p>Hôm nay <strong>đậm</strong> và <em>nghiêng</em> &amp; '
                                          '<a href="https://x.y">link</a></p><ol><li>một</li>'
                                          '<li class="ql-indent-1">con</li><li>hai</li></ol>'},
        {"Ngày": "2026-11-02", "Ghi chú": "<p>Dòng 1<br>Dòng 2</p>"},
    ])
    md = ns["_notes_to_markdown"](notes)
    assert md.index("02/11/2026") < md.index("16/11/2026")
    assert "## Thứ Hai, 02/11/2026" in md and "Dòng 1\nDòng 2" in md
    assert "**đậm**" in md and "*nghiêng*" in md and "& [link](https://x.y)" in md
    assert "1. một\n  1. con\n2. hai" in md
