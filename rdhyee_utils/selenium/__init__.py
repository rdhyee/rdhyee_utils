import datetime
import json
import re
import time
import os

import selenium

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait


def selenium_driver(browser="firefox", headless=False, profile=None):

    CHROME_DATA_DIR = os.environ.get(
        "CHROME_DATA_DIR", "/Users/raymondyee/Library/Application Support/Google/Chrome"
    )
    FIREFOX_BINARY = os.environ.get(
        "FIREFOX_BINARY", "/Applications/Firefox.app/Contents/MacOS/firefox-bin"
    )
    FIREFOX_PATH = os.environ.get(
        "FIREFOX_PATH", "/Users/raymondyee/D/Document/selenium/geckodriver"
    )
    CHROMEDRIVER_PATH = os.environ.get(
        "CHROMEDRIVER_PATH", "/Users/raymondyee/D/Document/selenium/chromedriver"
    )

    if browser == "firefox":
        # binary = webdriver.firefox.firefox_binary.FirefoxBinary(firefox_path=FIREFOX_BINARY)
        firefox_capabilities = DesiredCapabilities.FIREFOX
        firefox_capabilities["binary"] = FIREFOX_BINARY

        firefox_options = webdriver.firefox.options.Options()
        firefox_options.headless = headless
        driver = webdriver.Firefox(
            capabilities=firefox_capabilities,
            executable_path=FIREFOX_PATH,
            options=firefox_options,
            firefox_profile=profile,
        )
    elif browser == "phantomjs":
        driver = webdriver.PhantomJS()
        # https://github.com/detro/ghostdriver/issues/269
        # need to set a reasonable size screen
        driver.set_window_size(1600, 1200)
    elif browser == "chrome":
        chrome_options = webdriver.ChromeOptions()
        if profile:
            # chrome_options.add_argument('--profile-directory={}'.format(profile))
            chrome_options.add_argument("no-sandbox")
            chrome_options.add_argument("user-data-dir={}".format(CHROME_DATA_DIR))
            chrome_options.add_argument("profile-directory={}".format(profile))
            # chrome_options.add_argument('user-data-dir={}'.format(profile))
        chrome_options.headless = headless
        driver = webdriver.Chrome(
            executable_path=CHROMEDRIVER_PATH, options=chrome_options
        )

    else:
        raise Exception("browser {} not acceptable".format(browser))

    return driver


def find_element(sel, selector, selector_type="css", timeout=20):

    if selector_type == "css":
        return WebDriverWait(sel, timeout).until(
            lambda d: d.find_element_by_css_selector(selector)
        )
    elif selector_type == "xpath":
        return WebDriverWait(sel, timeout).until(
            lambda d: d.find_element_by_xpath(selector)
        )


def find_elements(sel, selector, selector_type="css", timeout=20):

    if selector_type == "css":
        return WebDriverWait(sel, timeout).until(
            lambda d: d.find_elements_by_css_selector(selector)
        )
    elif selector_type == "xpath":
        return WebDriverWait(sel, timeout).until(
            lambda d: d.find_elements_by_xpath(selector)
        )


def fill_in(sel, selector, value, selector_type="css"):
    if selector_type == "css":
        return sel.execute_script(
            """document.querySelector("{}").value="{}";""".format(selector, value)
        )
    else:
        return None


def test_wikimedia_commons(browser="Firefox"):

    sel = selenium_driver(browser)
    sel.get("https://en.wikipedia.org/wiki/Main_Page")

    commons_link = sel.find_element_by_xpath('//a[text()="Commons"]')
    print((sel.current_url))

    sel.quit()
    assert commons_link.get_attribute("href") == "https://commons.wikimedia.org/"


def test_se(browser="chrome", headless=False):
    sel = selenium_driver(browser=browser, headless=headless)
    sel.get("https://raymondyee.net")

    print((sel.current_url))

    time.sleep(10)
    sel.quit()
