"""Nạp riêng vài hàm thuần/tầng dữ liệu từ app.py để test mà không chạy cả app Streamlit.

app.py là 1 script chạy từ trên xuống (gọi Supabase, vẽ UI ngay khi import), nên không import thẳng
được. Ở đây parse AST, chỉ lấy đúng các `def` cần test rồi exec trong 1 namespace riêng, các
phụ thuộc (Supabase client, cache loader) do test tự cung cấp.
"""
import ast
import pathlib

APP = pathlib.Path(__file__).resolve().parent.parent / "app.py"


class CacheStub:
    """Thay cho 1 loader @st.cache_data: gọi được, có .clear(), đếm số lần clear."""

    def __init__(self, fn=None):
        self.fn, self.cleared = fn, 0

    def __call__(self, *a, **k):
        return self.fn(*a, **k)

    def clear(self):
        self.cleared += 1


def load_functions(names, namespace):
    tree = ast.parse(APP.read_text(encoding="utf-8"))
    nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
    missing = set(names) - {n.name for n in nodes}
    assert not missing, f"không tìm thấy trong app.py: {missing}"
    for n in nodes:
        n.decorator_list = []  # bỏ @st.cache_data/@st.fragment -- test tự cấp stub
    exec(compile(ast.Module(body=nodes, type_ignores=[]), str(APP), "exec"), namespace)
    return namespace
