"""Chạy app thật (dữ liệu mẫu FOREST_LOCAL_DEV, không cần Supabase) qua mọi trang, không được có lỗi."""
import os

import pytest
from streamlit.testing.v1 import AppTest

PAGES = [
    ("Hôm nay", {}, {}),
    *[("Báo cáo", {"sub": s}, {}) for s in ["Tổng quan", "Tuần", "Tháng", "Năm", "Dự án"]],
    *[("Nhật ký đọc sách", {}, {"rl_view_tabs": s}) for s in ["Tổng quan", "Trích dẫn", "Chi tiết"]],
    *[("Gundam", {}, {"rl_view_tabs_gd": s}) for s in ["Tổng quan", "Chi tiết"]],
    ("Tìm kiếm", {}, {}),
    *[("Tuỳ biến", {"tsub": s}, {}) for s in ["Tổng quan", "Giao diện"]],
]


@pytest.fixture(autouse=True)
def _local_dev(monkeypatch):
    monkeypatch.setenv("FOREST_LOCAL_DEV", "1")
    monkeypatch.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.mark.parametrize("nav,params,state", PAGES, ids=lambda v: v if isinstance(v, str) else None)
def test_page_renders_without_exception(nav, params, state):
    at = AppTest.from_file("../app.py", default_timeout=120)
    at.query_params["nav"] = nav
    for k, v in params.items():
        at.query_params[k] = v
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not [e for e in at.error if "Không kết nối được cơ sở dữ liệu" in e.value]
