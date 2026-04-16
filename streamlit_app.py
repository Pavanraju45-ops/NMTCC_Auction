import streamlit as st
import pandas as pd
from io import BytesIO

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="NMTCC Auction", layout="wide")

# ---------------- CSS ----------------
st.markdown("""
<style>
.player-card {
    padding:30px;
    border-radius:20px;
    background: linear-gradient(135deg,#1E293B,#334155);
    text-align:center;
    color:white;
    margin-bottom:20px;
}
.big-font {
    font-size:28px;
    font-weight:bold;
    color:#FFD700;
}
.team-card {
    padding:15px;
    border-radius:15px;
    background:#1e293b;
    color:white;
    margin-bottom:10px;
}
</style>
""", unsafe_allow_html=True)

# ---------------- DEFAULTS ----------------
defaults = {
    "page": "setup",
    "auction_started": False,
    "teams": {},
    "players_df": None,
    "players_per_team": 11,
    "bid": 5,
    "current_player_index": {},
    "sold_players": [],
    "unsold_players": [],
    "history": [],
    "unsold_round": False
}

for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ---------------- TITLE ----------------
st.markdown("<h1 style='text-align:center;color:#FFD700;'>🏏 NMTCC AUCTION</h1>", unsafe_allow_html=True)


# ============================================================
# SETUP PAGE
# ============================================================
if st.session_state.page == "setup":

    st.header("Auction Setup")

    num_teams = st.number_input("Number of Teams", 2, 20, 2)

    teams = {}

    for i in range(num_teams):

        st.subheader(f"Team {i+1}")

        col1, col2 = st.columns(2)

        with col1:
            team_name = st.text_input("Team Name", key=f"team_{i}")

        with col2:
            captain = st.text_input("Captain", key=f"captain_{i}")

        if team_name:
            teams[team_name] = {
                "captain": captain,
                "players": [],
                "purse": 100
            }

    uploaded_file = st.file_uploader("Upload Player Excel", type=["xlsx"])

    players_per_team = st.number_input("Players Per Team", 1, 30, 11)

    purse = st.number_input("Auction Purse", 10, 1000, 100)

    if st.button("🚀 Start Auction"):

        if uploaded_file is None:
            st.error("Upload Excel File")
            st.stop()

        df = pd.read_excel(uploaded_file)

        df.columns = (
            df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
        )

        required_cols = ["player_name", "set", "base_price"]

        if not all(col in df.columns for col in required_cols):
            st.error("Excel must contain: player_name, set, base_price")
            st.stop()

        for team in teams:
            teams[team]["purse"] = purse

        st.session_state.teams = teams
        st.session_state.players_df = df
        st.session_state.players_per_team = players_per_team
        st.session_state.current_player_index = {
            set_name: 0 for set_name in df["set"].unique()
        }

        st.session_state.page = "auction"
        st.rerun()


# ============================================================
# AUCTION PAGE
# ============================================================
elif st.session_state.page == "auction":

    df = st.session_state.players_df

    # BACK BUTTON
    if st.button("⬅ Back to Setup"):
        st.session_state.page = "setup"
        st.rerun()

    st.divider()

    # AVAILABLE SETS
    available_sets = []

    for set_name in df["set"].unique():

        filtered = df[df["set"] == set_name]

        if st.session_state.current_player_index[set_name] < len(filtered):
            available_sets.append(set_name)

    # UNSOLD ROUND
    if not available_sets and st.session_state.unsold_players and not st.session_state.unsold_round:

        st.session_state.unsold_round = True

    # MAIN AUCTION COMPLETE
    if not available_sets and not st.session_state.unsold_round:

        st.session_state.page = "summary"
        st.rerun()

    # UNSOLD ROUND LOGIC
    if st.session_state.unsold_round:

        st.header("🔁 Unsold Players Round")

        unsold_df = pd.DataFrame(st.session_state.unsold_players)

        if unsold_df.empty:
            st.session_state.page = "summary"
            st.rerun()

        player = unsold_df.iloc[0]

    else:

        selected_set = st.selectbox("Choose Set", available_sets)

        filtered_players = df[df["set"] == selected_set].reset_index(drop=True)

        current_index = st.session_state.current_player_index[selected_set]

        player = filtered_players.iloc[current_index]

    # PLAYER CARD
    st.markdown(f"""
    <div class='player-card'>
        <h2>{player['player_name']}</h2>
        <h4>Set: {player['set']}</h4>
        <h3>Base Price: ₹{player['base_price']}</h3>
    </div>
    """, unsafe_allow_html=True)

    # BID
    st.markdown(f"<div class='big-font'>Current Bid: ₹{st.session_state.bid}</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("➕ Increase Bid"):
            st.session_state.bid += 2 if st.session_state.bid < 15 else 5
            st.rerun()

    with col2:
        if st.button("➖ Decrease Bid"):
            if st.session_state.bid > 5:
                st.session_state.bid -= 2 if st.session_state.bid <= 15 else 5
            st.rerun()

    with col3:
        if st.button("🔄 Reset Bid"):
            st.session_state.bid = int(player["base_price"])
            st.rerun()

    winning_team = st.selectbox("Winning Team", list(st.session_state.teams.keys()))

    col4, col5, col6 = st.columns(3)

    # SELL
    with col4:
        if st.button("🔨 Sell Player"):

            team = st.session_state.teams[winning_team]

            if team["purse"] < st.session_state.bid:
                st.error("Insufficient Purse")

            else:
                team["players"].append(player["player_name"])
                team["purse"] -= st.session_state.bid

                st.session_state.sold_players.append({
                    "Player": player["player_name"],
                    "Team": winning_team,
                    "Price": st.session_state.bid
                })

                if st.session_state.unsold_round:
                    st.session_state.unsold_players.pop(0)
                else:
                    st.session_state.current_player_index[selected_set] += 1

                st.session_state.bid = 5

                st.rerun()

    # UNSOLD
    with col5:
        if st.button("❌ Unsold"):

            if st.session_state.unsold_round:
                st.session_state.unsold_players.pop(0)

            else:
                st.session_state.unsold_players.append(player.to_dict())
                st.session_state.current_player_index[selected_set] += 1

            st.rerun()

    # UNDO
    with col6:
        if st.button("↩ Undo"):

            if st.session_state.sold_players:

                last = st.session_state.sold_players.pop()

                st.session_state.teams[last["Team"]]["players"].remove(last["Player"])
                st.session_state.teams[last["Team"]]["purse"] += last["Price"]

                st.rerun()

    # TEAM TABLES
    st.divider()

    st.header("🏆 Team Squads")

    cols = st.columns(len(st.session_state.teams))

    for idx, (team, details) in enumerate(st.session_state.teams.items()):

        with cols[idx]:

            st.markdown(f"### {team}")

            st.write(f"Captain: {details['captain']}")
            st.write(f"Purse Left: ₹{details['purse']}")

            team_df = pd.DataFrame({
                "Players": details["players"]
            })

            st.dataframe(team_df)


# ============================================================
# SUMMARY PAGE
# ============================================================
elif st.session_state.page == "summary":

    st.success("🎉 Auction Completed!")

    if st.button("⬅ Return to Auction"):
        st.session_state.page = "auction"
        st.rerun()

    sold_df = pd.DataFrame(st.session_state.sold_players)

    st.dataframe(sold_df)

    def convert_df(df):
        output = BytesIO()

        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)

        return output.getvalue()

    st.download_button(
        "📥 Download Auction Results",
        convert_df(sold_df),
        "auction_results.xlsx"
    )

    if st.button("🔄 Restart Auction"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
