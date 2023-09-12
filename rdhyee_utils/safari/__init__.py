__all__ = ["Safari", "SafariWindow", "SafariTab"]

import applescript
from appscript import app, k, its

ascript = """
on safari_current_urls()
    tell application "Safari"
        set currentURLs to do JavaScript "Array.from(document.querySelectorAll('a[href]')).map(a => a.href);" in front document
    end tell
end safari_current_urls
"""


class SafariDocument(object):
    def __init__(self, app, rawdoc, window_id=None):
        self.app = app
        self.rawdoc = rawdoc
        self.window_id = window_id

    def __repr__(self):
        return "<SafariDocument: {}>".format(self.name)

    @property
    def name(self):
        return self.rawdoc.name()

    @property
    def modified(self):
        return self.rawdoc.modified()

    @property
    def file(self):
        return self.rawdoc.file()

    def close(self, saving=k.yes, saving_in=None):
        self.rawdoc.close(saving=saving, saving_in=saving_in)

    def save(self, in_=None, as_=None):
        self.rawdoc.save(in_=in_, as_=as_)

    def print_(self, print_dialog=k.yes, with_properties=None):
        self.rawdoc.print_(print_dialog=print_dialog, with_properties=with_properties)


class SafariTab(object):
    def __init__(self, app, window_id, rawtab):
        self.app = app
        self.rawtab = rawtab
        self.window_id = window_id
        self.window = SafariWindow(self.app, self.window_id)

    def __repr__(self):
        return "<SafariTab: {}>".format(self.name)

    @property
    def name(self):
        return self.rawtab.name()

    @property
    def source(self):
        return self.rawtab.source()

    @property
    def url(self):
        return self.rawtab.URL()

    @url.setter
    def url(self, url):
        self.rawtab.URL.set(url)

    @property
    def index(self):
        return self.rawtab.index()

    @property
    def text(self):
        return self.rawtab.text()

    @property
    def visible(self):
        return self.rawtab.visible()

    def activate(self):
        """
        activate the tab: make this tab the current one in the window

        """
        self.window.current_tab = self
        self.app.activate()

    def do_javascript(self, js):
        return self.rawtab.do_JavaScript(js)

    def close(self, saving=k.no, saving_in=None):
        if saving_in is None:
            self.rawtab.close(saving=saving)
        else:
            self.rawtab.close(saving=saving, saving_in=saving_in)


class SafariWindow(object):
    def __init__(self, app, window_id):
        self.app = app
        self.window_id = window_id
        self.rawwindow = self.app.windows.ID(self.window_id).get()

    def __repr__(self):
        return "<SafariWindow: {}>".format(self.name)

    @property
    def id(self):
        return self.window_id

    @property
    def name(self):
        return self.rawwindow.name()

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
    def miniaturizable(self):
        return self.rawwindow.miniaturizable()

    @property
    def miniaturized(self):
        return self.rawwindow.miniaturized()

    @miniaturized.setter
    def miniaturized(self, miniaturized):
        self.rawwindow.miniaturized.set(miniaturized)

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
    def document(self):
        return SafariDocument(self.app, self.rawwindow.document(), self.window_id)

    @property
    def rawtabs(self):
        return self.rawwindow.tabs()

    @property
    def tabs(self):
        return [SafariTab(self.app, self.window_id, t) for t in self.rawwindow.tabs()]

    @property
    def current_tab(self):
        return SafariTab(self.app, self.window_id, self.rawwindow.current_tab())

    @current_tab.setter
    def current_tab(self, tab):
        self.rawwindow.current_tab.set(tab.rawtab)


class Safari:
    def __init__(self, app_name="Safari"):
        self.app = app(app_name)
        self.scpt = applescript.AppleScript(ascript)

    def __repr__(self):
        return "<Safari: {}>".format(self.name())

    @property
    def name(self):
        return self.app.name()

    @property
    def version(self):
        return self.app.version()

    @property
    def frontmost(self):
        return self.app.frontmost()

    @property
    def windows(self):
        return [SafariWindow(self.app, w.id()) for w in self.app.windows()]

    @property
    def tabs(self):
        tabs = []
        for w in self.windows:
            for t in w.tabs:
                tabs.append(t)
        return tabs

    @property
    def documents(self):
        return [w.document for w in self.windows]

    @property
    def current_urls(self):
        return self.scpt.call("safari_current_urls")

    def activate(self):
        self.app.activate()

    def open_url(self, url, window=None, tab=None, activate=True):
        if window is None:
            self.app.make(new=k.document, with_properties={k.URL: url})
        else:
            if tab is None:
                tab = window.make(new=k.tab)
            tab.URL.set(url)
        if activate:
            self.app.activate()
            if tab is not None:
                window.current_tab.set(tab)


def main():
    s = Safari()
    print(s.name)
    for w in s.windows:
        print(w.name)


if __name__ == "__main__":
    main()
