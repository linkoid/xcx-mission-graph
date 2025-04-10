import sqlite3
import urllib.parse
import requests
import requests_cache
from bs4 import BeautifulSoup, PageElement, SoupStrainer, Tag

_base_url = 'https://xenoblade.fandom.com/'

class Hyperlink:
    def __init__(self, element):
        self._element = element

    @property
    def href(self) -> str:
        return self._element['href']

    @property
    def title(self) -> str:
        return self._element['title']

    @property
    def string(self) -> str:
        return self._element.string

    def __repr__(self):
        return repr(self._element)
        #return f'<Mission "{self.name}">'

class Mission:
    @staticmethod
    def request(url: str | bytes, *, timeout=-1, session: requests.Session = ...) -> 'Mission | None':
        info_box = Mission._try_get_infobox(url, timeout=timeout, session=session)
        if info_box is None:
            return None
        return Mission(url, info_box=info_box)

    @staticmethod
    def _try_get_infobox(url: str | bytes, *, timeout=-1, session: requests.Session = None):
        if '://' not in url:
            url = urllib.parse.urljoin(_base_url, url)
        if session is None:
            response = requests.get(url, timeout=timeout)
        else:
            response = session.get(url, timeout=timeout)
        response.raise_for_status()
        mission_strainer = SoupStrainer('div', class_='xcx mission')
        soup = BeautifulSoup(response.content, 'lxml', )
        return soup.find(mission_strainer)

    def __init__(self, url: str | bytes, *, info_box: str | BeautifulSoup = ...):
        if info_box is ...:
            info_box = Mission._try_get_infobox(url)
        if info_box is None:
            raise ValueError(f"'info_box' cannot be None and could not be found in '{url}'")
        self._href = urllib.parse.urlparse(url).path
        self._info_box = BeautifulSoup(str(info_box), 'lxml')

    def _get_data_value(self, data_source: str):
        tag = self._info_box.find('div', {'data-source': data_source}, class_='pi-data')
        if tag is None:
            return None
        pi_data_value = tag.find('div', class_='pi-data-value')
        if pi_data_value is None:
            return None
        a = pi_data_value.find('a')
        return Hyperlink(a) if a is not None else str(pi_data_value.get_text().strip())

    @property
    def href(self):
        return self._href

    @property
    def name(self):
        return self._info_box.find('h2', {'data-source': 'name'}).get_text()

    @property
    def type(self):
        nav = self._info_box.find('nav')
        return nav.get_text().strip() if nav else None

    @property
    def summary(self):
        return self._get_data_value('summary')

    @property
    def client(self):
        return self._get_data_value('client')

    @property
    def location(self):
        return self._get_data_value('location')

    @property
    def difficulty(self):
        value = self._get_data_value('difficulty')
        return value.strip('-').strip() if value else value

    @property
    def prereqs(self):
        div = self._info_box.find('div', {'data-source': 'prereqs'})
        div = div.find('div') if div is not None else None
        if div is None:
            return None
        return [ Prerequisite(x.strip())
                 for x in bytes.decode(div.renderContents(encoding='utf8'), encoding='utf8').split('<br/>') ]

    def __repr__(self):
        return f"Mission('{self.href}')"
        #return f'<Mission "{self.name}">'

    def details(self):
        return \
f"""Mission('{self.href}')
    name: {self.name}
    type: {self.type}
    summary: {self.summary}
    client: {self.client}
    location: {self.location}
    difficulty: {self.difficulty}
    prereqs: {[str(x) for x in self.prereqs]}
"""

class Prerequisite:
    def __init__(self, html: str):
        element: 'Any' = BeautifulSoup(html, 'lxml')
        self._element: Tag = element
        if not isinstance(self._element, Tag):
            self._element = Tag()

    def _single_a(self):
        all_a = self._element.find_all('a')
        if len(all_a) != 1:
            return None
        return all_a[0]

    @property
    def href(self):
        a = self._single_a()
        return str(a['href']) if a else None

    @property
    def title(self):
        a = self._single_a()
        return str(a['title']) if a else None

    @property
    def text(self):
        return self._element.text
    
    @property
    def is_mission(self):
        a = self._single_a()
        if a is None:
            return False
        return self._element.text == a.text

    def __str__(self):
        return self.text

    def __repr__(self):
        return f'Prerequisite(\'{self._element!r}\')'


class MissionsDAO:
    def __init__(self):
        _setup_database()
        self.connection = sqlite3.connect('missions.sqlite')
    def __enter__(self):
        return self
    def __exit__(self, a, b, c):
        self.connection.close()

_did_setup = False
def _setup_database():
    global _did_setup
    if _did_setup:
        return
    _did_setup = True
    
    connection = sqlite3.connect('missions.sqlite')
    cursor = connection.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hyperlinks (
            href VARCHAR(255) PRIMARY KEY,
            title TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS missions (
            url VARCHAR(255) PRIMARY KEY,
            name TEXT,
            type TEXT,
            summary TEXT,
            client VARCHAR(255),
            location VARCHAR(255),
            difficulty TEXT,
            prereqs_text TEXT,
            
            FOREIGN KEY (client) REFERENCES hyperlinks(href),
            FOREIGN KEY (location) REFERENCES hyperlinks(href)
        )
    ''')

if __name__ == '__main__':
    _setup_database()
