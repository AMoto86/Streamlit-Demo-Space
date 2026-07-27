"""
Network Connectivity & Pathway Management Dashboard
Main Streamlit entry point.
"""

from datetime import datetime
import pandas as pd
import streamlit as st
from database import (
    initialize_database,
    seed_dummy_data,
    get_all_nodes,
    get_all_edges,
    get_health_summary,
    get_connection_tests,
    add_node,
    add_edge,
    record_connection_test,
)
from graph_engine import (
    build_networkx_graph,
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

# Fetch node names once, outside any form, so all forms can safely use it
all_nodes = get_all_nodes()
node_names = [n["name"] for n in all_nodes]

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
            st.session_state.node_msg = ("error", "Node name cannot be empty.")
        else:
            success = add_node(node_name.strip(), node_type)
            if success:
                st.session_state.node_msg = (
                    "success", f"Node '{node_name}' added successfully!"
                )
            else:
                st.session_state.node_msg = (
                    "error", f"A node named '{node_name}' already exists."
                )

# Display add-node feedback outside the form so it persists
if "node_msg" in st.session_state:
    msg_type, msg_text = st.session_state.node_msg
    if msg_type == "success":
        st.sidebar.success(msg_text)
    else:
        st.sidebar.error(msg_text)
    del st.session_state.node_msg

# ---- Add Pathway Form ----
with st.sidebar.form("add_pathway_form", clear_on_submit=True):
    st.subheader("🔗 Add Pathway")

    col1, col2 = st.columns(2)
    with col1:
        src_node = st.selectbox("Source Node", node_names, key="src1")
    with col2:
        tgt_node = st.selectbox("Target Node", node_names, key="tgt1")

    submit_pathway = st.form_submit_button("Add Pathway")

    if submit_pathway:
        if src_node == tgt_node:
            st.session_state.edge_msg = (
                "error", "Source and target must be different nodes."
            )
        else:
            success = add_edge(src_node, tgt_node)
            if success:
                st.session_state.edge_msg = (
                    "success",
                    f"Pathway from '{src_node}' to '{tgt_node}' added!",
                )
            else:
                st.session_state.edge_msg = (
                    "error",
                    "Pathway already exists or one of the nodes was not found.",
                )

# Display add-pathway feedback outside the form so it persists
if "edge_msg" in st.session_state:
    msg_type, msg_text = st.session_state.edge_msg
    if msg_type == "success":
        st.sidebar.success(msg_text)
    else:
        st.sidebar.error(msg_text)
    del st.session_state.edge_msg

# ---- Connection Status Form ----
with st.sidebar.form("connection_status_form", clear_on_submit=True):
    st.subheader("📡 Connection Status")

    # Build filtered lists by node type
    sensors = [n["name"] for n in all_nodes if n["type"] == "Sensor"]
    gateways = [n["name"] for n in all_nodes if n["type"] == "Intermediary"]
    endpoints = [n["name"] for n in all_nodes if n["type"] == "Endpoint"]

    conn_sensor = st.selectbox("Sensor", sensors, key="conn_sensor")
    conn_gateway = st.selectbox("Gateway", gateways, key="conn_gateway")
    conn_endpoint = st.selectbox("Endpoint", endpoints, key="conn_endpoint")

    conn_status = st.selectbox(
        "Status",
        options=["FMC", "PMC", "NMC", "Untested"],
        key="conn_status",
    )

    conn_date = st.date_input(
        "Test Date",
        value=datetime.now().date(),
        key="conn_date",
    )

    submit_conn = st.form_submit_button("Save Status")

    if submit_conn:
        record_connection_test(
            sensor_name=conn_sensor,
            gateway_name=conn_gateway,
            endpoint_name=conn_endpoint,
            status=conn_status,
            test_date=str(conn_date),
        )
        st.session_state.conn_msg = (
            "success",
            f"Status **{conn_status}** saved for "
            f"{conn_sensor} → {conn_gateway} → {conn_endpoint}.",
        )

# Display connection status feedback outside the form so it persists
if "conn_msg" in st.session_state:
    msg_type, msg_text = st.session_state.conn_msg
    if msg_type == "success":
        st.sidebar.success(msg_text)
    else:
        st.sidebar.error(msg_text)
    del st.session_state.conn_msg


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
# Main Area — Connection Status Table
# ---------------------------------------------------------------------------

st.subheader("📡 Connection Status")

conn_tests = get_connection_tests(limit=50)

if conn_tests:
    conn_table = []
    for ct in conn_tests:
        conn_table.append(
            {
                "Sensor": ct["sensor_name"],
                "Gateway": ct["gateway_name"],
                "Endpoint": ct["endpoint_name"],
                "Status": ct["status"],
                "Test Date": ct["test_date"],
            }
        )

    conn_df = pd.DataFrame(conn_table)

    # Color-code the status column
    STATUS_COLORS = {
        "FMC": "#50C878",      # Green  — Full Mission Capable
        "PMC": "#F5A623",      # Orange — Partially Mission Capable
        "NMC": "#E74C3C",      # Red    — Not Mission Capable
        "Untested": "#999999", # Grey
    }

    def highlight_conn_status(val):
        color = STATUS_COLORS.get(val, "#999999")
        return f"color: {color}; font-weight: bold"

    st.dataframe(
        conn_df.style.map(highlight_conn_status, subset=["Status"]),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info(
        "No connection status records yet. "
        "Use the sidebar to record a connection status."
    )

st.markdown("---")


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

    df = pd.DataFrame(table_data)

    # Apply color-based styling for the status column
    def highlight_status(val):
        if val == "Active":
            return "color: #50C878; font-weight: bold"
        elif val == "Down":
            return "color: #E74C3C; font-weight: bold"
        return ""

    st.dataframe(
        df.style.map(highlight_status, subset=["Status"]),
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No pathways configured yet. Use the sidebar to add pathways.")
