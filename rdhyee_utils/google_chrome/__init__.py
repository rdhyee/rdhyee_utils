__all__ = ["GoogleChrome", "GoogleChromeTab", "GoogleChromeWindow"]

import applescript
from appscript import app, k, its


class GoogleChromeTab(object):
    """
    This won't handle moving a tab from one window to another....
    """

    def __init__(self, gc, window_id, tab_id):
        self.gc = gc
        self.tab_id = tab_id
        self.window_id = window_id
        self.rawwindow = self.gc.windows.ID(self.window_id).get()
        self.rawtab = gc.windows.ID(window_id).tabs.ID(tab_id)

    def __repr__(self):
        return "<ChromeTab: {}>".format(self.title)

    @property
    def id(self):
        return self.tab_id

    def title_md(self):
        return "[{}]({})".format(self.title, self.url)

    @property
    def title(self):
        return self.rawtab.title()

    @property
    def url(self):
        return self.rawtab.URL()

    @url.setter
    def url(self, url):
        self.rawtab.URL.set(url)

    @property
    def index_in_window(self):
        w = self.rawwindow
        for i, tab_ in enumerate(w.tabs()):
            if tab_.id() == self.tab_id:
                return i + 1
        return None

    @property
    def loading(self):
        return self.rawtab.loading()

    def execute(self, js):
        return self.rawtab.execute(js)

    def view_source(self):
        return self.rawtab.view_source()

    def focus(self):
        """
        gc.windows()[0].active_tab_index.set(9)
        """
        index = self.index_in_window
        if index is not None:
            return self.rawwindow.active_tab_index.set(index)
        else:
            return None

    def close(self):
        self.rawtab.close()
        # should mark this as inactive?


class GoogleChromeWindow(object):
    def __init__(self, gc, window_id):
        self.gc = gc
        self.window_id = window_id
        self.rawwindow = self.gc.windows.ID(self.window_id).get()

    def __repr__(self):
        return "Window: {}".format(self.name)

    @property
    def given_name(self):
        return self.rawwindow.given_name()

    @given_name.setter
    def given_name(self, name):
        self.rawwindow.given_name.set(name)

    @property
    def name(self):
        return self.rawwindow.name()

    @property
    def id(self):
        return self.rawwindow.id()

    @property
    def index(self):
        return self.rawwindow.index()

    @index.setter
    def index(self, index):
        self.rawwindow.index.set(index)

    @property
    def bounds(self):
        return self.rawwindow.bounds()

    @bounds.setter
    def bounds(self, bounds):
        self.rawwindow.bounds.set(bounds)

    @property
    def closeable(self):
        return self.rawwindow.closeable()

    @property
    def minimizable(self):
        return self.rawwindow.minimizable()

    @property
    def minimized(self):
        return self.rawwindow.minimized()

    @minimized.setter
    def minimized(self, minimized):
        self.rawwindow.minimized.set(minimized)

    @property
    def resizable(self):
        return self.rawwindow.resizable()

    @property
    def visible(self):
        return self.rawwindow.visible()

    @visible.setter
    def visible(self, visible):
        self.rawwindow.visible.set(visible)

    @property
    def zoomable(self):
        return self.rawwindow.zoomable()

    @property
    def zoomed(self):
        return self.rawwindow.zoomed()

    @zoomed.setter
    def zoomed(self, zoomed):
        self.rawwindow.zoomed.set(zoomed)

    @property
    def active_tab(self):
        tab = self.rawwindow.active_tab()
        return GoogleChromeTab(self.gc, self.window_id, tab.id())

    @property
    def active_tab_index(self):
        return self.rawwindow.active_tab_index()

    @property
    def mode(self):
        return self.rawwindow.mode()

    @property
    def tabs(self):
        tabs = []
        for tab in self.rawwindow.tabs():
            tabs.append(GoogleChromeTab(self.gc, self.window_id, tab.id()))
        return tabs


class GoogleChrome(object):
    def __init__(self, app_name="Google Chrome"):
        self.gc = app(app_name)

    def __repr__(self):
        return "<GoogleChrome: {}>".format(self.name)

    @property
    def name(self):
        return self.gc.name()

    @property
    def frontmost(self):
        return self.gc.frontmost()

    @property
    def version(self):
        return self.gc.version()

    @property
    def windows(self):
        _windows = []
        for w in self.gc.windows():
            _windows.append(GoogleChromeWindow(self.gc, w.id()))
        return _windows

    def window_by_id(self, window_id):
        return self.gc.windows.ID(self.window_id).get()

    def tab_by_id(self, tab_id, window_id=None):
        if window_id is not None:
            return GoogleChromeTab(self.gc, window_id, tab_id)
        else:
            for tab_ in self.tabs():
                if tab_.tab_id == tab_id:
                    return tab_
            return None

    @property
    def tabs(self):
        tabs = []
        for w in self.windows:
            for tab in w.tabs:
                # tabs.append(GoogleChromeTab(self.gc, w.id(), tab.id()))
                tabs.append(tab)
        return tabs
