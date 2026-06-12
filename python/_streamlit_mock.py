"""
Shared Streamlit mock module for CLI scripts that import from lp_v130_app.

Must be imported BEFORE any lp_v130_app imports, as it sets
sys.modules['streamlit'] so that `import streamlit as st` inside
lp_v130_app resolves to the mock instead of the real library.

Usage (at the top of a CLI script, before any lp_v130_app imports):
    from _streamlit_mock import st_mock
"""

import sys


class _MockCtx:
    """Proper context manager for mocking with/with-as statements."""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def __call__(self, *a, **kw):
        return self
    def __getattr__(self, name):
        return self  # Chain any attribute access
    def __bool__(self):
        return False


class _MockST:
    """Universal mock for all Streamlit calls. Returns self for chaining."""
    def __call__(self, *a, **kw):
        return _MOCK_RETURN
    def __enter__(self):
        return _MOCK_RETURN
    def __exit__(self, *a):
        return False
    def __getattr__(self, name):
        # Special return values for specific methods
        if name == 'file_uploader':
            return lambda *a, **kw: None
        if name == 'button':
            return lambda *a, **kw: False
        if name == 'tabs':
            return lambda *a: [_MOCK_RETURN] * len(a)
        if name == 'columns':
            return lambda *a: [_MOCK_RETURN] * (a[0] if a else 1)
        if name == 'progress':
            return lambda *a, **kw: _MockCtx()
        if name == 'session_state':
            return _MOCK_SESSION_STATE
        if name == 'sidebar':
            return _MOCK_SIDEBAR
        if name == 'cache_data':
            return lambda f: f
        if name == 'cache_resource':
            return lambda f: f
        if name == 'empty':
            return lambda: _MOCK_RETURN
        if name == 'spinner':
            def _spinner(*a, **kw):
                if a and callable(a[0]):
                    return a[0]
                return _MockCtx()
            return _spinner
        if name == 'expander':
            return lambda *a, **kw: _MockCtx()
        if name == 'write_stream':
            return lambda *a, **kw: _MockCtx()
        return _MOCK_RETURN

class _MockSessionState(dict):
    """Dict that also supports attribute access (like streamlit's session_state)."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)
    def __setattr__(self, name, value):
        self[name] = value
    def __delattr__(self, name):
        try:
            del self[name]
        except KeyError:
            raise AttributeError(name)


_MOCK_RETURN = _MockST()
_MOCK_SESSION_STATE = _MockSessionState({
    'draws': [],
    'predictor': None,
    'bayes': None,
    'accuracy_history': [],
    'last_pred': None,
    'last_all_preds': None,
    'trained': False,
    'log_lines': [],
    'training_running': False,
    'model_report_data': [],
    'training_time': 0.0,
    '_last_upload_hash': None,
    'draws_raw': [],
})
_MOCK_SIDEBAR = _MockST()

st_mock = _MockST()
st_mock.set_page_config = lambda **kw: None
st_mock.session_state = _MOCK_SESSION_STATE
st_mock.sidebar = _MOCK_SIDEBAR
st_mock.tabs = lambda *a: [_MOCK_RETURN] * len(a[0]) if a and isinstance(a[0], (list, tuple)) else [_MOCK_RETURN] * len(a)
st_mock.columns = lambda *a: [_MOCK_RETURN] * (a[0] if a else 1)
st_mock.progress = lambda *a, **kw: _MockCtx()
st_mock.metric = lambda *a, **kw: None
st_mock.divider = lambda: None
st_mock.success = lambda *a, **kw: None
st_mock.warning = lambda *a, **kw: None
st_mock.info = lambda *a, **kw: None
st_mock.error = lambda *a, **kw: None
st_mock.spinner = lambda *a: (lambda f: f) if (a and callable(a[0])) else _MockCtx()
st_mock.expander = lambda *a, **kw: _MockCtx()
st_mock.write_stream = lambda *a, **kw: _MockCtx()
st_mock.dataframe = lambda *a, **kw: None
st_mock.download_button = lambda *a, **kw: None
st_mock.caption = lambda *a, **kw: None
st_mock.subheader = lambda *a, **kw: None
st_mock.header = lambda *a, **kw: None
st_mock.title = lambda *a, **kw: None
st_mock.write = lambda *a, **kw: None
st_mock.code = lambda *a, **kw: None
st_mock.empty = lambda: _MOCK_RETURN
st_mock.pyplot = lambda *a, **kw: None
st_mock.plotly_chart = lambda *a, **kw: None
st_mock.cache_data = lambda f: f
st_mock.cache_resource = lambda f: f
st_mock.file_uploader = lambda *a, **kw: None
st_mock.button = lambda *a, **kw: False
st_mock.tabs = lambda *a: [_MOCK_RETURN] * len(a[0]) if a and isinstance(a[0], (list, tuple)) else [_MOCK_RETURN] * len(a)
st_mock.columns = lambda *a: [_MOCK_RETURN] * (a[0] if a else 1)
st_mock.number_input = lambda *a, **kw: 0
st_mock.selectbox = lambda *a, **kw: None
st_mock.checkbox = lambda *a, **kw: False
st_mock.radio = lambda *a, **kw: a[1][0] if a and len(a) > 1 else None
st_mock.text_area = lambda *a, **kw: ''
st_mock.text_input = lambda *a, **kw: ''
st_mock.slider = lambda *a, **kw: a[2] if len(a) > 2 else 0
st_mock.date_input = lambda *a, **kw: None
st_mock.color_picker = lambda *a, **kw: '#000000'
st_mock.toggle = lambda *a, **kw: False
st_mock.time_input = lambda *a, **kw: None

# Register mock so that `import streamlit` inside lp_v130_app resolves here
sys.modules['streamlit'] = st_mock
