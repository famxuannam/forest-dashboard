"""Parser file import (Forest CSV, Reminders Shortcut, Day One JSON, Kindle Clippings)."""
import io
import json

from import_parsers import (parse_dayone_json, parse_forest_csv, parse_kindle_clippings,
                            parse_reading_log_shortcut_csv)


def test_forest_csv_filters_failed_and_unset_and_computes_duration():
    csv = ("Start Time,End Time,Tag,Is Success\n"
           "2026-11-01 09:00:00,2026-11-01 09:50:00,Deep work,True\n"
           "2026-11-01 10:00:00,2026-11-01 10:25:00,Deep work,False\n"
           "2026-11-01 11:00:00,2026-11-01 11:30:00,Unset,True\n"
           "2026-11-01 12:00:00,not-a-date,Reading,True\n")
    df, stats, missing = parse_forest_csv(io.StringIO(csv))
    assert missing == []
    assert list(df["Dự án"]) == ["Deep work"]
    assert list(df["Thời lượng (Phút)"]) == [50]
    assert stats == {"raw": 4, "failed": 1, "unset": 1, "valid": 1}


def test_forest_csv_reports_missing_columns():
    df, _, missing = parse_forest_csv(io.StringIO("Foo,Bar\n1,2\n"))
    assert df is None and set(missing) == {"Dự án", "Thời gian bắt đầu", "Thời gian kết thúc"}


def test_reading_log_title_may_contain_pipes():
    raw = ("list|title|completed_date\n"
           "Toni Morrison - Beloved|Phần 1 | 124 | bản đầy đủ|2026-11-02T08:00:00\n"
           "Gundam - 0079|Tập 1|2026-11-03\n"
           "broken line without pipes\n"
           "Sách|Tiêu đề|not-a-date\n").encode("utf-8")
    df, stats, missing = parse_reading_log_shortcut_csv(io.BytesIO(raw))
    assert missing == []
    assert list(df["Tiêu đề phần"]) == ["Phần 1 | 124 | bản đầy đủ", "Tập 1"]
    assert stats == {"raw": 4, "valid": 2}


def test_reading_log_missing_header():
    _, _, missing = parse_reading_log_shortcut_csv(io.BytesIO(b"a|b\n1|2\n"))
    assert set(missing) == {"list", "title", "completed_date"}


def test_dayone_merges_same_vn_day_and_converts_markdown():
    data = {"entries": [
        # 18:00 UTC ngày 1 = 01:00 giờ VN ngày 2
        {"creationDate": "2026-11-01T18:00:00Z", "text": "**Đậm** và *nghiêng* \\*không\\*"},
        {"creationDate": "2026-11-02T03:00:00Z", "text": "- một\n- hai"},
        {"creationDate": "2026-11-05T03:00:00Z", "text": "![](dayone-moment://abc)"},
    ]}
    result, err = parse_dayone_json(io.StringIO(json.dumps(data)))
    assert err is None
    assert [str(d) for d in result] == ["2026-11-02"]
    html = result[next(iter(result))]
    assert "<strong>Đậm</strong>" in html and "<em>nghiêng</em>" in html and "*không*" in html
    assert "<ul>" in html and "<strong>01:00</strong>" in html and "<strong>10:00</strong>" in html


def test_dayone_rejects_non_dayone_json():
    result, err = parse_dayone_json(io.StringIO('{"foo": 1}'))
    assert result is None and "entries" in err


def test_kindle_clippings_parses_and_skips_bookmarks():
    raw = ("﻿The Dispossessed (Ursula K. Le Guin)\n"
           "- Your Highlight on page 12 | location 183-185 | Added on Monday, 2 November 2026 08:00:00\n\n"
           "You cannot buy the revolution.\n==========\n"
           "The Dispossessed (Ursula K. Le Guin)\n"
           "- Your Bookmark on page 13 | location 190 | Added on Monday, 2 November 2026 08:05:00\n\n\n==========\n"
           "Beloved (Toni Morrison)\n"
           "- Your Note on page 3 | Added on Tuesday, 3 November 2026 09:00:00\n\n"
           "Ghi chú của tôi\n==========\n")
    df, stats = parse_kindle_clippings(raw.encode("utf-8"))
    assert list(df["Loại"]) == ["highlight", "note"]
    assert df.iloc[0]["Tác giả"] == "Ursula K. Le Guin" and df.iloc[0]["Vị trí"] == "183-185"
    assert df.iloc[1]["Vị trí"] == "trang 3"
    assert stats["bookmarks"] == 1 and stats["valid"] == 2
