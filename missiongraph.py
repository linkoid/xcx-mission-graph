import os
import shutil
import webbrowser
from collections import OrderedDict
import networkx as nx
from pyvis.network import Network


from missions import Mission, Prerequisite, HyperlinkLike
from scrapefandom import scrape_all_missions, scrape_all_missions_concurrent

#def get_mission_color(mission: Mission):
#    if mission.type.startswith('Basic'):
#        return 'blue'
#    elif mission.type.startswith('Normal'):
#        return 'green'
#    elif mission.type.startswith('Affinity'):
#        return 'orange'
#    elif mission.type.startswith('Story'):
#        return 'red'
#    else:
#        return 'white'

def get_mission_size(mission: Mission):
    if mission.type.startswith('Basic'):
        return 6
    elif mission.type.startswith('Normal'):
        return 8
    elif mission.type.startswith('Affinity'):
        return 10
    elif mission.type.startswith('Story'):
        return 20
    else:
        return 5

#def get_mission_weight(mission: Mission):
#    if mission.type.startswith('Basic'):
#        return 0.10
#    elif mission.type.startswith('Normal'):
#        return 0.25
#    elif mission.type.startswith('Affinity'):
#        return 0.50
#    elif mission.type.startswith('Story'):
#        return 1.0
#    else:
#        return 0.10

def simplify_edge_label(link: HyperlinkLike):
    if link.title in link.text:
        return link.text.replace(link.title, '').strip()
    return link.text

def build_graph(skip_basic=False):
    graph = nx.DiGraph(arrows=True)

    # Draw nodes from missions
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
            group=mission_type,
            label=mission_title,
            size=get_mission_size(mission),
            #color=get_mission_color(mission),
            #weight=get_mission_weight(mission),
            title=mission.embed,
        )
        if mission_type == 'Story':
            chapter = int(mission.name.replace('Chapter ', '')[:2])
            graph.add_node(
                mission.href,
                x=(chapter - 6) * 500,
                physics=False,
                shape='box',
                #level=chapter
            )

    # Draw edges from leadsto data
    for mission in missions.values():
        if mission.leadsto:
            graph.add_edge(mission.href, mission.leadsto.href, label='leads to', dashes=True)

    # Draw edges from prerequisites
    for mission in missions.values():
        for prereq in mission.prereqs:
            if prereq.is_mission and prereq.href not in missions.keys():
                continue
            if not prereq.is_mission and prereq.href in missions.keys():
                # Add edges from a mission to it's respective "Mission accepted" criteria
                graph.add_edge(
                    prereq.href,
                    mission.href,
                    label=simplify_edge_label(prereq),
                    title=prereq.embed,
                    dashes=True,
                )
            elif prereq.is_mission:
                if 'Chapter' in prereq.title:
                    graph.add_edge(prereq.href, mission.href, weight=0.25)
                else:
                    graph.add_edge(prereq.href, mission.href)
            elif prereq.href is not None:
                if prereq.href not in ['/wiki/BLADE_Level', '/wiki/Level_(XCX)', '/wiki/Cross']:
                    graph.add_edge(
                        prereq.href, mission.href,
                        label=simplify_edge_label(prereq),
                        title=prereq.embed,
                        dashes=True,
                    )
                    graph.add_node(
                        prereq.href,
                        label=prereq.title,
                        title=prereq.embed,
                        group='Other',
                        shape='square',
                        size=6,
                    )

            # Set special attributes for chapter edges
            if prereq.title and 'Chapter' in prereq.title and 'Chapter' not in mission.name:
                chapter = int(prereq.title.replace('Chapter ', '')[:2])
                #graph.add_node(mission.href, level=chapter)
                graph.add_edge(
                    prereq.href, mission.href,
                    length=190,
                )

    # Draw edges from required characters
    for mission in missions.values():
        for required in mission.required:
            graph.add_edge(required.href, mission.href)
            graph.add_node(required.href, label=required.title, group='Character', shape='square')

    # Draw edges from rewards
    for mission in missions.values():
        for reward in mission.rewards:
            if reward.unlocks_recruits:
                for recruit in reward.recruits:
                    graph.add_edge(mission.href, recruit.href, label=simplify_edge_label(required))
                    graph.add_node(recruit.href, label=recruit.title, title=reward.embed, group='Character', shape='square')

    return graph

def build_graph_network():
    graph = build_graph()

    # Perform transitive reduction on the graph.
    # e.g. missions that depend on both BFFs and Chapter 5 will only
    # depend on BFFs because BFFs already depends on Chapter 5.
    reduced_graph: nx.DiGraph = nx.transitive_reduction(graph)
    for key, data in graph.nodes.data():
        reduced_graph.add_node(key, **data)
    for node_key0, node_key1, data in graph.edges.data():
        if (node_key0, node_key1) in reduced_graph.edges or 'label' in data:
            reduced_graph.add_edge(node_key0, node_key1, **data)
        #elif 'Chapter' not in node_key0:
        #    reduced_graph.add_edge(node_key0, node_key1, hidden=True, **data)
    graph = reduced_graph

    # Set node value based on degree
    degrees = nx.centrality.out_degree_centrality(graph)
    node_count = len(graph.nodes)
    for key, size in graph.nodes.data('size', default=10):
        #print(f'{key=} {degree=} {min(degree, 1)=}')
        graph.add_node(key, size=size+degrees[key]*(node_count-1))
        #graph.add_node(key, value=min(degree, 1))

    net = Network(
        height='100%',
        width='100%',
        directed=True,
        filter_menu=True,
        layout=True,
        neighborhood_highlight=True,
        cdn_resources='remote',
        bgcolor='#000000',
        font_color='#FFFFFF',
    )
    net.from_nx(graph)
    net.options.interaction.__dict__['hover'] = True
    net.options.layout.hierarchical.enabled = False
    net.options.layout.randomSeed = 2015_04_25
    net.options.layout.improvedLayout = False # Too big for improved layout
    #net.heading = "Xenoblade Chronicles X - Missions"
    #net.show_buttons()

    net.options.physics.stabilization.iterations = 500
    net.options.physics.stabilization.updateInterval = 10
    #net.options.physics.stabilization.onlyDynamicEdges = True
    #net.options.physics.stabilization.fit = False

    node_count = net.num_nodes()
    net.options.__dict__['nodes'] = {
        'scaling': {
            'max': node_count,
            'label': {
                'enabled': False,
                'maxVisible': 14,
            }
            #'customScalingFunction': '''
            #    function (min, max, total, value) {
            #        return min + Math.min(1, value / max);
            #    }
            #'''
        },
    }

    net.options.__dict__['edges'] = {
        'font': {
            'size': 10,
            'color': '#AFAFAF',
            'strokeWidth': 0,
        },
        'scaling': {
            'label': {
                'min': 10,
                'max': 20,
                'drawThreshold': 8,
            },
        },
    }

    net.options.__dict__['groups'] = {
        'Other': {
            'color': 'blue',
            'shape': 'square',
            'font': {
                'size': 10,
            },
            'scaling': {
                'min': 6,
                'max': 6 + node_count / 4,
                'label': {
                    'enabled': True,
                    'drawThreshold': 8,
                },
            }
        },
        'Basic': {
            'color': 'blue',
            'font': {
                'size': 10,
            },
            'scaling': {
                'min': 6,
                'max': 6 + node_count / 4,
                'label': {
                    'enabled': True,
                    'drawThreshold': 10,
                },
            }
        },
        'Normal': {
            'color': 'green',
            'scaling': {
                'min': 8,
                'max': 8 + node_count / 4,
                'label': {
                    'enabled': True,
                    'drawThreshold': 10,
                },
            }
        },
        'Affinity': {
            'color': 'orange',
            'scaling': {
                'min': 10,
                'max': 10 + node_count / 4,
                'label': {
                    'enabled': True,
                    'drawThreshold': 6,
                },
            }
        },
        'Character': {
            'color': 'orange',
            'shape': 'square',
            'scaling': {
                'min': 10,
                'max': 10 + node_count / 4,
                'label': {
                    'enabled': True,
                    'drawThreshold': 6,
                },
            },
            'image': 'https://static.wikia.nocookie.net/xenoblade/images/0/06/Anon_NPC_icon.png',
            'brokenImage': 'https://static.wikia.nocookie.net/xenoblade/images/0/06/Anon_NPC_icon.png',
        },
        'Story': {
            'color': 'red',
            'shape': 'box',
            'physics': False,
            'scaling': {
                'min': 20,
                'max': 20 + node_count / 4,
                'label': {
                    'enabled': True,
                    'drawThreshold': 2,
                },
            },
            'fixed': { 'x': True }
        },
    }
    
    return net

def show_net(net: Network, file='index.html', notebook=False):
    html = net.generate_html(file, local=False, notebook=notebook)
    extra_header = '''

        <!-- HTML Meta Tags -->
        <title>Xenoblade Chronicles X - Interactive Mission Graph</title>
        <meta name="description" content="An interactive dependency graph of all missions in Xenoblade Chronicles X and Definitive Edition.">

        <!-- Open Graph Meta Tags -->
        <meta property="og:url" content="https://linkoid.github.io/xcx-mission-graph/">
        <meta property="og:type" content="website">
        <meta property="og:title" content="Xenoblade Chronicles X - Interactive Mission Graph">
        <meta property="og:description" content="An interactive dependency graph of all missions in Xenoblade Chronicles X and Definitive Edition.">
        <meta property="og:image" content="https://linkoid.github.io/xcx-mission-graph/preview.png">
        <meta property="og:image:width" content="955">
        <meta property="og:image:height" content="537">

        <!-- Twitter Meta Tags -->
        <meta name="twitter:card" content="summary_large_image">
        <meta property="twitter:domain" content="linkoid.github.io">
        <meta property="twitter:url" content="https://linkoid.github.io/xcx-mission-graph/">
        <meta name="twitter:title" content="Xenoblade Chronicles X - Interactive Mission Graph">
        <meta name="twitter:description" content="An interactive dependency graph of all missions in Xenoblade Chronicles X and Definitive Edition.">
        <meta name="twitter:image" content="https://linkoid.github.io/xcx-mission-graph/preview.png">
        
        <!-- Fandom Links and Styles -->
        <base href='https://xenoblade.fandom.com/'>
        <link href="/wikia.php?controller=ThemeApi&amp;method=themeVariables" rel="stylesheet">
        <link rel="stylesheet" href="/load.php?lang=en&amp;modules=ext.fandom.ArticleInterlang.css%7Cext.fandom.CreatePage.css%7Cext.fandom.Experiments.TRFC147%7Cext.fandom.GlobalComponents.CommunityHeader.css%7Cext.fandom.GlobalComponents.CommunityHeaderBackground.css%7Cext.fandom.GlobalComponents.CommunityNavigation.css%7Cext.fandom.GlobalComponents.GlobalComponentsTheme.light.css%7Cext.fandom.GlobalComponents.GlobalExploreNavigation.css%7Cext.fandom.GlobalComponents.GlobalFooter.css%7Cext.fandom.GlobalComponents.GlobalNavigationTheme.light.css%7Cext.fandom.GlobalComponents.GlobalTopNavigation.css%7Cext.fandom.GlobalComponents.StickyNavigation.css%7Cext.fandom.HighlightToAction.css%7Cext.fandom.PortableInfoboxFandomDesktop.css%7Cext.fandom.ServerSideExperiments.splitTrafficReleaseNewNav.css%7Cext.fandom.SuggestedPages.css%7Cext.fandom.Thumbnails.css%7Cext.fandom.ThumbnailsViewImage.css%7Cext.fandom.Uncrawlable.css%7Cext.fandom.bannerNotifications.desktop.css%7Cext.fandom.quickBar.css%7Cext.fandomVideo.css%7Cext.staffSig.css%7Cext.visualEditor.desktopArticleTarget.noscript%7Cskin.fandomdesktop.CargoTables-ext.css%7Cskin.fandomdesktop.Math.css%7Cskin.fandomdesktop.font.Lora.css%7Cskin.fandomdesktop.rail.css%7Cskin.fandomdesktop.rail.popularPages.css%7Cskin.fandomdesktop.styles%7Cvendor.tippy.css&amp;only=styles&amp;skin=fandomdesktop">
        <link rel="stylesheet" href="/load.php?lang=en&amp;modules=site.styles&amp;only=styles&amp;skin=fandomdesktop">
        <!-- Fix Fandom Icons not Loading -->
        <meta name="referrer" content="no-referrer">
        
        <!-- Custom Styles -->
        <style type="text/css">
        html > body {
            background-color: black;
        }
        html > body > .card {
            height: 100vh;
            border: black;
        }
        #filter-menu {
            background-color: black;
        }
        div#mynetwork {
            border-color: black;
        }
        div#mynetwork > .popup {
            padding: 5px;
            background-color: #040404;
            border: 4px solid #5594AA;
            color: white;
            font-weight: bold;
        }
        div#mynetwork > .popup * a {
            color: #DDF;
        }
        div#mynetwork > .popup:has(> .xcx) {
            border-radius: 15px;
            border-color: transparent;
            background-color: transparent;
        }
        .popup .xcx .portable-infobox {
            background-color: #040404;
        }
        body > #loadingBar {
            background-color: rgba(0,0,0,0.8);
            & .outerBorder {
                border: 4px solid #5594AA;
                background: #040404;
                width: 640px;
                height: 48px;
                &::before {
                    content: 'A';
                    position: absolute;
                    display: block;
                    left: 12px;
                    top: 6px;
                    width: 28px;
                    height: 28px;
                    text-align: center;
                    font-weight: bold;
                    color: #135156;
                    background-color: white;
                    border: 2px solid #28A4A4;
                    border-radius: 20px;
                }
            }
            & #text {
                color: #6FD0DA;
                top: 2px;
                left: 560px;
                font-weight: bold;
            }
            & #bar {
                background-color: #34ECEC;
                left: 40px;
                top: 0px;
                border-radius: 0px;
                &::before {
                    content: '';
                    position: absolute;
                    display: block;
                    left: -2px;
                    top: -2px;
                    border-style: solid;
                    border-color: #040404 transparent transparent #040404;
                    border-width: 0px 0px 23px 23px;
                }
                &::after {
                    content: '';
                    position: absolute;
                    display: block;
                    right: -2px;
                    top: -2px;
                    border-style: solid;
                    border-color: #040404 transparent #040404 transparent;
                    border-width: 0px 0px 23px 23px;
                }
            }
        }
        </style>
        
    '''
    # Insert additional header tags
    header_tag = '<meta charset="utf-8">'
    head_pos = html.index(header_tag)
    html = html[:head_pos+len(header_tag)] + extra_header + html[head_pos+len(header_tag):]

    # Update to latest version of vis-network
    html = html.replace('vis-network/9.1.2', 'vis-network/9.1.9')
    # vis-network.min.js
    html = html.replace('sha512-LnvoEWDFrqGHlHmDD2101OrLcbsfkrzoSpvtSQtxK3RMnRV0eOkhhBN2dXHKRrUU8p2DGRTk35n4O8nWSVe1mQ==',
                        'sha512-4/EGWWWj7LIr/e+CvsslZkRk0fHDpf04dydJHoHOH32Mpw8jYU28GNI6mruO7fh/1kq15kSvwhKJftMSlgm0FA==')

    html = '<!DOCTYPE html>\n' + html

    with open(file, 'w+', encoding='utf8') as out:
        out.write(html)
    webbrowser.open(file)


if __name__ == '__main__':
    network = build_graph_network()
    show_net(network)
