import pandas as pd
import numpy as np

def apply_generic_swing(
    df_states,
    margin_shifts,
    turnout_shifts,
    third_party_shifts=None,
    max_margin_points=100.0
):
    """
    Apply a generic swing approach with:
      - National turnout shift by demographic (capped at 100% group share)
      - Margin shifts by demographic (capped at +/- max_margin_points)
      - Third-party shift by demographic, preserving the new two-party margin

    Parameters
    ----------
    df_states : pd.DataFrame
        Each row = 1 state.
        Columns:
          - 'State'
          - 'BaselineObama', 'BaselineMcCain', 'BaselineThird' (floats, e.g. 0.47 = 47%)
          - Several group-share columns, e.g. 'BlackShare', 'WhiteCollegeShare', etc.
            whose sum is ~1.0 for each state (before turnout shifts).
    margin_shifts : dict
        group_name -> float (in **percentage points**)
        e.g. { "BlackShare": 5.0, "HispanicShare": -2.0 }
    turnout_shifts : dict
        group_name -> float (fractional)
        e.g. { "BlackShare": 0.10, "HispanicShare": -0.05 }
        This means +10% or -5% on the *group's share*.
    third_party_shifts : dict, optional
        group_name -> float (the new desired fraction of that group that goes 3rd party).
        e.g. { "AsianShare": 0.09 } means 9% of Asians now go third party.
        We'll approximate the impact at the state level.
    max_margin_points : float
        The maximum absolute margin in percentage points allowed.  E.g., 100.0 = +/- 100%.

    Returns
    -------
    pd.DataFrame
        A new DataFrame with columns:
          - FinalObama, FinalMcCain, FinalThird
          - FinalMargin
          - Winner
    """

    df = df_states.copy()

    # Identify columns that hold group shares
    # We'll assume all columns ending with 'Share' are demographic share columns
    group_cols = [c for c in df.columns if c.endswith("Share") 
                  and c not in ["BaselineObama", "BaselineMcCain", "BaselineThird"]]

    # 1) Apply turnout shifts, cap each group at 1.0
    for idx, row in df.iterrows():
        row_sum = 0.0
        # Adjust each group's share
        for g_col in group_cols:
            base_val = row[g_col]
            t_shift = turnout_shifts.get(g_col, 0.0)  # e.g. 0.10
            new_val = base_val * (1 + t_shift)
            # cap at 1.0
            if new_val > 1.0:
                new_val = 1.0
            df.at[idx, g_col] = new_val
            row_sum += new_val

        # re-normalize so sum of group_cols is 1.0 if row_sum > 0
        if row_sum > 0:
            for g_col in group_cols:
                df.at[idx, g_col] = df.at[idx, g_col] / row_sum
        else:
            # if row_sum == 0, we can't re-normalize, but that'd be an edge case
            pass

    # 2) Baseline margin & two-party sum
    df["BaselineMargin"] = df["BaselineObama"] - df["BaselineMcCain"]
    df["TwoPartySum"] = df["BaselineObama"] + df["BaselineMcCain"]  # e.g. 0.98 or so

    # 3) Sum partial margin shifts for each state
    margin_shift_list = []
    for idx, row in df.iterrows():
        partial_shift = 0.0
        for g_col in group_cols:
            shift_pts = margin_shifts.get(g_col, 0.0)
            fraction = row[g_col]
            partial_shift += shift_pts * fraction
        margin_shift_list.append(partial_shift)

    df["MarginShift"] = margin_shift_list

    # 4) new margin = baseline margin + margin shift
    #    clamp to [-max_margin_points, +max_margin_points]
    df["NewMargin"] = df["BaselineMargin"] + df["MarginShift"]
    df["NewMargin"] = df["NewMargin"].clip(lower=-max_margin_points, upper=max_margin_points)

    # Convert margin in points to fraction if BaselineObama etc. are fractions
    # e.g., +5.0 points => 0.05 in fraction
    # We'll do it consistently below:
    df["MarginFrac"] = df["NewMargin"] 

    # 5) Recompute two-party shares ignoring third-party for the moment
    #    If TwoPartySum = X, MarginFrac = M,
    #    Obama2p = (X + M)/2, McCain2p = (X - M)/2
    df["Obama2p"] = (df["TwoPartySum"] + df["MarginFrac"]) / 2.0
    df["McCain2p"] = (df["TwoPartySum"] - df["MarginFrac"]) / 2.0

    # 6) We'll keep BaselineThird as a starting point, then incorporate any
    #    group-level third-party shifts in a partial approach.
    df["FinalThird"] = df["BaselineThird"].copy()

    # If user provided a 'third_party_shifts', apply them
    # We'll approximate that "X% of that group goes third party"
    # Then we do a partial shift for each group in each state
    if third_party_shifts:
        # For each state, we sum up how much third party changes.
        # Then we preserve the new margin by adjusting Obama & McCain proportionally.
        tp_delta_list = []
        for idx, row in df.iterrows():
            partial_tp_change = 0.0
            for g_col in group_cols:
                # e.g. user says "AsianShare": 0.09 => 9%
                if g_col in third_party_shifts:
                    new_tp_for_group = third_party_shifts[g_col]  # fraction
                    # Let's assume baseline for that group is 'BaselineThird' of the state?
                    # This is approximate. We do partial difference times fraction:
                    baseline_tp_for_group = row["BaselineThird"]  # approximate
                    diff = (new_tp_for_group - baseline_tp_for_group) * row[g_col]
                    partial_tp_change += diff

            tp_delta_list.append(partial_tp_change)

        df["ThirdPartyDelta"] = tp_delta_list
        df["FinalThird"] = df["BaselineThird"] + df["ThirdPartyDelta"]

    # 7) Now we have:
    #    - Obama2p, McCain2p as initial 2-party shares
    #    - FinalThird as updated third-party
    # We re-normalize them so total = 1.0, but we want to preserve the new margin if possible.
    # The new margin in fraction is MarginFrac = (Obama2p - McCain2p).
    # We'll handle it row-by-row:

    final_obama = []
    final_mccain = []
    final_third = []

    for idx, row in df.iterrows():
        o2p = row["Obama2p"]
        m2p = row["McCain2p"]
        t_base = row["FinalThird"]
        # sum them
        total = o2p + m2p + t_base
        if total <= 0:
            # degenerate case
            final_obama.append(0.5)
            final_mccain.append(0.5)
            final_third.append(0.0)
            continue

        # We want to preserve (o2p - m2p) = row["MarginFrac"]
        # Also we want third = t_base +/- partial shift
        # => define new_Obama2p, new_McCain2p = (some re-scale) while preserving difference
        # We'll do:
        #    new_O_plus_M = 1 - t_base
        #    marginFrac   = (o2p - m2p)
        # => new_O = (new_O_plus_M + marginFrac)/2
        #    new_M = (new_O_plus_M - marginFrac)/2
        # Then scale them so all sum to 1.0

        # first clamp t_base to [0,1] in case partial shift was big
        if t_base < 0: 
            t_base = 0.0
        if t_base > 1:
            t_base = 1.0

        new_o_plus_m = 1.0 - t_base
        margin_frac = row["MarginFrac"]  # we want to keep this

        # But if margin_frac is bigger than new_o_plus_m, it's not feasible to preserve
        # that margin. We'll clamp it so new_O doesn't exceed new_o_plus_m or go negative.
        if margin_frac > new_o_plus_m:
            # means we can't have that big a margin
            margin_frac = new_o_plus_m
        if margin_frac < -new_o_plus_m:
            margin_frac = -new_o_plus_m

        new_o2p = (new_o_plus_m + margin_frac) / 2.0
        new_m2p = (new_o_plus_m - margin_frac) / 2.0

        # Now we have new_o2p + new_m2p + t_base = 1.0 by construction
        final_obama.append(new_o2p)
        final_mccain.append(new_m2p)
        final_third.append(t_base)

    df["FinalObama"] = final_obama
    df["FinalMcCain"] = final_mccain
    df["FinalThird"] = final_third

    # 8) Final margin & winner
    df["FinalMargin"] = df["FinalObama"] - df["FinalMcCain"]
    df["Winner"] = np.where(df["FinalMargin"] > 0, "Obama", "McCain")

    return df

def construct_national_df(path_demographics="data/national_demographics.csv", exit_poll=None):
    # Read the national demographics CSV
    df_national = pd.read_csv(path_demographics)

    # Rename columns for consistency with the state data
    rename_map = {
        "Asian/Pacific Islander": "AsianShare",
        "Black/African American": "BlackShare",
        "Hispanic/Latino": "HispanicShare",
        "Other": "OtherShare",
        "College_White": "WhiteCollegeShare",
        "Noncollege_White": "WhiteNonCollegeShare",
        "Male": "MaleShare",
        "Female": "FemaleShare",
    }
    df_national = df_national.rename(columns=rename_map)

    # Check for missing columns
    required_cols = [
        "WhiteCollegeShare", "WhiteNonCollegeShare", "BlackShare", "HispanicShare",
        "AsianShare", "OtherShare", "MaleShare", "FemaleShare"
    ]
    missing_cols = [col for col in required_cols if col not in df_national.columns]
    if missing_cols:
        raise ValueError(f"Missing columns in national demographics: {missing_cols}")

    # Extract baseline shares from exit_poll
    if exit_poll is not None:
        total_row = exit_poll.loc[exit_poll['Subgroup'] == 'Total']
        if not total_row.empty:
            baseline_obama = total_row['Obama'].values[0]
            baseline_mccain = total_row['McCain'].values[0]
            baseline_third = total_row['Other'].values[0]
        else:
            raise ValueError("Exit poll 'Total' row is missing.")
    else:
        raise ValueError("Exit poll DataFrame is required.")

    # Add baseline result columns
    df_national["BaselineObama"] = baseline_obama
    df_national["BaselineMcCain"] = baseline_mccain
    df_national["BaselineThird"] = baseline_third

    return df_national

def construct_df_states(
    path_demographics="data/state_demographics.csv",
    path_results="data/results.csv"
):
    """
    Construct a DataFrame (df_states) that merges:
      1) State-level demographics (in decimal form) from state_demographics.csv
      2) State-level election results (in decimal form) from results.csv

    The CSV 'state_demographics.csv' includes columns like:
      STATE,
      Female, Male,
      Female_Percentage, Male_Percentage,
      White_College_Percentage, White_Non_College_Percentage,
      Black_Percentage, Hispanic_Percentage, Asian_Percentage, Other_Percentage,
      18-24_Percentage, 25-29_Percentage, 30-39_Percentage, 40-49_Percentage,
      50-64_Percentage, 65+_Percentage,
      $15,000-30,000, $30,000-50,000, etc. (with _Percentage),
      Not_a_veteran_Percentage, Veteran_Percentage,
      etc.

    The CSV 'results.csv' has columns like:
      STATE, OBAMA, MCCAIN, THIRDPARTY, EV, MARGIN, TURNOUT
      (all in decimals, e.g. 0.47 for 47%).
    
    We'll rename or select columns to create a final DataFrame with columns:
      [
        "State",
        "BaselineObama",
        "BaselineMcCain",
        "BaselineThird",
        "WhiteCollegeShare",
        "WhiteNonCollegeShare",
        "BlackShare",
        "HispanicShare",
        "AsianShare",
        "OtherShare",
        "MaleShare",
        "FemaleShare",
        # Age bracket shares:
        "Age18_24Share", "Age25_29Share", "Age30_39Share", "Age40_49Share", "Age50_64Share", "Age65PlusShare",
        # Income bracket shares:
        "Under15kShare", "k15_30Share", "k30_50Share", "k50_75Share", "k75_100Share",
        "k100_150Share", "k150_200Share", "Over200kShare",
        # Veteran status:
        "VetShare", "NotVetShare",
        # From results:
        "EV", "MARGIN", "TURNOUT"
      ]

    Parameters
    ----------
    path_demographics : str
        Filepath to your state_demographics.csv.
    path_results : str
        Filepath to your results.csv.

    Returns
    -------
    pd.DataFrame
        A merged DataFrame with one row per state, containing
        baseline results and demographic columns in decimal form.
    """

    # 1) Read the demographics CSV
    df_demo = pd.read_csv(path_demographics)

    # The demographics CSV has a column 'STATEICP' for state name; rename it to 'State'.
    df_demo = df_demo.rename(columns={"STATE": "State"})

    # We'll create a rename map for key columns. 
    # (Double-check each column name matches your CSV precisely!)
    rename_map = {
        # Race/Ethnicity
        "Black_Percentage": "BlackShare",
        "Hispanic_Percentage": "HispanicShare",
        "Asian_Percentage": "AsianShare",
        "Other_Percentage": "OtherShare",
        "White_Non_College_Percentage": "WhiteNonCollegeShare",
        "White_College_Percentage": "WhiteCollegeShare",
        # Sex
        "Male_Percentage": "MaleShare",
        "Female_Percentage": "FemaleShare",
        # Age brackets
        "18-24_Percentage": "Age18_24Share",
        "25-29_Percentage": "Age25_29Share",
        "30-39_Percentage": "Age30_39Share",
        "40-49_Percentage": "Age40_49Share",
        "50-64_Percentage": "Age50_64Share",
        "65+_Percentage": "Age65PlusShare",
        # Veteran status
        "Not_a_veteran_Percentage": "NotVetShare",
        "Veteran_Percentage": "VetShare",
        # Income brackets (assuming columns like 'Under_15000_Percentage', etc.)
        "Under_15000_Percentage": "Under15kShare",
        "15000-30000_Percentage": "k15_30Share",
        "30000-50000_Percentage": "k30_50Share",
        "50000-75000_Percentage": "k50_75Share",
        "75000-100000_Percentage": "k75_100Share",
        "100000-150000_Percentage": "k100_150Share",
        "150000-200000_Percentage": "k150_200Share",
        "Over_200000_Percentage": "Over200kShare",
    }

    df_demo = df_demo.rename(columns=rename_map)

    # 2) Read the results CSV
    df_results = pd.read_csv(path_results)
    # We'll rename 'STATE' -> 'State'
    df_results = df_results.rename(columns={"STATE": "State"})
    # Also rename OBAMA, MCCAIN, THIRDPARTY -> BaselineObama, BaselineMcCain, BaselineThird
    df_results = df_results.rename(columns={
        "OBAMA": "BaselineObama",
        "MCCAIN": "BaselineMcCain",
        "THIRDPARTY": "BaselineThird"
    })

    # 3) Merge on 'State'
    df_merged = pd.merge(df_demo, df_results, on="State", how="inner")

    # 4) Select columns for final
    keep_cols = [
        "State",
        # Race/Ethnicity, Sex
        "WhiteCollegeShare", "WhiteNonCollegeShare",
        "BlackShare", "HispanicShare", "AsianShare", "OtherShare",
        "MaleShare", "FemaleShare",
        # Age
        "Age18_24Share", "Age25_29Share", "Age30_39Share", "Age40_49Share", "Age50_64Share", "Age65PlusShare",
        # Income
        "Under15kShare", "k15_30Share", "k30_50Share", "k50_75Share", "k75_100Share",
        "k100_150Share", "k150_200Share", "Over200kShare",
        # Veteran
        "VetShare", "NotVetShare",
        # Results
        "BaselineObama", "BaselineMcCain", "BaselineThird",
        "EV", "MARGIN", "TURNOUT"
    ]

    # Filter to only those columns that exist
    keep_cols = [c for c in keep_cols if c in df_merged.columns]

    # 5) Build the final DataFrame
    df_states = df_merged[keep_cols].copy()

    return df_states

def check_state_winner(row):
    """
    Given a row containing FinalObama, FinalMcCain, FinalThird columns,
    return the string for whichever candidate has the highest share.
    In case of a tie, this function breaks ties arbitrarily or uses a policy you define.
    """
    # Extract final shares
    obama_share = row["FinalObama"]
    mccain_share = row["FinalMcCain"]
    third_share = row["FinalThird"]

    # Compare
    max_value = max(obama_share, mccain_share, third_share)

    # Return whichever is largest
    if max_value == third_share:
        return "ThirdParty"
    elif max_value == obama_share:
        return "Obama"
    else:
        return "McCain"

def calculate_winner(row):
    """
    row must have columns: FinalObama, FinalMcCain, FinalThird
    Returns: a string in { 'Obama', 'McCain', 'ThirdParty' }
    """
    o = row["FinalObama"]
    m = row["FinalMcCain"]
    t = row["FinalThird"]

    maximum = max(o, m, t)
    if maximum == t:
        return "ThirdParty"
    elif maximum == o:
        return "Obama"
    else:
        return "McCain"


