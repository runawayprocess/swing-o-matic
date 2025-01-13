import plotly.graph_objects as go
import pandas as pd

def generate_map(state_results):
    # Validate input
    if state_results is None or state_results.empty:
        print("Error: state_results is empty or None.")
        return None

    required_columns = {"State", "Margin", "Winner"}
    if not required_columns.issubset(state_results.columns):
        print("Error: state_results is missing required columns.")
        return None

    # Handle invalid data
    if state_results.isin(["-", None]).any().any():
        print("Error: state_results contains invalid data.")
        return None

    # Create a diverging colorscale centered at zero
    colorscale = [
        [0, "rgb(255, 0, 0)"],       # Red for McCain
        [0.5, "rgb (0, 0, 255)"],    # Blue for tie
        [1, "rgb(0, 0, 255)"]        # Blue for Obama
    ]

    # Normalize margins to range 0-1 for colorscale mapping
    max_margin = max(abs(state_results['Margin'].min()), state_results['Margin'].max())
    z = state_results['Margin'].apply(lambda x: 1 if x > 0 else 0)

    # Create hover text with formatted margins
    def format_margin(row):
        margin = row['Margin']*100
        if margin > 0:
            return f"+{margin:.1f}% D"
        else:
            return f"+{abs(margin):.1f}% R"

    hover_text = state_results.apply(
        lambda row: f"State: {row['State']}<br>Margin: {format_margin(row)}<br>Winner: {row['Winner']}",
        axis=1
    )

    fig = go.Figure(
        data=go.Choropleth(
            locations=state_results['State'],
            z=z,
            locationmode='USA-states',
            text=hover_text,
            hoverinfo='text',
            colorscale=colorscale,
            marker_line_color='white',
            showscale=False        
        )
    )

    fig.update_layout(
        geo=dict(
            scope='usa',
            projection=go.layout.geo.Projection(type='albers usa'),
            showlakes=True,
            lakecolor='rgb(255, 255, 255)'
        ),
    )

    return fig

if __name__ == "__main__":
    # Example DataFrame for testing
    data = {
        'State': ['CA', 'TX', 'FL', 'NY'],
        'Margin': [10, -5, -2, 8],  # Example margins
        'Winner': ['Obama', 'McCain', 'McCain', 'Obama']
    }
    state_results = pd.DataFrame(data)

    map_figure = generate_map(state_results)
    if map_figure:
        map_figure.show()
