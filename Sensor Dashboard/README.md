# 🌐 Network Connectivity & Pathway Management Dashboard

A Streamlit-based dashboard for monitoring and managing network topology. Test connections between nodes, visualize pathways interactively, and track system health in real time.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Installation](#installation)
- [Usage](#usage)
- [Dashboard Sections](#dashboard-sections)
- [Database Schema](#database-schema)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Features

- **Interactive Network Visualization** — An interactive graph (powered by PyVis/vis.js) that displays nodes and edges with color-coded statuses. Nodes are draggable and physics is disabled so you can arrange the layout freely.
- **Hover-to-Highlight** — Hovering any node or edge highlights its entire upstream data-delivery tree (all nodes and edges that can reach an endpoint through the hovered element) and dims everything else.
- **Connection Testing** — Run connection tests between any two nodes. The dashboard finds the shortest path, marks edges along that path as **Active**, and logs the result.
- **System Health Metrics** — At-a-glance metrics for total nodes, total pathways, active pathways, and down pathways.
- **Pathway Management** — Add new nodes and pathways directly from the sidebar.
- **Audit Trail** — Every connection test is logged with a timestamp for historical review.
- **SQLite Backend** — All data is persisted in a local SQLite database (`network.db`), automatically created and seeded on first run.

---

## Architecture

```
Sensor Dashboard/
├── app.py            # Streamlit entry point — UI, forms, and page layout
├── database.py       # SQLite CRUD operations and health-summary queries
├── graph_engine.py   # NetworkX graph construction, pathfinding, and PyVis HTML generation
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

| Module | Responsibility |
|---|---|
| `app.py` | Streamlit UI, sidebar forms, health metrics, interactive graph rendering, test results, and pathway table |
| `database.py` | SQLite table creation, seeding dummy data, node/edge/test CRUD, and health-statistics queries |
| `graph_engine.py` | Builds a NetworkX `DiGraph`, finds shortest paths via BFS, and generates a PyVis HTML visualization with custom hover JavaScript |

---

## Installation

### Prerequisites

- **Python 3.9+**
- **pip** (Python package manager)

### Steps

1. **Clone or navigate to the project directory:**
   ```bash
   cd "Sensor Dashboard"
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   If you don't have a `requirements.txt` yet, install the packages manually:
   ```bash
   pip install streamlit networkx pyvis pandas
   ```

3. **Launch the dashboard:**
   ```bash
   streamlit run app.py
   ```

   The app will open in your default browser at `http://localhost:8501`.

---

## Usage

### Adding a Node

1. In the **sidebar**, locate the **➕ Add Node** form.
2. Enter a unique **Node Name** (e.g., `Sensor D`).
3. Select a **Node Type**: `Sensor`, `Endpoint`, or `Intermediary`.
4. Click **Add Node**. A success or error message will appear below the form.

### Adding a Pathway

1. In the **sidebar**, locate the **🔗 Add Pathway** form.
2. Select a **Source Node** and a **Target Node** from the dropdowns.
3. Click **Add Pathway**. The new pathway starts with a **Down** status.

### Running a Connection Test

1. In the **sidebar**, locate the **🧪 Run Connection Test** form.
2. Select a **Source Node** and a **Target Node**.
3. Click **Test Connection**.
   - **If a path exists:** The shortest path is displayed, all edges along that path are marked **Active**, and the result is logged.
   - **If no path exists:** An error message is shown and the failure is logged.

### Viewing the Network Topology

The interactive graph in the main area shows all nodes and pathways:

- **Node colors:**
  - 🔵 Blue = Sensor
  - 🟢 Green = Endpoint
  - 🟠 Orange = Intermediary
- **Edge colors:**
  - 🟢 Green = Active
  - 🔴 Red = Down
  - 🟡 Yellow = Highlighted (path found during a test)

**Interactions:**
- **Drag** nodes to rearrange the layout (physics is disabled, so other nodes won't move).
- **Hover** over any node or edge to highlight its upstream data-delivery tree.
- **Zoom** and **pan** using mouse scroll and click-drag on the background.

### Viewing Pathway Details

The **🔗 Pathway Details** table at the bottom lists every pathway with its source, target, status, and last-tested timestamp. Statuses are color-coded:

- **Active** — green text
- **Down** — red text

---

## Dashboard Sections

| Section | Description |
|---|---|
| **📊 System Health** | Four metric cards showing total nodes, total pathways, active pathways, and down pathways |
| **🗺️ Network Topology** | Interactive PyVis graph with hover-to-highlight, drag-to-reposition, and zoom/pan |
| **📋 Recent Test Results** | The 10 most recent connection tests with source, target, result, and timestamp |
| **🔗 Pathway Details** | A styled table of all pathways with color-coded status |

---

## Database Schema

The SQLite database (`network.db`) is created automatically in the project directory on first run.

### `nodes`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT |
| `name` | TEXT | UNIQUE, NOT NULL |
| `type` | TEXT | NOT NULL, CHECK (`Sensor`, `Endpoint`, `Intermediary`) |

### `edges`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT |
| `source_id` | INTEGER | NOT NULL, FOREIGN KEY → `nodes(id)` |
| `target_id` | INTEGER | NOT NULL, FOREIGN KEY → `nodes(id)` |
| `status` | TEXT | NOT NULL, DEFAULT `Down`, CHECK (`Active`, `Down`) |
| `last_tested` | TEXT | Nullable ISO 8601 timestamp |

### `test_results`

| Column | Type | Constraints |
|---|---|---|
| `id` | INTEGER | PRIMARY KEY, AUTOINCREMENT |
| `source_name` | TEXT | NOT NULL |
| `target_name` | TEXT | NOT NULL |
| `result` | TEXT | NOT NULL |
| `timestamp` | TEXT | NOT NULL, ISO 8601 |

### Seeded Data

On first run, the database is populated with the following sample topology:

```
Sensor A ──→ Gateway 1 ──→ Endpoint A
Sensor B ──→ Gateway 1 ──→ Gateway 2 ──→ Endpoint B
Sensor C ──→ Gateway 2
```

---

## Configuration

### Database Location

The database file `network.db` is created in the same directory as `app.py`. To change its location, edit `DB_PATH` in `database.py`:

```python
DB_PATH = os.path.join(os.path.dirname(__file__), "network.db")
```

### Server Options

Streamlit server settings can be customized via command-line flags or a `streamlit.config.toml` file:

```bash
streamlit run app.py --server.port 8080 --browser.gatherUsageStats false
```

### Graph Appearance

Colors and styling for the interactive graph are defined in `graph_engine.py`:

| Constant | Purpose | Default |
|---|---|---|
| `NODE_COLORS` | Node colors by type | Sensor=Blue, Endpoint=Green, Intermediary=Orange |
| `EDGE_COLORS` | Edge colors by status | Active=Green, Down=Red |
| `HIGHLIGHT_COLOR` | Highlight color for paths and hover | Gold (`#FFD700`) |
| `DIM_COLOR` | Dimmed color during hover | Dark (`#333344`) |

---

## Troubleshooting

| Issue | Solution |
|---|---|
| `ModuleNotFoundError: No module named 'streamlit'` | Run `pip install -r requirements.txt` or install packages individually |
| Graph does not render | Ensure `pyvis` and `networkx` are installed; check browser console for JavaScript errors |
| `AttributeError: 'Styler' object has no attribute 'applymap'` | Upgrade pandas and ensure you're using `df.style.map()` (fixed in this version) |
| Database errors on startup | Delete the existing `network.db` file and restart the app to reinitialize |
| Form feedback messages disappear immediately | This is fixed in the current version — messages are stored in `st.session_state` and rendered outside the form |

---

## License

This project is provided as-is for educational and demonstration purposes.
