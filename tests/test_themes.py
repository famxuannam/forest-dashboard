"""Kiểm tra tính nhất quán của bộ theme Gundam (ui_catalog.GUNDAM_THEMES)."""
import ui_catalog as u

_REQUIRED = {"name", "era", "mode", "font", "pattern", "cut", "radius", "bg", "card", "chip", "border",
             "text", "text-2", "text-3", "text-4", "accent", "on-accent", "trim", "trim2", "chart", "note"}


def _lum(hexcode):
    h = hexcode.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contrast(a, b):
    la, lb = _lum(a), _lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_default_theme_is_first_and_rx78():
    assert u.DEFAULT_THEME == "RX-78-2"
    assert next(iter(u.GUNDAM_THEMES)) == u.DEFAULT_THEME


def test_every_theme_is_complete_and_valid():
    for key, th in u.GUNDAM_THEMES.items():
        assert _REQUIRED <= set(th), key
        assert th["mode"] in ("light", "dark"), key
        assert th["font"] in u.BODY_FONTS, key
        assert th["pattern"] in u.THEME_PATTERNS, key
        assert len(th["chart"]) >= 6, key
        assert len(set(th["chart"])) == len(th["chart"]), key


def test_text_and_accent_contrast():
    for key, th in u.GUNDAM_THEMES.items():
        assert _contrast(th["text"], th["card"]) >= 7, key
        assert _contrast(th["text-3"], th["card"]) >= 4.5, key
        assert _contrast(th["on-accent"], th["accent"]) >= 4.5, key


def test_tokens_cover_css_vars():
    tok = u.theme_tokens(u.GUNDAM_THEMES[u.DEFAULT_THEME])
    for name in ("bg", "card", "card-tl", "border", "divider", "divider-2", "divider-on-bg", "chip", "text",
                 "text-2", "text-3", "text-4", "text-on-bg", "text-on-bg-2", "on-accent", "trim", "trim2"):
        assert name in tok
    cv = u.theme_card_vars(u.GUNDAM_THEMES[u.DEFAULT_THEME])
    assert cv["corner_shape"] == "bevel"
