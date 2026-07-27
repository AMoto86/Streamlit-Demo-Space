"""
Graph Engine module for Network Connectivity Dashboard.
Handles NetworkX graph construction, pathfinding, and PyVis visualization.
"""

import json
import networkx as nx
from pyvis.network import Network

# Color mapping for node types
NODE_COLORS = {
    "Sensor": "#4A90D9",       # Blue
    "Endpoint": "#50C878",     # Green
    "Intermediary": "#F5A623", # Orange
}

# Color mapping for edge statuses
EDGE_COLORS = {
    "Active": "#50C878",       # Green
    "Down": "#E74C3C",         # Red
}

# Highlight colors used by the custom hover JavaScript
HIGHLIGHT_COLOR = "#FFD700"    # Bright gold for highlighted nodes/edges
DIM_COLOR = "#333344"          # Darkened color for non-relevant elements
EDGE_DIM_COLOR = "#333344"     # Darkened color for non-relevant edges


# Column ordering for node types (left → right)
COLUMN_ORDER = ["Sensor", "Intermediary", "Endpoint"]


def _compute_column_positions(graph: nx.DiGraph) -> dict:
    """
    Compute explicit (x, y) positions for every node so that nodes are
    laid out in vertical columns by type:
        Column 0 → Sensors
        Column 1 → Intermediaries (gateways)
        Column 2 → Endpoints

    Within each column nodes are evenly spaced along the y-axis.

    Returns a dict:  { node_name: (x, y), ... }
    """
    # Group nodes by type
    groups = {col: [] for col in COLUMN_ORDER}
    for node_name, attrs in graph.nodes(data=True):
        ntype = attrs.get("node_type", "Sensor")
        if ntype in groups:
            groups[ntype].append(node_name)
        else:
            # Fallback: put unknown types in the last column
            groups[COLUMN_ORDER[-1]].append(node_name)

    positions = {}
    for col_idx, col_type in enumerate(COLUMN_ORDER):
        members = groups[col_type]
        x = col_idx * 300  # 300 px per column
        for row_idx, name in enumerate(sorted(members)):
            y = row_idx * 120  # 120 px vertical spacing
            positions[name] = (x, y)

    return positions


def _get_endpoint_nodes(graph: nx.DiGraph) -> set:
    """
    Return the set of node names whose type is 'Endpoint'.

    Endpoints are the final destinations for data in the network.
    """
    return {
        name for name, attrs in graph.nodes(data=True)
        if attrs.get("node_type") == "Endpoint"
    }


def _build_upstream_map(graph: nx.DiGraph) -> dict:
    """
    Build a mapping of every node -> set of (node, edge) pairs that can
    reach *any* endpoint through that node.

    For each endpoint we walk the graph in reverse (following incoming
    edges).  Every node and edge encountered on those reverse walks is
    part of the "data delivery tree" for that endpoint.

    Returns a dict:
        { node_name: { "nodes": { ... }, "edges": { (src, tgt), ... } } }
    """
    endpoints = _get_endpoint_nodes(graph)
    if not endpoints:
        return {}

    # For every node, collect the set of upstream nodes and edges that
    # eventually reach an endpoint through that node.
    upstream = {name: {"nodes": set(), "edges": set()} for name in graph.nodes()}

    for endpoint in endpoints:
        # BFS / DFS in reverse direction starting from the endpoint
        visited_nodes = {endpoint}
        visited_edges = set()
        stack = [endpoint]

        while stack:
            current = stack.pop()
            # Look at all incoming edges (predecessors)
            for predecessor in graph.predecessors(current):
                edge_key = (predecessor, current)
                if edge_key not in visited_edges:
                    visited_edges.add(edge_key)
                if predecessor not in visited_nodes:
                    visited_nodes.add(predecessor)
                    stack.append(predecessor)

        # Merge results into the per-node lookup
        for node_name in visited_nodes:
            upstream[node_name]["nodes"].update(visited_nodes)
            upstream[node_name]["edges"].update(visited_edges)

    return upstream


def build_networkx_graph(nodes: list, edges: list) -> nx.DiGraph:
    """
    Construct a NetworkX directed graph from database data.
    
    The graph represents the network topology where:
        - Nodes are network devices (Sensors, Endpoints, Intermediaries)
        - Directed edges represent data pathways between devices
    
    Args:
        nodes: List of node dicts with 'id', 'name', 'type' keys.
        edges: List of edge dicts with 'source_name', 'target_name', 'status' keys.
    
    Returns:
        A NetworkX DiGraph with node and edge attributes set.
    """
    graph = nx.DiGraph()

    # Add nodes with their type attribute
    for node in nodes:
        graph.add_node(
            node["name"],
            node_type=node["type"],
            node_id=node["id"],
        )

    # Add edges with their status attribute
    for edge in edges:
        graph.add_edge(
            edge["source_name"],
            edge["target_name"],
            status=edge["status"],
        )

    return graph


def find_path(graph: nx.DiGraph, source: str, target: str) -> list:
    """
    Find the shortest path between two nodes in the graph.
    
    Uses NetworkX's shortest_path algorithm which performs a BFS on
    unweighted graphs. Returns the sequence of nodes from source to target.
    
    Args:
        graph: The NetworkX DiGraph.
        source: Name of the source node.
        target: Name of the target node.
    
    Returns:
        A list of node names representing the path, or an empty list if
        no path exists.
    """
    try:
        path = nx.shortest_path(graph, source=source, target=target)
        return path
    except nx.NetworkXNoPath:
        return []
    except nx.NodeNotFound:
        return []


def get_path_edges(graph: nx.DiGraph, path: list) -> list:
    """
    Extract the edge pairs from a path.
    
    Given a path like [A, B, C], returns [(A, B), (B, C)].
    
    Args:
        graph: The NetworkX DiGraph.
        path: List of node names representing a valid path.
    
    Returns:
        List of (source, target) tuples for each edge in the path.
    """
    edges = []
    for i in range(len(path) - 1):
        edges.append((path[i], path[i + 1]))
    return edges


def generate_pyvis_html(
    graph: nx.DiGraph,
    highlight_path: list = None,
) -> str:
    """
    Generate an interactive HTML network visualization using PyVis.
    
    Visualization features:
        - Nodes are colored by type (Sensor=Blue, Endpoint=Green,
          Intermediary=Orange)
        - Edges are colored by status (Active=Green, Down=Red)
        - **Physics is disabled** so nodes can be repositioned independently
          without affecting neighbours.
        - Optional path highlighting with thicker, yellow edges.
        - **Hover-to-highlight**: hovering any node or edge highlights the
          entire upstream data-delivery tree (all nodes and edges that can
          reach an endpoint through the hovered element).

    Args:
        graph: The NetworkX DiGraph to visualize.
        highlight_path: Optional list of nodes to highlight (thick yellow
                        edges).

    Returns:
        HTML string containing the interactive network graph.
    """
    # ------------------------------------------------------------------
    # 1. Build the upstream lookup so hover-JS knows which elements belong
    #    to each node's data-delivery tree.
    # ------------------------------------------------------------------
    upstream_map = _build_upstream_map(graph)

    # ------------------------------------------------------------------
    # 2. Compute column-based positions so Sensors, Gateways, and
    #    Endpoints line up in separate vertical columns.
    # ------------------------------------------------------------------
    positions = _compute_column_positions(graph)

    # ------------------------------------------------------------------
    # 3. Create PyVis network — physics OFF so nodes stay in place.
    # ------------------------------------------------------------------
    net = Network(
        height="600px",
        width="100%",
        bgcolor="#1a1a2e",
        font_color="white",
        directed=True,
    )

    # Physics disabled → nodes stay exactly where you drag them.
    net.set_options("""
    {
        "physics": {
            "enabled": false
        },
        "interaction": {
            "hover": true,
            "tooltipDelay": 200,
            "dragNodes": true,
            "dragView": true,
            "zoomView": true
        }
    }
    """)

    # ------------------------------------------------------------------
    # 4. Collect per-node metadata for the hover JavaScript.
    # ------------------------------------------------------------------
    node_type_map = {}
    node_color_map = {}

    for node_name, node_attrs in graph.nodes(data=True):
        node_type = node_attrs.get("node_type", "Sensor")
        color = NODE_COLORS.get(node_type, "#999999")
        node_type_map[node_name] = node_type
        node_color_map[node_name] = color

        x, y = positions.get(node_name, (0, 0))

        net.add_node(
            node_name,
            label=node_name,
            color=color,
            size=25,
            shape="dot",
            font={"color": "white", "size": 14},
            borderWidth=2,
            title=f"Type: {node_type}",
            x=x,
            y=y,
        )

    # ------------------------------------------------------------------
    # 4. Prepare highlight edge set for path emphasis (from test runs).
    # ------------------------------------------------------------------
    highlight_edges = set()
    if highlight_path:
        for i in range(len(highlight_path) - 1):
            highlight_edges.add((highlight_path[i], highlight_path[i + 1]))

    # Collect edge metadata
    edge_status_map = {}

    for source, target, edge_attrs in graph.edges(data=True):
        status = edge_attrs.get("status", "Down")
        is_highlighted = (source, target) in highlight_edges
        edge_status_map[(source, target)] = status

        if is_highlighted:
            edge_color = HIGHLIGHT_COLOR
            edge_width = 5
        else:
            edge_color = EDGE_COLORS.get(status, "#999999")
            edge_width = 2

        net.add_edge(
            source,
            target,
            color={"color": edge_color, "highlight": HIGHLIGHT_COLOR},
            width=edge_width,
            title=f"Status: {status}",
            smooth=False,
        )

    # ------------------------------------------------------------------
    # 5. Build the upstream JSON blob that the hover JS will consume.
    #    Each entry maps a node name to the set of nodes and edges in its
    #    data-delivery tree.
    # ------------------------------------------------------------------
    upstream_json = {}
    for node_name, info in upstream_map.items():
        upstream_json[node_name] = {
            "nodes": sorted(info["nodes"]),
            "edges": [list(e) for e in sorted(info["edges"])],
        }

    # Build a flat list of all edges for edge-hover lookups
    all_edges = [
        [src, tgt]
        for src, tgt in graph.edges()
    ]

    # ------------------------------------------------------------------
    # 6. Inject custom JavaScript for hover-to-highlight behaviour.
    # ------------------------------------------------------------------
    hover_js = _build_hover_script(upstream_json, all_edges, node_color_map)

    # ------------------------------------------------------------------
    # 7. Generate HTML and inject the script.
    # ------------------------------------------------------------------
    html = net.generate_html()
    # Insert our custom script just before </head>
    html = html.replace("</head>", f"{hover_js}\n</head>")

    return html


# -----------------------------------------------------------------------
# Hover JavaScript generator
# -----------------------------------------------------------------------

def _build_hover_script(
    upstream_json: dict,
    all_edges: list,
    node_color_map: dict,
) -> str:
    """
    Return a <script> block that:
      1. Listens for hover events on nodes and edges.
      2. On hover, highlights the entire upstream data-delivery tree
         (nodes + edges that can reach an endpoint through the hovered
         element) and dims everything else.
      3. On mouse-leave, restores original colours.

    Parameters are serialised to JSON and embedded directly in the script
    so the behaviour is fully self-contained in the generated HTML.
    """
    upstream_safe = json.dumps(upstream_json)
    edges_safe = json.dumps(all_edges)
    colors_safe = json.dumps(node_color_map)

    return f"""
<script type="text/javascript">
(function() {{
    // ---- data injected from Python ----
    var UPSTREAM = {upstream_safe};
    var ALL_EDGES = {edges_safe};
    var ORIGINAL_COLORS = {colors_safe};
    var HIGHLIGHT = "{HIGHLIGHT_COLOR}";
    var DIM       = "{DIM_COLOR}";
    var EDGE_DIM  = "{EDGE_DIM_COLOR}";

    // Wait for vis.network to be ready
    document.addEventListener("DOMContentLoaded", function() {{
        // The vis network is stored on the global `network` object
        var net = network;
        if (!net) return;

        var bodyStyle = document.body.style;
        var origBg = bodyStyle.backgroundColor;

        /* ---- helpers ---- */

        // Build a set of edge ids for a list of [src, tgt] pairs
        function edgeIds(edgePairs) {{
            var ids = [];
            edgePairs.forEach(function(pair) {{
                var e = net.getEdges();
                for (var i = 0; i < e.length; i++) {{
                    if (e[i].from === pair[0] && e[i].to === pair[1]) {{
                        ids.push(e[i].id);
                        break;
                    }}
                }}
            }});
            return ids;
        }}

        // Find which node(s) an edge connects
        function edgeNodePairs(edgeId) {{
            var edge = net.edges.view.get(edgeId);
            if (!edge) return [];
            return [[edge.from, edge.to]];
        }}

        /* ---- apply highlight ---- */

        function highlightTree(nodeName) {{
            var info = UPSTREAM[nodeName];
            if (!info || info.nodes.length === 0) return;

            var highlightNodeIds = info.nodes;
            var highlightEdgeIds = edgeIds(info.edges);

            // Dim all nodes, then brighten the tree
            var allNodes = net.body.nodes;
            var allEdgesObj = net.body.edges;

            // Build original colour snapshots
            var nodeSnap = {{}};
            var edgeSnap = {{}};

            Object.keys(allNodes).forEach(function(id) {{
                nodeSnap[id] = allNodes[id].options.color;
            }});
            Object.keys(allEdgesObj).forEach(function(id) {{
                edgeSnap[id] = allEdgesObj[id].options.color;
            }});

            // Dim everything
            Object.keys(allNodes).forEach(function(id) {{
                allNodes[id].options.color = DIM;
            }});
            Object.keys(allEdgesObj).forEach(function(id) {{
                allEdgesObj[id].options.color = EDGE_DIM;
                allEdgesObj[id].options.width = 1;
            }});

            // Highlight tree nodes
            highlightNodeIds.forEach(function(nid) {{
                if (allNodes[nid]) {{
                    allNodes[nid].options.color = HIGHLIGHT;
                    allNodes[nid].options.size = 35;
                }}
            }});

            // Highlight tree edges
            highlightEdgeIds.forEach(function(eid) {{
                if (allEdgesObj[eid]) {{
                    allEdgesObj[eid].options.color = HIGHLIGHT;
                    allEdgesObj[eid].options.width = 4;
                }}
            }});

            net.redraw();

            // Store snapshot for restore
            window._nodeSnap = nodeSnap;
            window._edgeSnap = edgeSnap;
            window._highlightNodes = highlightNodeIds;
            window._highlightEdges = highlightEdgeIds;
        }}

        /* ---- restore original colours ---- */

        function restoreColors() {{
            var allNodes = net.body.nodes;
            var allEdgesObj = net.body.edges;

            if (window._nodeSnap) {{
                Object.keys(window._nodeSnap).forEach(function(id) {{
                    allNodes[id].options.color = window._nodeSnap[id];
                    allNodes[id].options.size = 25;
                }});
            }}
            if (window._edgeSnap) {{
                Object.keys(window._edgeSnap).forEach(function(id) {{
                    allEdgesObj[id].options.color = window._edgeSnap[id];
                    allEdgesObj[id].options.width = 2;
                }});
            }}

            net.redraw();
            window._nodeSnap = null;
            window._edgeSnap = null;
        }}

        /* ---- node hover ---- */

        net.on("hoverNode", function(params) {{
            var nodeId = params.node;
            // Resolve node label from id
            var nodeData = net.body.nodes[nodeId];
            if (nodeData && nodeData.options && nodeData.options.label) {{
                highlightTree(nodeData.options.label);
            }}
        }});

        net.on("hoverEdge", function(params) {{
            var edgeId = params.edge;
            var edgeData = net.edges.view.get(edgeId);
            if (!edgeData) return;

            // For edge hover: highlight the union of upstream trees for
            // BOTH the source and target nodes of this edge.
            var src = edgeData.from;
            var tgt = edgeData.to;

            // Resolve labels
            var srcNode = net.body.nodes[src];
            var tgtNode = net.body.nodes[tgt];
            var srcLabel = srcNode ? srcNode.options.label : src;
            var tgtLabel = tgtNode ? tgtNode.options.label : tgt;

            // Merge upstream info
            var infoSrc = UPSTREAM[srcLabel] || {{nodes:[], edges:[]}};
            var infoTgt = UPSTREAM[tgtLabel] || {{nodes:[], edges:[]}};

            var mergedNodes = {{}};
            infoSrc.nodes.forEach(function(n){{ mergedNodes[n]=true; }});
            infoTgt.nodes.forEach(function(n){{ mergedNodes[n]=true; }});

            var mergedEdges = {{}};
            infoSrc.edges.forEach(function(e){{ mergedEdges[e[0]+'-'+e[1]]=e; }});
            infoTgt.edges.forEach(function(e){{ mergedEdges[e[0]+'-'+e[1]]=e; }});

            var mergedInfo = {{
                nodes: Object.keys(mergedNodes),
                edges: Object.values(mergedEdges)
            }};

            // Temporarily add merged info and highlight
            UPSTREAM['__hover_edge__'] = mergedInfo;
            highlightTree('__hover_edge__');
            delete UPSTREAM['__hover_edge__'];
        }});

        /* ---- mouse leave resets ---- */

        net.on("blurNode", function() {{ restoreColors(); }});
        net.on("blurEdge", function() {{ restoreColors(); }});
    }});
}})();
</script>
    """
