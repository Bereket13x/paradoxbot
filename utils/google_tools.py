import base64
import contextlib
import re
import time
from datetime import datetime
import requests

class chromeDriver:
    @staticmethod
    def start_driver():
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from selenium.webdriver.chrome.service import Service as ChromeService
            from webdriver_manager.chrome import ChromeDriverManager

            chrome_options = ChromeOptions()
            chrome_options.add_argument("--ignore-certificate-errors")
            chrome_options.add_argument("--test-type")
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920x1080")
            chrome_options.add_argument("--disable-gpu")
            prefs = {"download.default_directory": "./temp"}
            chrome_options.add_experimental_option("prefs", prefs)
            
            service = ChromeService(executable_path=ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            return driver, None
        except Exception as err:
            return None, str(err)

    @staticmethod
    def bypass_cache(inputstr, driver=None):
        from selenium.webdriver.common.by import By
        if driver is None:
            driver, error = chromeDriver.start_driver()
            if not driver:
                return None, error
        driver.get(inputstr)
        if "google" in inputstr:
            with contextlib.suppress(Exception):
                driver.find_element(By.ID, "L2AGLb").click()
            with contextlib.suppress(Exception):
                driver.find_element(
                    By.XPATH, "//button[@aria-label='Accept all']"
                ).click()
        return driver, None

    @staticmethod
    def get_html(inputstr):
        driver, error = chromeDriver.bypass_cache(inputstr)
        if not driver:
            return None, error
        html = driver.page_source
        driver.close()
        return html, None

    @staticmethod
    async def get_screenshot(inputstr, event=None):
        start = datetime.now()
        driver, error = chromeDriver.bypass_cache(inputstr)
        if not driver:
            return None, error
        if event:
            await event.edit("`Calculating Page Dimensions with Google Chrome BIN`")
        height = driver.execute_script(
            "return Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);"
        )
        width = driver.execute_script(
            "return Math.max(document.body.scrollWidth, document.body.offsetWidth, document.documentElement.clientWidth, document.documentElement.scrollWidth, document.documentElement.offsetWidth);"
        )
        driver.set_window_size(width + 100, height + 100)
        im_png = driver.get_screenshot_as_png()
        if event:
            await event.edit("`Stoppping Chrome Bin`")
        driver.close()
        end = datetime.now()
        ms = (end - start).seconds
        return im_png, f"**url : **{inputstr} \n**Time :** `{ms} seconds`"


class GooglePic:
    def __init__(self, image, site):
        self.image = image
        self.site = site

    def __hash__(self):
        return hash(self.image + self.site)

    @staticmethod
    def __title_fetch__(html):
        title = ""
        pattern1 = re.compile(r"Image search ([^\"]+)")
        pattern2 = re.compile(r"\[\"(.*?)(?=\",null,\[\[\"ROSTI\")")
        if match := pattern1.search(html):
            title = match[1]
        elif match := pattern2.search(html):
            title = match[1]
        return "Visual matches" if (len(title) > 100 or not title) else title

    @staticmethod
    def reverse_data(image_filename, flag=False):
        data = {
            "title": None,
            "lens": None,
            "google": None,
            "image_set": None,
            "error": None,
        }
        with open(image_filename, mode="rb") as f:
            url = f"https://lens.google.com/upload?ep=ccm&s=&st={int(time.time())}"
            try:
                res1 = requests.post(url, files={"encoded_image": f})
                if res1.ok:
                    data["lens"] = re.search(r"https?://[^\"]+", res1.text).group()
                    res2 = requests.get(data["lens"])
                    if res2.ok:
                        html = res2.text.encode().decode("unicode_escape")
                        with contextlib.suppress(Exception):
                            data["google"] = re.search(
                                r"https://www.google.com/search\?tbs.+?(?=\")", html
                            ).group()
                        if not data["google"]:
                            html, data["error"] = chromeDriver.get_html(data["lens"])
                            html = html.encode().decode("unicode_escape")
                            data["google"] = re.search(
                                r"https://www.google.com/search\?tbs.+?(?=\")", html
                            ).group()
                    if html:
                        if flag:
                            data["image_set"] = set()
                            for link in re.findall(
                                r"https://www.google.com/imgres\?imgurl.+?(?=\")", html
                            ):
                                image = re.search(r"imgurl=(.+?)&", link)[1]
                                site = re.search(r"imgrefurl=(.+?)&", link)[1]
                                if image.endswith(
                                    (".jpg", ".jpeg", ".png", ".gif")
                                ) or site.endswith((".jpg", ".jpeg", ".png", ".gif")):
                                    data["image_set"].add(GooglePic(image, site))
                        data["title"] = GooglePic.__title_fetch__(html)
            except Exception as error:
                data["error"] = str(error)
        return data
