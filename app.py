import dash
from dash import dcc, html, Input, Output
import pandas as pd
from calculations import apply_generic_swing, construct_df_states, calculate_winner, construct_national_df
from map import generate_map

# Load exit poll data for original margins and total vote shares
def load_exit_poll_data():
    exit_poll = pd.read_csv("data/exit_poll.csv")
    original_margins = {
        "WhiteNonCollegeShare": round((exit_poll.loc[exit_poll['Subgroup'] == 'White no college degree', 'Obama'].values[0] -
                                       exit_poll.loc[exit_poll['Subgroup'] == 'White no college degree', 'McCain'].values[0]) * 100),
        "WhiteCollegeShare": round((exit_poll.loc[exit_poll['Subgroup'] == 'White college graduates', 'Obama'].values[0] -
                                     exit_poll.loc[exit_poll['Subgroup'] == 'White college graduates', 'McCain'].values[0]) * 100),
        "BlackShare": round((exit_poll.loc[exit_poll['Subgroup'] == 'Black', 'Obama'].values[0] -
                             exit_poll.loc[exit_poll['Subgroup'] == 'Black', 'McCain'].values[0]) * 100),
        "HispanicShare": round((exit_poll.loc[exit_poll['Subgroup'] == 'Hispanic', 'Obama'].values[0] -
                                exit_poll.loc[exit_poll['Subgroup'] == 'Hispanic', 'McCain'].values[0]) * 100),
        "AsianShare": round((exit_poll.loc[exit_poll['Subgroup'] == 'Asian', 'Obama'].values[0] -
                             exit_poll.loc[exit_poll['Subgroup'] == 'Asian', 'McCain'].values[0]) * 100),
        "OtherShare": round((exit_poll.loc[exit_poll['Subgroup'] == 'Other', 'Obama'].values[0] -
                             exit_poll.loc[exit_poll['Subgroup'] == 'Other', 'McCain'].values[0]) * 100),
    }
    total_vote_shares = exit_poll.set_index('Subgroup')['% of Total Vote'].to_dict()
    return original_margins, total_vote_shares, exit_poll

def create_dash_app():
    # Initialize Dash app
    app = dash.Dash(__name__)
    app.title = "2008 Swing-O-Matic"

    # Load data and original margins
    df_states = construct_df_states(
        path_demographics="data/state_demographics.csv",
        path_results="data/results.csv"
    )
    original_margins, total_vote_shares, exit_poll = load_exit_poll_data()
    # Extract initial popular vote shares from the "Total" subgroup
    total_row = exit_poll.loc[exit_poll['Subgroup'] == 'Total']
    initial_obama_share = total_row['Obama'].values[0]
    initial_mccain_share = total_row['McCain'].values[0]
    initial_other_share = total_row['Other'].values[0]
    national_demographics = pd.read_csv("data/national_demographics.csv")
    # Define the app layout
    app.layout = html.Div([
        html.H1("2008 Swing-O-Matic", style={"textAlign": "center"}),

        html.Div("""
        Adjust the sliders below to see how demographic changes affect the election outcome.
        """, style={"textAlign": "center"}),

        # Use a flexbox container to split sliders and results
        html.Div([
            # Left column: Sliders
            html.Div([
                html.Div([
                    html.Label(f"Non-College White Margin (Original: {original_margins['WhiteNonCollegeShare']:+d})"),
                    dcc.Slider(id='non_college_white_slider', min=-100, max=100, step=1,
                            value=original_margins['WhiteNonCollegeShare'], marks=None),
                    dcc.Input(id='non_college_white_input', type='number',
                            value=original_margins['WhiteNonCollegeShare'], min=-100, max=100),
                ], style={"margin-bottom": "20px"}),

                html.Div([
                    html.Label(f"College White Margin (Original: {original_margins['WhiteCollegeShare']:+d})"),
                    dcc.Slider(id='college_white_slider', min=-100, max=100, step=1,
                            value=original_margins['WhiteCollegeShare'], marks=None),
                    dcc.Input(id='college_white_input', type='number',
                            value=original_margins['WhiteCollegeShare'], min=-100, max=100),
                ], style={"margin-bottom": "20px"}),

                html.Div([
                    html.Label(f"Black Margin (Original: {original_margins['BlackShare']:+d})"),
                    dcc.Slider(id='black_slider', min=-100, max=100, step=1,
                            value=original_margins['BlackShare'], marks=None),
                    dcc.Input(id='black_input', type='number',
                            value=original_margins['BlackShare'], min=-100, max=100),
                ], style={"margin-bottom": "20px"}),

                html.Div([
                    html.Label(f"Hispanic Margin (Original: {original_margins['HispanicShare']:+d})"),
                    dcc.Slider(id='hispanic_slider', min=-100, max=100, step=1,
                            value=original_margins['HispanicShare'], marks=None),
                    dcc.Input(id='hispanic_input', type='number',
                            value=original_margins['HispanicShare'], min=-100, max=100),
                ], style={"margin-bottom": "20px"}),

                html.Div([
                    html.Label(f"Asian Margin (Original: {original_margins['AsianShare']:+d})"),
                    dcc.Slider(id='asian_slider', min=-100, max=100, step=1,
                            value=original_margins['AsianShare'], marks=None),
                    dcc.Input(id='asian_input', type='number',
                            value=original_margins['AsianShare'], min=-100, max=100),
                ], style={"margin-bottom": "20px"}),

                html.Div([
                    html.Label(f"Other Margin (Original: {original_margins['OtherShare']:+d})"),
                    dcc.Slider(id='other_slider', min=-100, max=100, step=1,
                            value=original_margins['OtherShare'], marks=None),
                    dcc.Input(id='other_input', type='number',
                            value=original_margins['OtherShare'], min=-100, max=100),
                ], style={"margin-bottom": "20px"}),
            ], style={"width": "45%", "padding": "20px"}),  # Adjust width as needed

            # Right column: Results
            html.Div([
                html.Div(id='winner-output', style={"textAlign": "left", "fontSize": "18px", "marginBottom": "20px"}),

                html.Div(id='popular-vote-output', style={"textAlign": "left", "fontSize": "18px", "marginBottom": "20px"}),

                html.Div(id='ec-vote-output', style={"textAlign": "left", "fontSize": "18px", "marginBottom": "20px"}),

                html.Div([
                    dcc.Graph(id='state-results-map', style={"height": "400px"}), 
                    # Add images below the map
                    html.Div([
                        html.Img(src="assets/McCain.png", style={"width": "30%", "margin": "10px"}),
                        html.Img(src="assets/Obama.png", style={"width": "30%", "margin": "10px"}),
                    ], style={"textAlign": "center", "marginTop": "20px"}),
                    ]),
            ], style={"width": "50%", "padding": "20px"}),  # Adjust width as needed
        ], style={"display": "flex", "flexDirection": "row", "justifyContent": "space-between"}),
    ])


    # Callbacks for syncing sliders and inputs
    def sync_slider_input(slider_id, input_id, original_margin):
        @app.callback(
            [Output(slider_id, 'value'), Output(input_id, 'value')],
            [Input(slider_id, 'value'), Input(input_id, 'value')]
        )
        def sync(slider_value, input_value):
            ctx = dash.callback_context
            if not ctx.triggered:
                return slider_value, slider_value
            trigger = ctx.triggered[0]['prop_id']
            return (input_value, input_value) if 'input' in trigger else (slider_value, slider_value)

    # Sync all sliders and inputs
    sync_slider_input('non_college_white_slider', 'non_college_white_input', original_margins['WhiteNonCollegeShare'])
    sync_slider_input('college_white_slider', 'college_white_input', original_margins['WhiteCollegeShare'])
    sync_slider_input('black_slider', 'black_input', original_margins['BlackShare'])
    sync_slider_input('hispanic_slider', 'hispanic_input', original_margins['HispanicShare'])
    sync_slider_input('asian_slider', 'asian_input', original_margins['AsianShare'])
    sync_slider_input('other_slider', 'other_input', original_margins['OtherShare'])

    # Callback to update results
    @app.callback(
        [
            Output('popular-vote-output', 'children'), 
            Output('state-results-map', 'figure'),
            Output('ec-vote-output', 'children')
        ],
        [
            Input('non_college_white_slider', 'value'),
            Input('college_white_slider', 'value'),
            Input('black_slider', 'value'),
            Input('hispanic_slider', 'value'),
            Input('asian_slider', 'value'),
            Input('other_slider', 'value'),
        ]
    )
    def update_results(non_college_white, college_white, black, hispanic, asian, other):
        try:
            # Sanitize input values
            def sanitize_value(value):
                return value if isinstance(value, (int, float)) and not pd.isnull(value) else 0

            non_college_white = sanitize_value(non_college_white)
            college_white = sanitize_value(college_white)
            black = sanitize_value(black)
            hispanic = sanitize_value(hispanic)
            asian = sanitize_value(asian)
            other = sanitize_value(other)
            # Load state-level data
            df_states = construct_df_states(
                path_demographics="data/state_demographics.csv",
                path_results="data/results.csv"
            )

            # Load national demographics data
            df_national = construct_national_df(
                path_demographics="data/national_demographics.csv",
                exit_poll=exit_poll
            )

           # Calculate margin shifts
            margin_shifts = {
                "WhiteNonCollegeShare": max(-100, min(100, non_college_white - original_margins['WhiteNonCollegeShare'])) / 20.00,
                "WhiteCollegeShare": max(-100, min(100, college_white - original_margins['WhiteCollegeShare'])) / 20.00,
                "BlackShare": max(-100, min(100, black - original_margins['BlackShare'])) / 20.00,
                "HispanicShare": max(-100, min(100, hispanic - original_margins['HispanicShare'])) / 20.00,
                "AsianShare": max(-100, min(100, asian - original_margins['AsianShare'])) / 20.00,
                "OtherShare": max(-100, min(100, other - original_margins['OtherShare'])) / 20.00,
            }
        
            df_states = apply_generic_swing(df_states, margin_shifts, turnout_shifts={})

            # Predict popular vote using national data
            margin_shifts = {
                "WhiteNonCollegeShare": max(-100, min(100, non_college_white - original_margins['WhiteNonCollegeShare'])) / 2.00,
                "WhiteCollegeShare": max(-100, min(100, college_white - original_margins['WhiteCollegeShare'])) / 2.00,
                "BlackShare": max(-100, min(100, black - original_margins['BlackShare'])) / 2.00,
                "HispanicShare": max(-100, min(100, hispanic - original_margins['HispanicShare'])) / 2.00,
                "AsianShare": max(-100, min(100, asian - original_margins['AsianShare'])) / 2.00,
                "OtherShare": max(-100, min(100, other - original_margins['OtherShare'])) / 2.00,
            }
            national_shares = df_national.iloc[0]  # There's only one row in national data
            obama_pop_vote = national_shares["BaselineObama"]
            mccain_pop_vote = national_shares["BaselineMcCain"]
            third_party_pop_vote = national_shares["BaselineThird"]

            # Normalize national demographic shares
            total_national_demographic_share = sum(
                national_shares[group] for group in original_margins if group in national_shares
            )
            normalized_national_shares = {
                group: national_shares[group] / total_national_demographic_share
                for group in original_margins if group in national_shares
            }

            for group, original_margin in original_margins.items():
                adjusted_margin = max(-1.0, min(1.0, (margin_shifts.get(group, 0) / 100.0)))
                
                if group in normalized_national_shares:
                    obama_pop_vote += adjusted_margin * normalized_national_shares[group]
                    mccain_pop_vote -= adjusted_margin * normalized_national_shares[group]

            # Clamp popular vote shares to [0, 1]
            obama_pop_vote = max(0.0, min(1.0, obama_pop_vote))
            mccain_pop_vote = max(0.0, min(1.0, mccain_pop_vote))
            third_party_pop_vote = max(0.0, min(1.0, third_party_pop_vote))

            # Normalize votes to 100%
            total_votes = obama_pop_vote + mccain_pop_vote + third_party_pop_vote
            obama_pop_vote /= total_votes
            mccain_pop_vote /= total_votes
            third_party_pop_vote /= total_votes

            # Calculate popular vote margin
            popular_vote_margin = round((obama_pop_vote - mccain_pop_vote) * 100, 1)
            popular_vote_output = (
                f"Popular Vote: Obama {round(obama_pop_vote * 100, 1)}%, "
                f"McCain {round(mccain_pop_vote * 100, 1)}%, "
                f"Margin {abs(popular_vote_margin)}%, "
            )

            # State-level winners
            df_states["Winner"] = df_states.apply(calculate_winner, axis=1)
            
            # Prepare state_results DataFrame for the map
            state_results = df_states[["State", "FinalMargin", "Winner"]].rename(
                columns={"State": "State", "FinalMargin": "Margin", "Winner": "Winner"}
            )
            
            # Calculate EC vote totals
            ec_vote_totals = df_states.groupby("Winner")["EV"].sum().to_dict()
            obama_ec_votes = ec_vote_totals.get("Obama", 0)
            mccain_ec_votes = ec_vote_totals.get("McCain", 0)

            ec_vote_output = (
                f"Electoral College:\n"
                f"Obama {obama_ec_votes}\n"
                f"McCain {mccain_ec_votes}\n"
            )
            
            # Generate map figure
            map_figure = generate_map(state_results)
        
        
            return popular_vote_output, map_figure, ec_vote_output

        except Exception as e:
            print(f"Error occurred: {e}")
            return "An error occurred while calculating results.", ""


    return app

if __name__ == "__main__":
    app = create_dash_app()
    app.run_server(debug=True)
