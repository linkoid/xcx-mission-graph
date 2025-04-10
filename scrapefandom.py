import sys
import traceback
import urllib.parse
import requests
import requests_cache
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import OrderedDict
from bs4 import BeautifulSoup

from missions import Mission, Hyperlink, MissionsDAO

base_url = 'https://xenoblade.fandom.com/'

def make_session():
    return requests_cache.CachedSession('.requests_cache', ignored_parameters=['Cookie'])
session = make_session()

def request_soup(url: str | bytes, session_: requests.Session = ...):
    if '://' not in url:
        url = urllib.parse.urljoin(base_url, url)
    if session_ is ...:
        session_ = session
    response = session_.get(url, timeout=5)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'lxml')
    return soup

def scrape_category_page_links(url: str | bytes):
    soup = request_soup(url)
    links: OrderedDict[str, str] = OrderedDict()
    for a in soup.find_all('a', class_='category-page__member-link'):
        links[a['href']] = a['title']
    return links

def scrape_subcategory_page_links(url: str | bytes):
    subcategory_pages = scrape_category_page_links(url)
    
    extra_subcategory_pages = {}
    for subcategory_page_url in subcategory_pages.keys():
        extra_subcategory_pages.update(scrape_category_page_links(subcategory_page_url))
    subcategory_pages.update(extra_subcategory_pages)
    
    links: OrderedDict[str, str] = OrderedDict()
    for subcategory_page_url, title in subcategory_pages.items():
        if not title.startswith('Category:'):
            continue
        links.update(scrape_category_page_links(subcategory_page_url))
    return links

def scrape_mission(url: str | bytes):
    return Mission.request(url, timeout=5, session=session)

def scrape_all_missions(slice_=slice(None, None), *, log=False):
    mission_links = scrape_subcategory_page_links('https://xenoblade.fandom.com/wiki/Category:XCX_Missions')
    for mission_url, mission_title in [*mission_links.items()][slice_]:
        mission = scrape_mission(mission_url)
        if mission is None:
            continue
        if log:
            try:
                #print(f'{mission!r} "{mission.name}"')
                print(mission.details())
            except:
                print(f'{traceback.format_exc()}{mission!r}:\n{mission._info_box}', file=sys.stderr)
        yield (mission_title, mission)

def scrape_all_missions_concurrent(slice_=slice(None), *, max_workers=5, log=False):
    mission_links = scrape_subcategory_page_links('https://xenoblade.fandom.com/wiki/Category:XCX_Missions')
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        tasks = { executor.submit(scrape_mission, mission_url): mission_title
                  for mission_url, mission_title in [*mission_links.items()][slice_] }
        for task in as_completed(tasks):
            mission: Mission = task.result()
            if mission is None:
                continue
            if log:
                try:
                    #print(f'{mission!r} "{mission.name}"')
                    print(mission.details())
                except:
                    print(f'{traceback.format_exc()}{mission!r}:\n{mission._info_box}', file=sys.stderr)
            yield (tasks[task], mission)

if __name__ == '__main__':
    scrape_all_missions(log=True)
