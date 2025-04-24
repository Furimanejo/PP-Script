from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import InvalidSessionIdException


class WebDetection:
    def __init__(self):
        options = webdriver.ChromeOptions()
        # options.page_load_strategy = "eager"
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
        )
        options.add_argument("--no-sandbox")
        options.add_argument("--log-level=3")
        options.add_argument("--start-minimized")
        options.add_argument("--disable-notifications")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--disable-gpu")

        # open driver
        self.driver = webdriver.Chrome(options=options)

    def terminate(self):
        self.driver.close()

    def open_url(self, url):
        self.driver.get(url)

    def get_elements_from_xpath(self, xpath, parent_element=None):
        try:
            if parent_element:
                return parent_element.find_elements(By.XPATH, xpath)
            return self.driver.find_elements(By.XPATH, xpath)
        except InvalidSessionIdException:
            return []

    def get_attribute_from_element(self, attribute, element):
        return element.get_attribute(attribute)

    def move_to_element(self, element):
        ActionChains(self.driver).move_to_element(element).perform()
