import requests


def get_http_session():
    http = requests.session()
    try:
        yield http
    finally:
        http.close()
