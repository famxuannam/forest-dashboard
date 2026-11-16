"""Cổng đăng nhập Google (mục [auth] trong secrets): giả lập st.user bằng AppTest.user (Streamlit 1.67).

Không bật FOREST_LOCAL_DEV (cờ đó bỏ qua đăng nhập), nên app không có Supabase -- người dùng hợp lệ
đi qua cổng rồi dừng ở thẻ "Chưa cấu hình Supabase", đủ để chứng minh cổng đã cho qua.
"""
import os

import pytest
from streamlit.testing.v1 import AppTest

ALLOWED = "me@example.com"
AUTH_SECRETS = {"auth": {"client_id": "test-client"}, "ALLOWED_EMAIL": ALLOWED}


@pytest.fixture(autouse=True)
def _repo_cwd(monkeypatch):
    monkeypatch.delenv("FOREST_LOCAL_DEV", raising=False)
    monkeypatch.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_app(user, secrets):
    at = AppTest.from_file("../app.py", default_timeout=120)
    at.user = user
    for k, v in secrets.items():
        at.secrets[k] = v
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def errors(at):
    return " ".join(e.value for e in at.error)


def test_logged_out_sees_only_login_button():
    at = run_app({"is_logged_in": False}, AUTH_SECRETS)
    assert [b.label for b in at.button] == ["Đăng nhập bằng Google"]
    assert not at.error


def test_wrong_email_is_rejected():
    at = run_app({"is_logged_in": True, "email": "other@example.com"}, AUTH_SECRETS)
    assert "other@example.com" in errors(at) and "không có quyền truy cập" in errors(at)
    assert [b.label for b in at.button] == ["Đăng xuất"]


def test_missing_allowed_email_blocks_everyone():
    at = run_app({"is_logged_in": True, "email": ALLOWED}, {"auth": {"client_id": "test-client"}})
    assert "thiếu `ALLOWED_EMAIL`" in errors(at)
    assert not at.button


def test_allowed_email_passes_gate():
    at = run_app({"is_logged_in": True, "email": ALLOWED}, AUTH_SECRETS)
    assert "Chưa cấu hình Supabase" in errors(at)
    assert "không có quyền truy cập" not in errors(at)
    assert "Đăng nhập bằng Google" not in [b.label for b in at.button]


def test_local_dev_skips_gate(monkeypatch):
    monkeypatch.setenv("FOREST_LOCAL_DEV", "1")
    at = run_app({"is_logged_in": False}, AUTH_SECRETS)
    assert "Đăng nhập bằng Google" not in [b.label for b in at.button]
    assert not at.error
