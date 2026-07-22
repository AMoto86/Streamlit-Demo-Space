"""
Network Connectivity & Pathway Management Dashboard
Main Streamlit entry point.
"""

import streamlit as st
from database import (
    initialize_database,
    seed_dummy_data,
    get_all_nodes,
    get_all_edges,
    get_health_summary,
    get_recent_tests,
    add_node,
    add_edge,
    update_edges_status,
    record_test_result,
)
from graph_engine import (
    build_networkx_graph,
    find_path,
    get_path_edges,
    generate_pyvis_html,
)


# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Network Connectivity Dashboard",
    page_icon="🌐",
    layout="wide",
)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

# Set up database tables and seed data on first run
initialize_database()
seed_dummy_data()


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------

st.title("🌐 Network Connectivity & Pathway Management Dashboard")
st.markdown(
    "Monitor and manage your network topology. Test connections, "
    "visualize pathways, and track system health in real time."
)
st.markdown("---")


# ---------------------------------------------------------------------------
# Sidebar — Forms
# ---------------------------------------------------------------------------

st.sidebar.header("⚙️ Network Controls")

# ---- Add Node Form ----
with st.sidebar.form("add_node_form", clear_on_submit=True):
    st.subheader("➕ Add Node")
    node_name = st.text_input("Node Name", placeholder="e.g., Sensor D")
    node_type = st.selectbox(
        "Node Type",
        options=["Sensor", "Endpoint", "Intermediary"],
    )
    submit_node = st.form_submit_button("Add Node")

    if submit_node:
        if not node_name.strip():
            st.error("Node name cannot be empty.")
        else:
            success = add_node(node_name.strip(), node_type)
            if success:
                st.success(f"Node '{node_name}' added successfully!")
            else:
                st.error(f"A node named '{node_name}' already exists.")

# ---- Add Pathway Form ----
with st.sidebar.form("add_pathway_form", clear_on_submit=True):
    st.subheader("🔗 Add Pathway")
    all_nodes = get_all_nodes()
    node_names = [n["name"] for n in all_nodes]

    col1, col2 = st.columns(2)
    with col1:
        src_node = st.selectbox("Source Node", node_names, key="src1")
    with col2:
        tgt_node = st.selectbox("Target Node", node_names, key="tgt1")

    submit_pathway = st.form_submit_button("Add Pathway")

    if submit_pathway:
        if src_node == tgt_node:
            st.error("Source and target must be different nodes.")
        else:
            success = add_edge(src_node, tgt_node)
            if success:
                st.success(f"Pathway from '{src_node}' to '{tgt_node}' added!")
            else:
                st.error(
                    "Pathway already exists or one of the nodes was not found."
                )

# ---- Run Test Form ----
with st.sidebar.form("run_test_form", clear_on_submit=True):
    st.subheader("🧪 Run Connection Test")

    col1, col2 = st.columns(2)
    with col1:
        test_src = st.selectbox("Source Node", node_names, key="src2")
    with col2:
        test_tgt = st.selectbox("Target Node", node_names, key="tgt2")

    submit_test = st.form_submit_button("Test Connection")

    if submit_test:
        if test_src == test_tgt:
            st.error("Source and target must be different nodes.")
        else:
            # Build the current graph state
            nodes = get_all_nodes()
            edges = get_all_edges()
            graph = build_networkx_graph(nodes, edges)

            # Find shortest path in the graph
            path = find_path(graph, test_src, test_tgt)

            if path:
                # Path exists — mark all edges along the path as Active
                path_edge_pairs = get_path_edges(graph, path)
                update_edges_status(path_edge_pairs, "Active")

                path_str = " → ".join(path)
                message = (
                    f"✅ Connection verified!\n\n"
                    f"**Path:** `{path_str}`\n\n"
                    f"Edges along the path are now marked **Active**."
                )
                st.success(message)
                record_test_result(
                    test_src, test_tgt, f"Success: {path_str}"
                )
            else:
                # No path found
                message = (
                    f"❌ No connection found between "
                    f"'{test_src}' and '{test_tgt}'."
                )
                st.error(message)
                record_test_result(test_src, test_tgt, "No connection found")


# ---------------------------------------------------------------------------
# Main Area — System Health Summary
# ---------------------------------------------------------------------------

st.subheader("📊 System Health")

summary = get_health_summary()

health_col1, health_col2, health_col3, health_col4 = st.columns(4)

health_col1.metric("Total Nodes", summary["total_nodes"])
health_col2.metric("Total Pathways", summary["total_edges"])
health_col3.metric("✅ Active Pathways", summary["active_edges"])
health_col4.metric("❌ Down Pathways", summary["down_edges"])

st.markdown("---")


# ---------------------------------------------------------------------------
# Main Area — Interactive Network Graph
# ---------------------------------------------------------------------------

st.subheader("🗺️ Network Topology")

# Build the current graph
nodes = get_all_nodes()
edges = get_all_edges()
graph = build_networkx_graph(nodes, edges)

# Generate PyVis HTML visualization
html_content = generate_pyvis_html(graph)

# Render the interactive graph in an iframe
st.components.v1.html(html_content, height=650, scrolling=False)

st.markdown("---")


# ---------------------------------------------------------------------------
# Main Area — Recent Test Results
# ---------------------------------------------------------------------------

st.subheader("📋 Recent Test Results")

recent = get_recent_tests(limit=10)

if recent:
    for test in recent:
        icon = "✅" if "Success" in test["result"] else "❌"
        st.markdown(
            f"{icon} **{test['source_name']}** → **{test['target_name']}** "
            f"— {test['result']}  `({test['timestamp']})`"
        )
else:
    st.info("No test results yet. Use the sidebar to run a connection test.")


# ---------------------------------------------------------------------------
# Main Area — Pathway Table
# ---------------------------------------------------------------------------

st.subheader("🔗 Pathway Details")

if edges:
    # Build a clean display table
    table_data = []
    for edge in edges:
        table_data.append(
            {
                "Source": edge["source_name"],
                "Target": edge["target_name"],
                "Status": edge["status"],
                "Last Tested": edge["last_tested"] or "Never",
            }
        )

    import pandas as pd

    df = pd.DataFrame(table_data)

    # Apply color-based styling for the status column
    def highlight_status(val):
        if val == "Active":
            return "color: #50C878; font-weight: bold"
        elif val == "Down":
            return "color: #E74C3C; font-weight: bold"
        return ""

    st.dataframe(
        df.style.applymap(highlight_status, subset=["Status"]),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No pathways configured yet. Use the sidebar to add pathways.")
