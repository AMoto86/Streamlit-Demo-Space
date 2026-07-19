import streamlit as st
from pytrends.request import TrendReq
import pandas as pd
import time

# List of popular first-person shooter (FPS) games to track
FPS_GAMES = [
    "Call of Duty",
    "Counter-Strike 2",
    "Valorant",
    "Apex Legends",
    "Overwatch 2",
    "Fortnite",
    "Doom Eternal",
    "Halo Infinite",
    "Battlefield 2042",
    "Rainbow Six Siege",
    "PUBG",
    "Warzone",
    "The Finals",
]

# Google Trends limits keywords per request - batch to avoid 400 errors
BATCH_SIZE = 5


@st.cache_data(ttl=3600)
def fetch_google_trends_data(keyword_list, timeframe="today 12-m"):
    """
    Fetch Google Trends data for the given list of FPS games in batches.
    Google Trends only allows ~5 keywords per request, so we batch them.
    """
    all_dfs = []

    # Split keywords into batches
    for i in range(0, len(keyword_list), BATCH_SIZE):
        batch = keyword_list[i : i + BATCH_SIZE]

        pytrends = TrendReq(hl="en-US", tz=360)
        try:
            pytrends.build_payload(
                kw_list=batch,
                cat=0,
                timeframe=timeframe,
                geo="",
                gprop="",
            )
            df = pytrends.interest_over_time()
            if "isPartial" in df.columns:
                df.drop(columns=["isPartial"], inplace=True)
            all_dfs.append(df)
        except Exception as e:
            st.warning(f"Could not fetch data for batch {batch}: {e}")
            continue

        time.sleep(1)  # Avoid rate limiting

    if not all_dfs:
        return None

    # Combine all batch results into one DataFrame
    combined_df = pd.concat(all_dfs, axis=1)
    return combined_df


def get_timeframe_options():
    """Return available timeframe options for Google Trends."""
    return {
        "Past 7 Days": "today 7-d",
        "Past 30 Days": "today 30-d",
        "Past 12 Months": "today 12-m",
        "Past 5 Years": "today 5-y",
    }


# --- Streamlit App ---
st.set_page_config(
    page_title="FPS Game Search Trends",
    page_icon="🎮",
    layout="wide",
)

st.title("🎮 Top First-Person Shooter Web Search Trends")
st.markdown(
    """
    This app shows real-time Google Trends data for popular first-person shooter (FPS) video games.
    Data is fetched directly from Google Trends and represents worldwide web search interest.
    """
)

# Sidebar controls
st.sidebar.header("⚙️ Settings")

# Timeframe selection
timeframe_labels = list(get_timeframe_options().keys())
selected_label = st.sidebar.selectbox(
    "Time Range",
    options=timeframe_labels,
    index=2,
)
selected_timeframe = get_timeframe_options()[selected_label]

# Number of top results to display
num_results = st.sidebar.slider(
    "Top Games to Display",
    min_value=5,
    max_value=len(FPS_GAMES),
    value=10,
)

# Fetch data
with st.spinner("Fetching data from Google Trends..."):
    trends_df = fetch_google_trends_data(FPS_GAMES, selected_timeframe)

if trends_df is not None and not trends_df.empty:
    # Calculate average interest for each game across the time period
    avg_interest = trends_df.mean().sort_values(ascending=False)

    # Take the top N results
    top_games = avg_interest.head(num_results)

    # Convert to DataFrame for easier plotting
    chart_data = pd.DataFrame(
        {"Game": top_games.index, "Average Search Interest": top_games.values}
    )
    chart_data = chart_data.sort_values(
        by="Average Search Interest", ascending=True
    )

    # Display the bar chart
    st.subheader(f"📊 Top {num_results} FPS Games by Search Interest ({selected_label})")

    st.bar_chart(
        chart_data.set_index("Game"),
        y="Average Search Interest",
        horizontal=True,
        height=400,
    )

    # Display the raw data table
    st.subheader("📋 Detailed Data")
    st.dataframe(
        chart_data.sort_values(by="Average Search Interest", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    # Show the trend over time for the top game
    st.subheader(f"📈 Search Trend Over Time: {top_games.index[0]}")
    trend_chart = trends_df[[top_games.index[0]]]
    st.line_chart(trend_chart, height=300)

else:
    st.error(
        "Could not fetch data from Google Trends. Please try again or check your internet connection."
    )

# Footer
st.markdown("---")
st.caption(
    "Data source: Google Trends via `pytrends` library. "
    "Search interest is normalized on a scale of 0-100, where 100 is the peak popularity."
)
