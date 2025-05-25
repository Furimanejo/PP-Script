import logging
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class HTTPHandler:
    def __init__(self, values: dict, logger: logging.Logger):
        self._logger = logger.getChild("http")
        self._port = f"{values["port"]}"
        self._paths = {}
        for name, url in values.get("paths", {}).items():
            assert isinstance(url, str)
            self._paths[name] = f"{url}"

    def get(self, path_name):
        url = f"https://127.0.0.1:{self._port}/{self._paths[path_name]}"
        try:
            response = requests.get(url=url, verify=False)
            if 200 <= response.status_code <= 204:
                return {"httpStatus": response.status_code, "data": response.json()}
            return response.json()
        except Exception as e:
            return {"exception": str(e)}
