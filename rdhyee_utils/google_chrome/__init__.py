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
        self.window = self.gc.windows.ID(self.window_id).get()
        self.rawtab = gc.windows.ID(window_id).tabs.ID(tab_id)

    def id(self):
        return self.tab_id

    def title_md(self):
        return "[{}]({})".format(self.rawtab.title(), self.rawtab.URL())

    def title(self):
        return self.rawtab.title()

    def url(self):
        return self.rawtab.URL()

    def index_in_window(self):
        w = self.window
        for (i, tab_) in enumerate(w.tabs()):
            if tab_.id() == self.tab_id:
                return i + 1
        return None

    def loading(self):
        return self.rawtab.loading()

    def focus(self):
        """
        gc.windows()[0].active_tab_index.set(9)
        """
        index = self.index_in_window()
        if index is not None:
            return self.window.active_tab_index.set(index)
        else:
            return None

    def close(self):
        self.rawtab.close()
        # should mark this as inactive?

    def __repr__(self):
        return "Tab: {}".format(self.rawtab.title())


class GoogleChromeWindow(object):
    def __init__(self, gc, window_id):
        self.gc = gc
        self.window_id = window_id
        self.rawwindow = self.gc.windows.ID(self.window_id).get()

    def name(self):
        return self.rawwindow.name()

    def id(self):
        return self.rawwindow.id()

    def tabs(self):
        for tab in self.rawwindow.tabs():
            yield GoogleChromeTab(self.gc, self.window_id, tab.id())

    def bounds(self):
        return self.rawwindow.bounds()

    def closeable(self):
        return self.rawwindow.closeable()

    def minimizable(self):
        return self.rawwindow.minimizable()

    def minimized(self):
        return self.rawwindow.minimized()

    def resizable(self):
        return self.rawwindow.resizable()

    def visible(self):
        return self.rawwindow.visible()

    def zoomable(self):
        return self.rawwindow.zoomable()

    def zoomed(self):
        return self.rawwindow.zoomed()

    def active_tab(self):
        return self.rawwindow.active_tab()

    def active_tab_index(self):
        return self.rawwindow.active_tab_index()

    def mode(self):
        return self.rawwindow.mode()

    def __repr__(self):
        return "Window: {}".format(self.name())


class GoogleChrome(object):
    def __init__(self, app_name="Google Chrome"):
        self.gc = app(app_name)

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

    def tabs(self):
        for w in self.windows():
            for tab in w.tabs():
                yield GoogleChromeTab(self.gc, w.id(), tab.id())