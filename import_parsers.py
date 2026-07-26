"""Các parser thuần cho dữ liệu import; không đọc/ghi Supabase."""

import json
import re
from html import escape as html_escape
from zoneinfo import ZoneInfo

import pandas as pd


APP_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

def parse_reading_log_shortcut_csv(uploaded):
    """Đọc file do Shortcut "Xuất tiến độ đọc" (xem tab Hướng dẫn) tạo ra -- đây là nguồn DUY
    NHẤT để nạp dữ liệu Đọc sách/Gundam vào app (không còn nhánh CalDAV, vì CalDAV chỉ đọc được
    Reminder List đã lưu trong iCloud, còn Shortcuts đọc thẳng dữ liệu trên máy nên thấy đủ cả
    list "Trên iPhone của tôi"). Định dạng: mỗi dòng "list|title|completed_date" (dấu '|'), dòng đầu là
    header đúng 3 tên cột trên. KHÔNG dùng pd.read_csv(sep='|') vì tiêu đề reminder (vd tiêu đề
    copy nguyên từ 1 video YouTube) có thể tự chứa dấu '|' -- 1 dòng dữ liệu thật đã gặp đúng ca
    này (link ...FULL MOVIE | Daniel Defoe | Classic Literature Adventure - YouTube) khiến
    read_csv 'Expected 3 fields, saw 6' và crash cả file. Tách thủ công: '|' ĐẦU tiên tách
    "list" (tên list tự đặt, không chứa '|'), '|' CUỐI tách "completed_date" (định dạng ngày
    giờ cố định, không chứa '|'), phần CÒN LẠI ở giữa luôn là "title" dù có bao nhiêu dấu '|'.
    Trả về (df, stats, missing_cols) cùng khuôn cột (Ngày hoàn thành, Sách (gốc), Tiêu đề phần)
    mà save_reading_log_bulk() cần -- gọi thẳng hàm đó sau khi người dùng xác nhận, y hệt luồng
    Khôi phục từ bản sao lưu."""
    raw = uploaded.read() if hasattr(uploaded, 'read') else uploaded
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8')
    lines = raw.splitlines()
    cols = ['Ngày hoàn thành', 'Sách (gốc)', 'Tiêu đề phần']
    need = ['list', 'title', 'completed_date']
    if not lines:
        return pd.DataFrame(columns=cols), {'raw': 0, 'valid': 0}, need
    header = [h.strip() for h in lines[0].split('|')]
    missing = [c for c in need if c not in header]
    if missing:
        return pd.DataFrame(columns=cols), {'raw': len(lines) - 1, 'valid': 0}, missing
    rows = []
    for line in lines[1:]:
        if not line.strip() or line.count('|') < 2:
            continue
        book, rest = line.split('|', 1)
        title, completed = rest.rsplit('|', 1)
        rows.append({'Sách (gốc)': book, 'Tiêu đề phần': title, 'Ngày hoàn thành': completed})
    stats = {'raw': len(lines) - 1}
    df = pd.DataFrame(rows, columns=['Sách (gốc)', 'Tiêu đề phần', 'Ngày hoàn thành'])
    df['Ngày hoàn thành'] = pd.to_datetime(df['Ngày hoàn thành'], format='ISO8601', errors='coerce')
    df = df[df['Ngày hoàn thành'].notna() & df['Sách (gốc)'].astype(str).str.strip().ne('')
            & (df['Tiêu đề phần'].astype(str).str.strip() != '')]
    stats['valid'] = len(df)
    return df[cols].reset_index(drop=True), stats, []


def parse_forest_csv(uploaded):
    """Đọc & chuẩn hoá CSV xuất từ Forest. Trả về (df_sạch, stats, missing_cols).
    stats gồm: raw (tổng dòng), failed (phiên thất bại), unset (unset/rỗng), valid (hợp lệ)."""
    df = pd.read_csv(uploaded).rename(columns={
        'Tag': 'Dự án', 'Project': 'Dự án',
        'Start Time': 'Thời gian bắt đầu', 'End Time': 'Thời gian kết thúc'})
    stats = {'raw': len(df), 'failed': 0, 'unset': 0, 'valid': 0}
    if 'Is Success' in df.columns:
        stats['failed'] = int((df['Is Success'] != True).sum())
        df = df[df['Is Success'] == True]
    missing = [c for c in ['Dự án', 'Thời gian bắt đầu', 'Thời gian kết thúc'] if c not in df.columns]
    if missing:
        return None, stats, missing
    df = df.dropna(subset=['Dự án'])
    df['Thời gian bắt đầu'] = pd.to_datetime(df['Thời gian bắt đầu'], errors='coerce')
    df['Thời gian kết thúc'] = pd.to_datetime(df['Thời gian kết thúc'], errors='coerce')
    df = df.dropna(subset=['Thời gian bắt đầu', 'Thời gian kết thúc'])
    _n = len(df)
    df = df[~df['Dự án'].astype(str).str.strip().str.lower().isin(['unset', ''])]
    stats['unset'] = _n - len(df)
    df['Thời lượng (Phút)'] = ((df['Thời gian kết thúc'] - df['Thời gian bắt đầu']).dt.total_seconds() / 60).round().astype(int)
    df = df[['Thời gian bắt đầu', 'Thời gian kết thúc', 'Dự án', 'Thời lượng (Phút)']]
    stats['valid'] = len(df)
    return df, stats, []


_DAYONE_EMBED_RE = re.compile(r'!\[\]\(dayone-moment:[^)]*\)')  # ảnh/video/pdf đính kèm, xem docstring dưới
_DAYONE_ESCAPE_RE = re.compile(r'\\([\\`*_{}\[\]()#+\-.!])')  # markdown escape Day One tự thêm (vd "\.", "\-")
_DAYONE_OL_RE = re.compile(r'^(\t*)(\d+)\.\s+(.*)$')  # dòng list đánh số, \t đầu dòng = mức thụt lề
_DAYONE_UL_RE = re.compile(r'^(\t*)[-*]\s+(.*)$')  # dòng list gạch đầu dòng, cùng quy ước thụt lề


def _dayone_lines_to_blocks(lines):
    """Gộp các dòng list liên tiếp (đánh số "1. ", gạch đầu dòng "- "/"\\* ", thụt lề bằng \\t) thành
    khối <ol>/<ul> THẬT (khớp đúng HTML mà Quill dùng cho list, kể cả class "ql-indent-N" cho thụt
    lề) thay vì chỉ hiện số/gạch đầu dòng như CHỮ THƯỜNG -- xác nhận với người dùng sau khi thấy bản
    đầu (chỉ nối dòng bằng <br>) không ra list "chuẩn" (không thụt lề/định dạng như Quill vẫn dùng
    cho ghi chú viết tay trong app). Dòng KHÔNG khớp list gộp thành 1 đoạn <p> nối bằng <br> như cũ.
    Đổi loại list (ol<->ul) hoặc gặp dòng thường đều TỰ ngắt khối list đang gộp dở, không trộn lẫn
    2 loại vào chung 1 <ol>/<ul>."""
    blocks = []
    buf_type = None  # 'ol' | 'ul' | 'p'
    buf_items = []

    def _flush():
        nonlocal buf_type, buf_items
        if not buf_items:
            return
        if buf_type == 'p':
            blocks.append('<p>' + '<br>'.join(buf_items) + '</p>')
        else:
            lis = ''.join(f'<li class="ql-indent-{lvl}">{txt}</li>' if lvl else f'<li>{txt}</li>'
                          for lvl, txt in buf_items)
            blocks.append(f'<{buf_type}>{lis}</{buf_type}>')
        buf_type, buf_items = None, []

    for line in lines:
        m_ol = _DAYONE_OL_RE.match(line)
        m_ul = None if m_ol else _DAYONE_UL_RE.match(line)
        if m_ol:
            if buf_type != 'ol':
                _flush()
                buf_type = 'ol'
            buf_items.append((len(m_ol.group(1)), m_ol.group(3)))
        elif m_ul:
            if buf_type != 'ul':
                _flush()
                buf_type = 'ul'
            buf_items.append((len(m_ul.group(1)), m_ul.group(2)))
        else:
            if buf_type != 'p':
                _flush()
                buf_type = 'p'
            buf_items.append(line)
    _flush()
    return ''.join(blocks)


def _dayone_text_to_html(text):
    """Chuyển trường "text" (markdown thô, ký tự đặc biệt đã được Day One tự escape bằng "\\") của
    1 entry Day One sang HTML gọn để nhét thẳng vào ô ghi chú Quill, GIỮ ĐÚNG đậm/nghiêng/list. CHỈ
    xử lý CHỮ -- ảnh/video/pdf đính kèm nhúng dạng "![](dayone-moment://...)" bị bỏ hẳn (đúng yêu
    cầu chỉ nhập nội dung chữ, không nhập ảnh/file đính kèm); vị trí/thời tiết nằm ở trường JSON
    riêng, không đọc tới nên không cần lọc ở đây.

    THỨ TỰ xử lý trong mỗi đoạn CỐ Ý: (1) escape HTML thật (&/</>) -- không đụng `\`/`*`/`#`/`[]()`
    nên an toàn làm trước; (2) bỏ link markdown `[chữ](url)` -- chỉ giữ lại phần chữ, bỏ hẳn URL
    (thường là link nội bộ craftdocs://... không mở được ngoài app gốc, không có giá trị gì khi
    nhập vào Ghi chú); (3) heading/**đậm**/*nghiêng* nhận diện dựa vào `*`/`#` KHÔNG có `\` phía
    trước (markdown thật Day One không tự escape) -- làm TRƯỚC bước bỏ escape; (4) bỏ escape (`\.`,
    `\-`, `\*`...) làm SAU CÙNG; (5) tách dòng, gộp list đánh số/gạch đầu dòng liên tiếp thành
    <ol>/<ul> thật qua _dayone_lines_to_blocks() -- PHẢI làm SAU bước (4) vì list gạch đầu dòng
    trong dữ liệu thật của Day One thường bị escape thành "\\- " (xem hàm đó). Đảo ngược thứ tự bước
    (4) lên trước bước (3) sẽ biến 1 dấu `*` thoát nghĩa thật sự (vd chú thích chân trang `*text\*`)
    thành ký tự markdown "trần", bị hiểu nhầm thành in nghiêng (bug đã gặp khi thử với dữ liệu mẫu
    thật -- 1 số câu trích dẫn có dấu `*` cuối câu kiểu chú thích bị tô nghiêng sai). KHÔNG parse
    đầy đủ CommonMark (bảng, list lồng nhiều cấp phức tạp...), đủ dùng cho nhật ký cá nhân chứ không
    cần render y hệt app Day One."""
    if not text:
        return ''
    text = _DAYONE_EMBED_RE.sub('', text)
    text = text.replace('​', '')
    text = text.strip()
    if not text:
        return ''
    html_parts = []
    for para in re.split(r'\n\s*\n', text):
        para = para.strip('\n')
        if not para.strip():
            continue
        para = html_escape(para)
        para = re.sub(r'\[([^\]]*)\]\([^)]*\)', r'\1', para)
        para = re.sub(r'^#{1,6}\s+(.+)$', r'<strong>\1</strong>', para, flags=re.MULTILINE)
        para = re.sub(r'(?<!\\)\*\*(.+?)(?<!\\)\*\*', r'<strong>\1</strong>', para)
        para = re.sub(r'(?<!\\)(?<!\*)\*(?!\*)(.+?)(?<!\\)(?<!\*)\*(?!\*)', r'<em>\1</em>', para)
        para = _DAYONE_ESCAPE_RE.sub(r'\1', para)
        html_parts.append(_dayone_lines_to_blocks(para.split('\n')))
    return ''.join(html_parts)


def parse_dayone_json(uploaded):
    """Đọc file JSON xuất từ Day One (app Day One -> Export -> JSON). Trả về (dict {date: html},
    error_msg). Gộp mọi entry CÙNG NGÀY (theo giờ Việt Nam, quy đổi từ "creationDate" UTC qua
    APP_TZ -- đã đối chiếu với bản xuất Markdown của cùng dữ liệu mẫu để xác nhận quy đổi UTC->giờ
    VN cho ra đúng ngày Day One hiển thị, kể cả entry "cả ngày" không giờ cụ thể) thành 1 khối, mỗi
    entry có nhãn giờ nhỏ để phân biệt nếu 1 ngày có ≥2 entry. CHỈ lấy trường "text" (nội dung chữ)
    -- bỏ hẳn ảnh/video/pdf đính kèm, vị trí, thời tiết (đúng yêu cầu chỉ nhập nội dung chữ)."""
    try:
        data = json.load(uploaded)
    except Exception as e:
        return None, f"File không đúng định dạng JSON: {e}"
    entries = data.get("entries") if isinstance(data, dict) else None
    if entries is None:
        return None, "File JSON không có mục 'entries' -- không giống định dạng Day One xuất ra."
    by_day = {}
    for e in entries:
        cd = e.get("creationDate")
        if not cd:
            continue
        try:
            ts = pd.Timestamp(cd)
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            ts = ts.tz_convert(APP_TZ)
        except Exception:
            continue
        html = _dayone_text_to_html(e.get("text") or "")
        if not html:
            continue
        by_day.setdefault(ts.date(), []).append((ts.strftime("%H:%M"), html))
    result = {}
    for day, parts in by_day.items():
        if len(parts) == 1:
            result[day] = parts[0][1]
        else:
            result[day] = "".join(f"<p><strong>{t}</strong></p>{h}" for t, h in
                                   sorted(parts, key=lambda p: p[0]))
    return result, None

def parse_kindle_clippings(raw):
    """Đọc "My Clippings.txt" (định dạng xuất mặc định của mọi Kindle, xem "Cách xuất Clippings"
    trong tab Hướng dẫn) -- mỗi entry cách nhau bởi 1 dòng đúng 10 dấu "=", gồm: dòng 1 "Tên sách
    (Tác giả)", dòng 2 metadata "- Your Highlight/Note/Bookmark on page X | location Y | Added on
    <ngày giờ>", 1 dòng trống, rồi nội dung (rỗng với Bookmark). Bookmark KHÔNG có nội dung nên bị
    bỏ qua hoàn toàn -- không có gì để hiện làm quote/note. Trả về (df, stats):
    df cột (Tên Kindle, Tác giả, Loại, Nội dung, Vị trí, Ngày thêm); stats = {'raw', 'valid',
    'bookmarks', 'invalid'}."""
    if isinstance(raw, bytes):
        raw = raw.decode('utf-8-sig', errors='replace')
    else:
        raw = raw.lstrip('﻿')
    blocks = [b.strip('\r\n') for b in re.split(r'\r?\n={10}\r?\n?', raw) if b.strip()]
    rows = []
    n_bookmark = n_invalid = 0
    for block in blocks:
        lines = block.splitlines()
        if len(lines) < 2:
            n_invalid += 1
            continue
        title_line, meta_line = lines[0].strip(), lines[1].strip()
        content = "\n".join(lines[2:]).strip()
        m = re.match(r'^(.*)\s+\(([^()]+)\)\s*$', title_line)
        title, author = (m.group(1).strip(), m.group(2).strip()) if m else (title_line, None)
        meta_low = meta_line.lower()
        kind = ('highlight' if 'highlight' in meta_low else 'note' if 'note' in meta_low
                else 'bookmark' if 'bookmark' in meta_low else None)
        if kind is None:
            n_invalid += 1
            continue
        if kind == 'bookmark':
            n_bookmark += 1
            continue
        if not content:
            n_invalid += 1
            continue
        loc_m = re.search(r'location\s+([\d\-]+)', meta_line, re.IGNORECASE)
        page_m = re.search(r'page\s+([\d\-]+)', meta_line, re.IGNORECASE)
        location = loc_m.group(1) if loc_m else (f"trang {page_m.group(1)}" if page_m else None)
        added_m = re.search(r'Added on (.+?)$', meta_line, re.IGNORECASE)
        added_at = pd.to_datetime(added_m.group(1), errors='coerce') if added_m else pd.NaT
        rows.append({'Tên Kindle': title, 'Tác giả': author, 'Loại': kind, 'Nội dung': content,
                     'Vị trí': location, 'Ngày thêm': added_at})
    cols = ['Tên Kindle', 'Tác giả', 'Loại', 'Nội dung', 'Vị trí', 'Ngày thêm']
    df = pd.DataFrame(rows, columns=cols)
    df, n_pen_merged = _collapse_kindle_pen_duplicates(df)
    stats = {'raw': len(blocks), 'valid': len(df), 'bookmarks': n_bookmark, 'invalid': n_invalid,
             'pen_merged': n_pen_merged}
    return df, stats


def _collapse_kindle_pen_duplicates(df):
    """Gộp các highlight "nháp" do tô bằng bút cảm ứng (không phải chọn từ nhanh) sinh ra: Kindle
    ghi lại MỖI LẦN đầu bút dịch chuyển như 1 highlight riêng trong My Clippings.txt, cách nhau vài
    giây, nội dung câu sau luôn là PHẦN MỞ RỘNG (tiền tố + thêm chữ) của câu trước -- chỉ có bản
    CUỐI CÙNG (dài/đầy đủ nhất) mới là highlight thật người dùng muốn giữ, 3-4 bản trước chỉ là
    trạng thái trung gian lúc đang kéo bút. Heuristic: cùng sách + cùng Loại 'highlight' + cách
    nhau tối đa 120 giây + nội dung bản trước là TIỀN TỐ (sau khi rstrip khoảng trắng) của bản sau
    -> coi là 1 chuỗi nháp, chỉ giữ bản dài nhất (luôn là bản cuối chuỗi trong thực tế, nhưng lấy
    max() để chắc chắn không phụ thuộc thứ tự). Ghi chú (Loại 'note') KHÔNG áp dụng -- gõ tay 1 lần
    rồi lưu, không có kiểu nháp tăng dần này. Trả về (df đã gộp, số dòng đã bỏ vì là bản nháp)."""
    if df.empty:
        return df, 0
    keep_mask = pd.Series(True, index=df.index)

    def _flush(cluster):
        if len(cluster) < 2:
            return
        longest = max(cluster, key=lambda i: len(str(df.loc[i, 'Nội dung'])))
        for i in cluster:
            if i != longest:
                keep_mask.loc[i] = False

    for _title, g in df[df['Loại'] == 'highlight'].groupby('Tên Kindle'):
        g = g.sort_values('Ngày thêm', kind='stable')
        cluster = []  # index list của chuỗi nháp đang gộp
        prev_i = None
        for i, row in g.iterrows():
            if prev_i is None:
                cluster = [i]
            else:
                prev_row = df.loc[prev_i]
                gap_ok = (pd.notna(row['Ngày thêm']) and pd.notna(prev_row['Ngày thêm'])
                          and (row['Ngày thêm'] - prev_row['Ngày thêm']).total_seconds() <= 120)
                is_extension = str(row['Nội dung']).startswith(str(prev_row['Nội dung']).rstrip())
                if gap_ok and is_extension:
                    cluster.append(i)
                else:
                    _flush(cluster)
                    cluster = [i]
            prev_i = i
        _flush(cluster)
    n_dropped = int((~keep_mask).sum())
    return df[keep_mask].reset_index(drop=True), n_dropped



