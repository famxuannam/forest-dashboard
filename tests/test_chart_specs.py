"""Spec ECharts của các biểu đồ cột (thay Plotly): JSON thuần, xếp chồng thẳng hàng, mốc đúng chỗ.

Các hàm *_spec nạp riêng từ app.py qua tests/_extract.py, phụ thuộc theme/màu do test tự cấp.
"""
import json
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from tests._extract import load_functions

SPEC_FUNCS = [
    "_hsl_hex", "_hex_rgb_str", "_readable_text", "_fmt_hours_short", "_fmt_hours_long", "_top_days",
    "_explode_session_hours", "_compute_eras", "_ec_rgba", "_ec_axis", "_ec_spec", "_ec_stacked_bars",
    "_wide_hours", "_trend_spec", "_single_bars_spec", "_hourly_spec", "_eras_spec",
]


@pytest.fixture(scope="module")
def ns():
    n = {
        "pd": pd, "date": date, "datetime": datetime, "timedelta": timedelta,
        "THEME": {"card": "#ffffff"}, "PLOT_TEXT": "#121722", "IS_DARK": False, "ACCENT_DARK": "#123456",
        "MAC_COLORS": ["#007aff", "#34c759", "#ff9500"],
        "COLOR_MAP": {"Công việc": "#1f4fa8", "Reading": "#d49a00"},
        "BUOI_BANDS": [("Khuya", 0, 5, "rgba(0,0,0,.05)"), ("Sáng", 5, 11, "rgba(0,0,0,.05)"),
                       ("Chiều", 11, 17, "rgba(0,0,0,.05)"), ("Tối", 17, 22, "rgba(0,0,0,.05)"),
                       ("Khuya ", 22, 24, "rgba(0,0,0,.05)")],
        "ERA_BREAK_DAYS": 21, "ERA_NOISE_SHARE": 0.4,
    }
    return load_functions(SPEC_FUNCS, n)


def sessions(rows):
    """rows: (ngày 'YYYY-MM-DD', giờ bắt đầu, phút, Nhóm, Dự án) -> DataFrame giống prep_analysis_data()."""
    out = []
    for d, h, mins, nhom, proj in rows:
        start = pd.Timestamp(f"{d} {h:02d}:00")
        out.append({"Ngày": start.date(), "Thời gian bắt đầu": start,
                    "Thời gian kết thúc": start + pd.Timedelta(minutes=mins), "Thời lượng (Phút)": mins,
                    "Nhóm": nhom, "Dự án": proj, "Tuần": start.strftime('%G-W%V')})
    return pd.DataFrame(out)


def daily_grouped(df, col="Nhóm"):
    g = df.groupby(["Ngày", col])['Thời lượng (Phút)'].sum().reset_index()
    g['Số giờ'] = g['Thời lượng (Phút)'] / 60
    g['Ngày'] = pd.to_datetime(g['Ngày'])
    return g


DF = sessions([
    ("2026-11-05", 9, 60, "Công việc", "Deep work"),   # Thứ Năm
    ("2026-11-05", 20, 30, "Reading", "Beloved"),
    ("2026-11-08", 9, 90, "Reading", "Beloved"),       # Chủ Nhật
    ("2026-11-10", 14, 120, "Công việc", "Deep work"),  # Thứ Ba (kỷ lục 2h)
])


def test_trend_day_spec_is_json_and_stacks_align(ns):
    spec, bars = ns["_trend_spec"](daily_grouped(DF), "Ngày", "Nhóm", ma_df=DF)
    json.dumps(spec)  # st.echarts_chart chỉ nhận JSON thuần
    assert bars == ["Công việc", "Reading"]  # nhiều giờ nhất ở đáy chồng
    bar_series = [s for s in spec["series"] if s["type"] == "bar"]
    # Trục time xếp chồng theo VỊ TRÍ: mọi series cột phải đủ 6 ngày 05..10, cùng thứ tự.
    xs = [[d["value"][0] if isinstance(d, dict) else d[0] for d in s["data"]] for s in bar_series]
    assert xs[0] == xs[1] == [f"2026-11-{i:02d}" for i in range(5, 11)]
    assert all(s["selectedMode"] == "single" and s["stack"] == "total" for s in bar_series)


def test_trend_day_week_divider_and_record(ns):
    spec, _ = ns["_trend_spec"](daily_grouped(DF), "Ngày", "Nhóm", ma_df=DF)
    # Ranh giới tuần: trưa Chủ Nhật 08/11 (giữa cột CN và cột T2 09/11).
    assert spec["series"][0]["markLine"]["data"] == [{"xAxis": "2026-11-08 12:00:00"}]
    names = [s["name"] for s in spec["series"]]
    assert "TB động 7 ngày" in names and "Kỷ lục" in names
    rec = next(s for s in spec["series"] if s["name"] == "Kỷ lục")
    assert rec["data"][0]["value"] == ["2026-11-10", 2.0]
    assert spec["yAxis"]["max"] == pytest.approx(2.0 * 1.18, abs=1e-3)


def test_trend_category_spec_has_total_labels(ns):
    g = DF.groupby(["Tuần", "Nhóm"])['Thời lượng (Phút)'].sum().reset_index()
    g['Số giờ'] = g['Thời lượng (Phút)'] / 60
    spec, bars = ns["_trend_spec"](g, "Tuần", "Nhóm")
    json.dumps(spec)
    assert spec["xAxis"]["type"] == "category" and spec["xAxis"]["data"] == ["2026-W45", "2026-W46"]
    totals = next(s for s in spec["series"] if s["name"] == "Tổng")
    assert [d["name"] for d in totals["data"]] == ["3h", "2h"]


def test_hourly_spec(ns):
    spec, bars = ns["_hourly_spec"](DF, "Nhóm")
    json.dumps(spec)
    assert set(bars) == {"Công việc", "Reading"}
    total = next(s for s in spec["series"] if s["name"] == "Tổng cộng")
    assert len(total["data"]) == 24 and len(total["markArea"]["data"]) == 5
    assert spec["xAxis"]["axisLabel"]["customValues"] == list(range(0, 24, 2))
    assert ns["_hourly_spec"](DF.iloc[0:0], "Nhóm") == (None, [])


def test_single_bars_spec(ns):
    spec = ns["_single_bars_spec"](["Th1", "Th2"], [1.5, 0.0], ["#111111", "rgba(0,0,0,0)"],
                                   lambda l: f"Tháng {l[2:]}")
    json.dumps(spec)
    assert spec["series"][0]["data"][0]["name"] == "Tháng 1 · 1 giờ 30 phút"


def test_eras_spec_segments_cover_axis(ns):
    df = sessions([(f"2024-{m:02d}-10", 9, 120, "Công việc", "Deep work") for m in range(1, 4)]
                  + [(f"2024-{m:02d}-10", 9, 120, "Reading", "Beloved") for m in range(6, 9)])
    eras = ns["_compute_eras"](df, date(2024, 12, 31))
    spec = ns["_eras_spec"](eras)
    json.dumps(spec)
    t0, t1 = spec["xAxis"][0]["min"], spec["xAxis"][0]["max"]
    # Đệm đầu = mốc t0 tuyệt đối, các đoạn sau cộng dồn đúng tới cuối trục.
    total = sum(s["data"][0]["value"] if isinstance(s["data"][0], dict) else s["data"][0]
                for s in spec["series"])
    assert spec["series"][0]["data"] == [t0] and total == t1
    labels = [s["name"] for s in spec["series"] if not s["name"].startswith("_pad")]
    assert labels[0] == "Mùa Công việc" and "Mùa Reading" in labels
    assert any(l.startswith("Khoảng nghỉ") for l in labels)
