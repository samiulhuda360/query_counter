from celery import Celery
import requests
from bs4 import BeautifulSoup
import time


app = Celery('tasks', broker='redis://redis:6379', backend='redis://redis:6379')

proxies = {
    "http": "http://letezcbn-rotate:6792gwkuo8oo@p.webshare.io:80/",
    "https": "http://letezcbn-rotate:6792gwkuo8oo@p.webshare.io:80/"
}


@app.task
def scrape_website(url, keyword):
    try:
        # Introduce a delay of 5 seconds before each request
        time.sleep(5)
        response = requests.get(url, proxies=proxies)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        h1_count = sum(keyword.lower() in h1.get_text().lower() for h1 in soup.find_all('h1'))
        h2_count = sum(keyword.lower() in h2.get_text().lower() for h2 in soup.find_all('h2'))
        body_count = soup.get_text().lower().count(keyword.lower())
        return h1_count, h2_count, body_count
    except requests.exceptions.RequestException as e:
        print(f"Error occurred while scraping the website: {e}")
        return "?", "?", "?"