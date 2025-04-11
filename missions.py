import copy
import urllib.parse
import requests
import requests_cache
from bs4 import BeautifulSoup, PageElement, SoupStrainer, Tag
from bs4.builder._lxml import LXMLTreeBuilder


_base_url = 'https://xenoblade.fandom.com/'
_builder = LXMLTreeBuilder()

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
        soup = BeautifulSoup(response.content, builder=_builder)
        return soup.find(mission_strainer)

    def __init__(self, url: str | bytes, *, info_box: Tag = ...):
        if info_box is ...:
            info_box = Mission._try_get_infobox(url)
        if info_box is None:
            raise ValueError(f"'info_box' cannot be None and could not be found in '{url}'")
        self._href = urllib.parse.urlparse(url).path
        self._info_box = copy.deepcopy(info_box)

    def _get_data_value_div(self, data_source: str):
        tag = self._info_box.find('div', {'data-source': data_source}, class_='pi-data')
        if tag is None:
            return None
        pi_data_value = tag.find('div', class_='pi-data-value')
        return pi_data_value

    def _get_data_value(self, data_source: str):
        pi_data_value = self._get_data_value_div(data_source)
        if pi_data_value is None:
            return None
        a = pi_data_value.find('a')
        return Hyperlink(a) if a is not None else str(pi_data_value.get_text().strip())

    def _get_data_value_list(self, data_source: str):
        div = self._get_data_value_div(data_source)
        if div is None:
            return
        temp_div = None
        for child in div.contents:
            if isinstance(child, Tag) and child.name == 'br':
                if temp_div is not None:
                    yield temp_div
                temp_div = None
                continue
            if temp_div is None:
                temp_div = div.copy_self()
            temp_div.append(copy.deepcopy(child))
        if temp_div is not None:
            yield temp_div

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
    def required(self):
        div = self._get_data_value_div('required')
        if div is None:
            return []
        return [ Hyperlink(a) for a in div.find_all('a') ]

    @property
    def leadsto(self):
        return self._get_data_value('leadsto')

    @property
    def prereqs(self):
        client = self.client
        return [ Prerequisite(element, client) for element in self._get_data_value_list('prereqs') ]

    @property
    def rewards(self):
        client = self.client
        return [ Reward(element, client) for element in self._get_data_value_list('rewards') ]

    @property
    def embed(self):
        embed = copy.deepcopy(self._info_box)
        h2 = embed.find('h2', {'data-source': 'name'})
        BeautifulSoup().new_tag('a')
        new_a = Tag(name='a', attrs={'href': self.href}, builder=_builder)
        for content in reversed(h2.contents):
            new_a.insert(0, content.extract())
        h2.insert(0, new_a)
        for a in embed.find_all('a'):
            a['target'] = '_blank'
        aside = embed.find('aside', class_='portable-infobox')
        if aside:
            aside['style'] = 'margin: 0px'
        return embed.decode()

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
    rewards: {self.rewards}
"""

class Hyperlink:
    def __init__(self, element: Tag):
        self._element = element

    @property
    def href(self) -> str:
        return self._element['href']

    @property
    def title(self) -> str:
        return self._element['title']

    @property
    def text(self) -> str:
        return self._element.text

    @property
    def string(self) -> str:
        return self._element.string

    def __repr__(self):
        return repr(self._element)
        #return f'<Mission "{self.name}">'

class Prerequisite:
    def __init__(self, element: Tag, client: Hyperlink = None):
        self._element = element
        self._client = client

    def _single_a(self):
        all_a = self._element.find_all('a')
        if len(all_a) != 1:
            return None
        return all_a[0]

    @property
    def href(self):
        a = self._single_a()
        if a and a['title'] != 'Cross':
            return str(a['href'])
        if self.is_affinity and self._client and self._client.text in self._element.text:
            return self._client.href
        return None

    @property
    def title(self):
        a = self._single_a()
        if a and a['title'] != 'Cross':
            return str(a['title'])
        if self.is_affinity and self._client and self._client.text in self._element.text:
            return self._client.title
        return None

    @property
    def text(self):
        if self.is_affinity:
            return self._element.text.replace('Cross-', '')
        return self._element.text

    @property
    def is_mission(self):
        a = self._single_a()
        if a is None:
            return False
        return self._element.text == a.text

    @property
    def is_affinity(self):
        if '♥' in self._element.text or 'affinity' in self._element.text:
            return True
        return False

    @property
    def embed(self):
        embed = copy.deepcopy(self._element)
        for a in embed.find_all('a'):
            a['target'] = '_blank'
        return embed.decode()

    def __str__(self):
        return self.text

    def __repr__(self):
        return f'Prerequisite(\'{self._element!r}\')'

class Reward:
    def __init__(self, element: Tag, client: Hyperlink = None):
        self._element = element
        self._client = client

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
    def unlocks_recruits(self):
        if 'recruit' in self.text or 'join' in self.text:
            return True
        return False

    @property
    def recruits(self):
        if not self.unlocks_recruits:
            return None
        return [ Hyperlink(a) for a in self._element.find_all('a') ] or [self._client]

    @property
    def embed(self):
        embed = copy.deepcopy(self._element)
        for a in embed.find_all('a'):
            a['target'] = '_blank'
        return embed.decode()

    def __str__(self):
        return self.text

    def __repr__(self):
        return f'Reward(\'{self._element!r}\')'

HyperlinkLike = Hyperlink | Prerequisite | Reward
