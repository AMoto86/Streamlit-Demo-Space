"""
Graph Engine module for Network Connectivity Dashboard.
Handles NetworkX graph construction, pathfinding, and PyVis visualization.
"""

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
        - Nodes are colored by type (Sensor=Blue, Endpoint=Green, Intermediary=Orange)
        - Edges are colored by status (Active=Green, Down=Red)
        - Physics simulation for natural layout
        - Optional path highlighting with thicker, yellow edges
    
    Args:
        graph: The NetworkX DiGraph to visualize.
        highlight_path: Optional list of nodes to highlight (thick yellow edges).
    
    Returns:
        HTML string containing the interactive network graph.
    """
    # Create a PyVis network with physics enabled for dynamic layout
    net = Network(
        height="600px",
        width="100%",
        bgcolor="#1a1a2e",          # Dark background
        font_color="white",
        directed=True,
    )

    # Configure physics for a stable, readable layout
    net.set_options("""
    {
        "physics": {
            "enabled": true,
            "stabilization": {"iterations": 100},
            "barnesHut": {
                "gravitationalConstant": -2000,
                "centralGravity": 0.3,
                "springLength": 150,
                "springConstant": 0.04,
                "damping": 0.09
            }
        },
        "interaction": {
            "hover": true,
            "tooltipDelay": 200
        }
    }
    """)

    # Add nodes with type-based styling
    for node_name, node_attrs in graph.nodes(data=True):
        node_type = node_attrs.get("node_type", "Sensor")
        color = NODE_COLORS.get(node_type, "#999999")

        net.add_node(
            node_name,
            label=node_name,
            color=color,
            size=25,
            shape="dot",
            font={"color": "white", "size": 14},
            borderWidth=2,
            title=f"Type: {node_type}",  # Tooltip
        )

    # Prepare highlight edge set for path emphasis
    highlight_edges = set()
    if highlight_path:
        for i in range(len(highlight_path) - 1):
            highlight_edges.add((highlight_path[i], highlight_path[i + 1]))

    # Add edges with status-based styling
    for source, target, edge_attrs in graph.edges(data=True):
        status = edge_attrs.get("status", "Down")
        is_highlighted = (source, target) in highlight_edges

        if is_highlighted:
            # Highlighted path edges: thick, bright yellow
            edge_color = "#FFD700"
            edge_width = 5
        else:
            # Regular edges: colored by status
            edge_color = EDGE_COLORS.get(status, "#999999")
            edge_width = 2

        net.add_edge(
            source,
            target,
            color={"color": edge_color, "highlight": "#FFD700"},
            width=edge_width,
            title=f"Status: {status}",  # Tooltip
            smooth={"type": "curvedCW", "roundness": 0.15},
        )

    return net.generate_html()
