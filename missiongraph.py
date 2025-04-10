import os
import shutil
import webbrowser
from collections import OrderedDict
import networkx as nx
from pyvis.network import Network


from missions import Mission, Prerequisite
from scrapefandom import scrape_all_missions, scrape_all_missions_concurrent

def get_mission_color(mission: Mission):
    if mission.type.startswith('Basic'):
        return 'blue'
    elif mission.type.startswith('Normal'):
        return 'green'
    elif mission.type.startswith('Affinity'):
        return 'orange'
    elif mission.type.startswith('Story'):
        return 'red'
    else:
        return 'black'

def get_mission_size(mission: Mission):
    if mission.type.startswith('Basic'):
        return 2
    elif mission.type.startswith('Normal'):
        return 8
    elif mission.type.startswith('Affinity'):
        return 10
    elif mission.type.startswith('Story'):
        return 20
    else:
        return 5

def get_mission_weight(mission: Mission):
    if mission.type.startswith('Basic'):
        return 0.10
    elif mission.type.startswith('Normal'):
        return 0.25
    elif mission.type.startswith('Affinity'):
        return 0.50
    elif mission.type.startswith('Story'):
        return 1.0
    else:
        return 0.10

def build_graph(skip_basic=False):
    graph = nx.DiGraph(arrows=True)
    missions: OrderedDict[str, Mission] = OrderedDict()
    for mission_title, mission in scrape_all_missions_concurrent():
        if mission_title.startswith('File:'):
            continue
        if mission.type.startswith('Basic Mission') and skip_basic:
            continue
        missions[mission.href] = mission
        mission_type = mission.type.split(' ')[0]
        graph.add_node(
            mission.href,
            mission_type=mission_type,
            location=str(mission.location.title),
            client=str(mission.client.title),
            #group=mission_type,
            label=mission_title,
            size=get_mission_size(mission),
            color=get_mission_color(mission),
            weight=get_mission_weight(mission),
            title=str(mission._info_box),
        )
        if 'Chapter' in mission.name:
            chapter = int(mission.name.replace('Chapter ', '')[:2])
            graph.add_node(
                mission.href,
                x=chapter * 300,
                physics=False,
                shape='box',
                level=chapter
            )

    for mission in missions.values():
        for prereq in mission.prereqs:
            if prereq.is_mission and prereq.href not in missions.keys():
                continue
            
            if not prereq.is_mission and prereq.href in missions.keys():
                # Add edges from a mission to it's respective "Mission accepted" criteria
                graph.add_edge(
                    prereq.href,
                    mission.href,
                    label=(prereq.text.replace(prereq.title, '').strip()
                           if prereq.title in prereq.text else prereq.text),
                )
            elif prereq.is_mission:
                if 'Chapter' in prereq.title:
                    graph.add_edge(prereq.href, mission.href, weight=0.25)
                else:
                    graph.add_edge(prereq.href, mission.href)
            elif prereq.href is not None:
                #graph.add_edge(prereq.text, mission.href)
                pass

            # Set level based on chapter requirements
            if prereq.title and 'Chapter' in prereq.title and 'Chapter' not in mission.name:
                chapter = int(prereq.title.replace('Chapter ', '')[:2])
                #graph.add_node(mission.href, level=chapter)
                
                
    return graph

def build_graph_network():
    graph = build_graph()

    degrees = nx.centrality.degree_centrality(graph)
    node_count = len(graph.nodes)
    for key, data in graph.nodes.data('size', default=10):
        print(f'{key=} {data=} {degrees[key]*node_count=}')
        graph.add_node(key, size=data+degrees[key]*node_count)

    net = Network(
        height='800px',
        width='100%',
        directed=True,
        filter_menu=True,
        #layout=True,
        neighborhood_highlight=True,
        cdn_resources='in_line',
        bgcolor='#000000',
        font_color='#FFFFFF'
    )
    #net.heading = "Xenoblade Chronicles X - Missions"
    net.from_nx(graph)
    return net

def show_net(net: Network, file='index.html', notebook=False):
    html = net.generate_html(file, local=False, notebook=notebook)
    head_pos = html.index('<head>')
    extra_header = '''
        <base href='https://xenoblade.fandom.com/'>
        <link href="/wikia.php?controller=ThemeApi&amp;method=themeVariables" rel="stylesheet">
        <link rel="stylesheet" href="/load.php?lang=en&amp;modules=ext.fandom.ArticleInterlang.css%7Cext.fandom.CreatePage.css%7Cext.fandom.Experiments.TRFC147%7Cext.fandom.GlobalComponents.CommunityHeader.css%7Cext.fandom.GlobalComponents.CommunityHeaderBackground.css%7Cext.fandom.GlobalComponents.CommunityNavigation.css%7Cext.fandom.GlobalComponents.GlobalComponentsTheme.light.css%7Cext.fandom.GlobalComponents.GlobalExploreNavigation.css%7Cext.fandom.GlobalComponents.GlobalFooter.css%7Cext.fandom.GlobalComponents.GlobalNavigationTheme.light.css%7Cext.fandom.GlobalComponents.GlobalTopNavigation.css%7Cext.fandom.GlobalComponents.StickyNavigation.css%7Cext.fandom.HighlightToAction.css%7Cext.fandom.PortableInfoboxFandomDesktop.css%7Cext.fandom.ServerSideExperiments.splitTrafficReleaseNewNav.css%7Cext.fandom.SuggestedPages.css%7Cext.fandom.Thumbnails.css%7Cext.fandom.ThumbnailsViewImage.css%7Cext.fandom.Uncrawlable.css%7Cext.fandom.bannerNotifications.desktop.css%7Cext.fandom.quickBar.css%7Cext.fandomVideo.css%7Cext.staffSig.css%7Cext.visualEditor.desktopArticleTarget.noscript%7Cskin.fandomdesktop.CargoTables-ext.css%7Cskin.fandomdesktop.Math.css%7Cskin.fandomdesktop.font.Lora.css%7Cskin.fandomdesktop.rail.css%7Cskin.fandomdesktop.rail.popularPages.css%7Cskin.fandomdesktop.styles%7Cvendor.tippy.css&amp;only=styles&amp;skin=fandomdesktop">
    '''
    html = html[:head_pos+6] + extra_header + html[head_pos+6:]
    with open(file, 'w+', encoding='utf8') as out:
        out.write(html)
    webbrowser.open(file)


if __name__ == '__main__':
    network = build_graph_network()
    show_net(network)
