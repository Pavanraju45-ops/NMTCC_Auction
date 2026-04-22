import html
import random
import urllib.parse
import uuid
from datetime import date, datetime, time
from io import BytesIO

import pandas as pd
import streamlit as st

from auth import check_admin, create_admin, has_any_admin
from db import (
    add_auction_players,
    add_auction_team,
    create_auction,
    create_master_team,
    get_master_team_by_name,
    init_schema,
    list_auctions,
    list_master_teams,
    record_sale,
    update_auction_status,
)
from sync_queue import enqueue, stats as sync_stats

st.set_page_config(page_title="NMTCC Auction", layout="wide", page_icon="🏏")

# Global styles
st.markdown(
    """
    <style>
    .hero-title { font-size: 3.2rem; font-weight: 800; text-align: center; margin: 0; letter-spacing: 2px; }
    .hero-sub { font-size: 1.2rem; text-align: center; color: #888; margin-top: 0.3rem; margin-bottom: 1.2rem; }
    .purse-badge {
        background: linear-gradient(135deg, #f59e0b, #ef4444);
        color: white; padding: 1.2rem 2rem; border-radius: 14px;
        text-align: center; margin-bottom: 1.2rem;
    }
    .purse-badge .label { font-size: 0.9rem; opacity: 0.9; text-transform: uppercase; letter-spacing: 2px; }
    .purse-badge .value { font-size: 3rem; font-weight: 800; line-height: 1.1; }
    .team-chip {
        display: inline-block; padding: 0.4rem 0.9rem; border-radius: 999px;
        font-weight: 600; margin: 0.25rem 0.3rem 0.25rem 0;
        text-decoration: none;
        transition: transform 0.12s ease, box-shadow 0.12s ease, opacity 0.12s ease;
    }
    a.team-chip { cursor: pointer; }
    a.team-chip:hover {
        opacity: 0.9;
        box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.6);
        transform: translateY(-1px);
    }
    a.team-chip:hover .chip-x { opacity: 1; }
    .chip-x {
        margin-left: 0.5rem; font-weight: 700; opacity: 0.65;
        border-left: 1px solid rgba(255,255,255,0.35); padding-left: 0.5rem;
    }
    .team-head {
        display: inline-block; padding: 0.3rem 0.8rem; border-radius: 8px;
        font-weight: 700; margin-bottom: 0.4rem;
    }
    .auction-id { font-family: monospace; font-size: 0.8rem; color: #888; }

    /* ---- Auction hero ---- */
    .hero {
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        color: white; padding: 1.8rem 2.2rem; border-radius: 18px;
        margin: 0.5rem 0 1.2rem 0;
        box-shadow: 0 12px 40px rgba(0,0,0,0.18);
    }
    .hero-player-name { font-size: 2.4rem; font-weight: 800; margin: 0; line-height: 1.1; }
    .hero-player-meta {
        font-size: 0.95rem; opacity: 0.75; margin: 0.2rem 0 1rem 0;
        letter-spacing: 1px;
    }
    .hero-bid-label {
        font-size: 0.78rem; opacity: 0.6; text-transform: uppercase;
        letter-spacing: 4px; text-align: center; margin: 0.2rem 0 0 0;
    }
    .hero-bid-value {
        font-size: 4.2rem; font-weight: 800; text-align: center;
        color: #fbbf24; line-height: 1.05; margin: 0 0 0.4rem 0;
        text-shadow: 0 0 32px rgba(251, 191, 36, 0.45);
    }
    .hero-bidder {
        text-align: center; font-size: 0.95rem; opacity: 0.85;
        margin: 0 0 0.8rem 0;
    }
    .hero-bidder b { color: #fbbf24; }

    /* ---- Progress strip ---- */
    .progress-strip {
        display: flex; justify-content: space-between; align-items: center;
        padding: 0.7rem 1.2rem; background: #f8fafc;
        border-radius: 10px; margin-bottom: 0.8rem; font-size: 0.9rem;
        color: #475569;
    }
    .progress-strip b { color: #0f172a; }

    /* ---- RTM strip ---- */
    .rtm-strip {
        display: flex; gap: 0.6rem; flex-wrap: wrap;
        padding: 0.9rem 1.1rem; background: #fef3c7;
        border: 1px solid #fcd34d; border-radius: 12px;
        margin-bottom: 1.1rem;
    }
    .rtm-item {
        display: flex; align-items: center; gap: 0.55rem;
        padding: 0.3rem 0.55rem 0.3rem 0.75rem;
        background: white; border-radius: 999px;
        font-weight: 600; font-size: 0.88rem;
    }
    .rtm-team-dot {
        width: 10px; height: 10px; border-radius: 50%;
    }
    .rtm-count {
        min-width: 1.6rem; text-align: center; padding: 0.1rem 0.5rem;
        border-radius: 999px; font-weight: 700; color: white;
        font-size: 0.85rem;
    }
    .rtm-count.has { background: #22c55e; }
    .rtm-count.none { background: #ef4444; }

    /* ---- Team cards ---- */
    .team-card {
        border: 2px solid #e5e7eb;
        border-radius: 14px;
        background: white;
        overflow: hidden;
        margin-bottom: 1rem;
        transition: transform 0.15s, box-shadow 0.2s, border-color 0.2s;
    }
    .team-card.active {
        border-color: #fbbf24;
        box-shadow: 0 0 0 3px rgba(251, 191, 36, 0.4), 0 8px 24px rgba(0,0,0,0.08);
        transform: translateY(-2px);
    }
    .team-card-header { padding: 0.85rem 1rem; }
    .team-card-title { font-size: 1.15rem; font-weight: 800; line-height: 1.1; }
    .team-card-captain { font-size: 0.8rem; opacity: 0.85; margin-top: 0.15rem; }
    .team-card-body { padding: 0.9rem 1rem 1rem 1rem; }
    .purse-row {
        display: flex; justify-content: space-between; align-items: flex-start;
        gap: 0.5rem;
    }
    .micro-label {
        font-size: 0.68rem; text-transform: uppercase; letter-spacing: 1.5px;
        color: #94a3b8; font-weight: 700;
    }
    .team-purse { font-size: 1.8rem; font-weight: 800; color: #065f46; line-height: 1.1; }
    .team-squad { font-size: 1.3rem; font-weight: 700; color: #1e293b; line-height: 1.1; text-align: right; }
    .team-squad .squad-hint { font-size: 0.7rem; color: #64748b; font-weight: 500; display: block; letter-spacing: 0.5px; }
    .progress-bar {
        width: 100%; height: 7px; background: #e5e7eb; border-radius: 999px;
        margin: 0.7rem 0 0.8rem 0; overflow: hidden;
    }
    .progress-bar-fill {
        height: 100%; background: linear-gradient(90deg, #10b981, #14b8a6);
        border-radius: 999px; transition: width 0.3s;
    }
    .progress-bar-fill.over { background: linear-gradient(90deg, #8b5cf6, #6366f1); }
    .player-list {
        max-height: 240px; overflow-y: auto; font-size: 0.88rem;
        border-top: 1px solid #f3f4f6; padding-top: 0.2rem;
    }
    .player-row {
        display: flex; justify-content: space-between; align-items: center;
        padding: 0.35rem 0.1rem; border-bottom: 1px solid #f3f4f6;
    }
    .player-row:last-child { border-bottom: none; }
    .player-cell-name { color: #334155; }
    .player-cell-price { font-weight: 700; color: #059669; }
    .player-cell-price.rtm { color: #7c3aed; }
    .rtm-tag {
        font-size: 0.65rem; background: #ede9fe; color: #6d28d9;
        padding: 0.05rem 0.4rem; border-radius: 4px; margin-left: 0.4rem;
        font-weight: 700; letter-spacing: 0.5px;
    }
    .empty-squad {
        text-align: center; padding: 1.1rem 0.5rem; color: #94a3b8;
        font-style: italic; font-size: 0.85rem;
    }
    .stButton > button { border-radius: 8px; font-weight: 600; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Ensure schema exists (init_schema itself is no-op after first success)
try:
    init_schema()
except Exception as e:
    st.error(f"Database error: {e}")
    st.stop()


# ---------------- Cached reads ----------------
@st.cache_data(ttl=30, show_spinner=False)
def cached_master_teams():
    return list_master_teams()


@st.cache_data(ttl=15, show_spinner=False)
def cached_recent_auctions():
    return list_auctions()


def invalidate_master_teams_cache():
    cached_master_teams.clear()


def invalidate_auctions_cache():
    cached_recent_auctions.clear()


# ---------------- Sync queue status (sidebar) ----------------
def render_sync_sidebar():
    s = sync_stats()
    with st.sidebar:
        st.markdown("### DB Sync")
        backlog = s["backlog"]
        if backlog == 0:
            st.success(f"Up to date · {s['succeeded']} synced")
        else:
            st.warning(f"Syncing… {backlog} pending")
        st.caption(
            f"enqueued: {s['enqueued']} · succeeded: {s['succeeded']} · "
            f"retried: {s['retried']} · failed: {s['failed']}"
        )
        if s["last_error"]:
            st.caption(f"last error: {s['last_error']}")
        if st.button("Refresh status", key="refresh_sync"):
            st.rerun()


render_sync_sidebar()


# ---------------- SESSION STATE ----------------
defaults = {
    "authenticated": False,
    "admin_username": None,
    "page": "home",
    # Auction runtime
    "auction_id": None,
    "teams": {},  # name -> {captain, color, purse, players:[], team_id, rtm_remaining}
    "players_df": None,
    "players_per_team": 11,
    "purse": 100,
    "bid": 5,
    "set_order": [],
    "set_players": {},
    "set_index": {},
    "current_set_idx": 0,
    "rtm_enabled": False,
    "rtm_count": 0,
    "current_bid_team": None,
    "rtm_stage": None,
    "rtm_player": None,
    "rtm_price": 0,
    "rtm_counter_price": 0,
    "rtm_new_team": None,
    "rtm_old_team": None,
    # Setup wizard
    "setup_selected_teams": [],  # list of dicts {name, captain, color, id (or None)}
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# =========================================================
# AUTH GATE
# =========================================================
def render_auth():
    st.markdown("<h1 class='hero-title'>🏏 NMTCC AUCTION</h1>", unsafe_allow_html=True)
    st.markdown("<p class='hero-sub'>Admin Sign-in Required</p>", unsafe_allow_html=True)

    first_run = not has_any_admin()

    _, mid, _ = st.columns([1, 2, 1])
    with mid:
        if first_run:
            st.info("No admin exists yet. Create the first admin account.")
            with st.form("create_admin"):
                u = st.text_input("Username")
                p1 = st.text_input("Password", type="password")
                p2 = st.text_input("Confirm Password", type="password")
                submitted = st.form_submit_button("Create Admin", use_container_width=True)
                if submitted:
                    if not u or not p1:
                        st.error("Username and password required")
                    elif p1 != p2:
                        st.error("Passwords do not match")
                    elif len(p1) < 6:
                        st.error("Password must be at least 6 characters")
                    else:
                        create_admin(u, p1)
                        st.success("Admin created. Please log in.")
                        st.rerun()
        else:
            with st.form("login"):
                u = st.text_input("Username")
                p = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Log in", use_container_width=True)
                if submitted:
                    if check_admin(u, p):
                        st.session_state.authenticated = True
                        st.session_state.admin_username = u
                        st.rerun()
                    else:
                        st.error("Invalid username or password")


if not st.session_state.authenticated:
    render_auth()
    st.stop()


# Header with logout
top_l, top_r = st.columns([6, 1])
with top_r:
    if st.button("Log out"):
        st.session_state.authenticated = False
        st.session_state.admin_username = None
        st.rerun()


# =========================================================
# HOME
# =========================================================
if st.session_state.page == "home":
    st.markdown("<h1 class='hero-title'>🏏 NMTCC AUCTION</h1>", unsafe_allow_html=True)
    st.markdown(
        "<p class='hero-sub'>Flamingo Cup · Season 1 · Part 2</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if st.button("🚀 Start New Auction", use_container_width=True, type="primary"):
            # reset any prior setup
            st.session_state.setup_selected_teams = []
            st.session_state.page = "setup"
            st.rerun()

        st.markdown("&nbsp;", unsafe_allow_html=True)

        with st.expander("📋 Past Auctions", expanded=False):
            auctions = cached_recent_auctions()
            if not auctions:
                st.caption("No past auctions yet.")
            else:
                for a in auctions:
                    dt = a["auction_datetime"].strftime("%Y-%m-%d %H:%M")
                    name = a["name"] or "(unnamed)"
                    st.markdown(
                        f"**{name}** — {dt} · status: `{a['status']}` "
                        f"<br><span class='auction-id'>ID: {a['id']}</span>",
                        unsafe_allow_html=True,
                    )
                    st.divider()


# =========================================================
# SETUP — reordered: Tournament basics → Players → Teams
# =========================================================
elif st.session_state.page == "setup":
    # Handle click-to-remove on team pills
    if "remove_team" in st.query_params:
        _rm = st.query_params["remove_team"]
        st.session_state.setup_selected_teams = [
            x for x in st.session_state.setup_selected_teams if x["name"] != _rm
        ]
        st.query_params.clear()
        st.rerun()

    st.title("Auction Setup")
    st.caption(f"Signed in as **{st.session_state.admin_username}**")

    # --- Tournament Basics ---
    st.subheader("1 · Tournament Basics")
    b1, b2 = st.columns(2)
    with b1:
        auction_name = st.text_input("Auction Name", placeholder="Flamingo Cup S1 P2")
        auction_date = st.date_input("Auction Date", value=date.today())
    with b2:
        auction_time = st.time_input("Auction Time", value=time(19, 0))
        players_per_team = st.number_input("Players per Team", 1, 20, 11)

    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        purse = st.number_input("Auction Purse", 10, 1000, 100, step=5)
    with c2:
        rtm_enabled = st.toggle("RTM Enabled", value=False)
    with c3:
        rtm_count = st.number_input(
            "RTMs per Team", 0, 5, 2, disabled=not rtm_enabled
        )

    st.divider()

    # --- Players Upload ---
    st.subheader("2 · Players")
    uploaded = st.file_uploader(
        "Upload Players Excel (columns: player_name, set, base_price)",
        type=["xlsx"],
    )
    df_preview = None
    if uploaded is not None:
        try:
            df_preview = pd.read_excel(uploaded)
            df_preview.columns = df_preview.columns.str.strip().str.lower().str.replace(" ", "_")
            required = {"player_name", "set", "base_price"}
            missing = required - set(df_preview.columns)
            if missing:
                st.error(f"Missing columns: {', '.join(missing)}")
                df_preview = None
            else:
                st.success(f"Loaded {len(df_preview)} players across {df_preview['set'].nunique()} sets")
                st.dataframe(df_preview, use_container_width=True, height=200)
        except Exception as e:
            st.error(f"Could not parse Excel: {e}")
            df_preview = None

    st.divider()

    # --- Teams ---
    st.subheader("3 · Teams Participating")
    st.caption("Max 15 teams. Each team name must be unique. Colours are saved for reuse.")

    master_teams = cached_master_teams()
    master_names = [t["name"] for t in master_teams]
    selected_names = [t["name"] for t in st.session_state.setup_selected_teams]

    t1, t2 = st.columns([3, 2])
    with t1:
        to_add = st.selectbox(
            "Add saved team",
            options=[n for n in master_names if n not in selected_names],
            index=None,
            placeholder="Select a saved team...",
            key="add_saved_team",
        )
        if st.button("➕ Add saved team", disabled=to_add is None):
            if len(st.session_state.setup_selected_teams) >= 15:
                st.error("Maximum 15 teams reached")
            else:
                team = next(t for t in master_teams if t["name"] == to_add)
                st.session_state.setup_selected_teams.append(
                    {
                        "id": team["id"],
                        "name": team["name"],
                        "captain": team["captain"],
                        "color": team["color"],
                        "text_color": team.get("text_color") or "#ffffff",
                    }
                )
                st.rerun()

    with t2:
        with st.popover("➕ Add new team"):
            # Plain widgets (not inside a form) so the preview updates live
            new_name = st.text_input("Team Name", key="new_team_name")
            new_captain = st.text_input("Captain", key="new_team_captain")
            c_bg, c_fg = st.columns(2)
            with c_bg:
                new_color = st.color_picker("Background", value="#3b82f6", key="new_team_bg")
            with c_fg:
                new_text_color = st.color_picker("Text Colour", value="#ffffff", key="new_team_fg")

            preview_label = (new_name.strip() or "Team") + " · " + (new_captain.strip() or "Captain")
            st.markdown(
                f"<div style='padding:0.5rem 1rem; border-radius:999px; display:inline-block; "
                f"background:{new_color}; color:{new_text_color}; font-weight:600; margin:0.4rem 0;'>"
                f"{preview_label}</div>",
                unsafe_allow_html=True,
            )

            if st.button("Save & Add", key="new_team_save"):
                nn = new_name.strip()
                if not nn:
                    st.error("Team name required")
                elif len(st.session_state.setup_selected_teams) >= 15:
                    st.error("Maximum 15 teams reached")
                elif nn.lower() in [n.lower() for n in selected_names]:
                    st.error("Team already added to this auction")
                else:
                    existing = get_master_team_by_name(nn)
                    if existing:
                        st.error(f"Team '{nn}' already exists in saved teams. Use the dropdown to add it.")
                    else:
                        team_id = create_master_team(
                            nn, new_captain.strip(), new_color, new_text_color
                        )
                        invalidate_master_teams_cache()
                        st.session_state.setup_selected_teams.append(
                            {
                                "id": team_id,
                                "name": nn,
                                "captain": new_captain.strip(),
                                "color": new_color,
                                "text_color": new_text_color,
                            }
                        )
                        # clear the form fields for the next entry
                        for k in ("new_team_name", "new_team_captain"):
                            if k in st.session_state:
                                del st.session_state[k]
                        st.rerun()

    # Selected teams display — click a chip to remove it
    if st.session_state.setup_selected_teams:
        st.markdown("**Selected Teams** · _click a team to remove_")
        chips = "".join(
            f"<a class='team-chip' "
            f"href='?remove_team={urllib.parse.quote(t['name'])}' "
            f"target='_self' "
            f"title='Click to remove {t['name']}' "
            f"style='background:{t['color']}; color:{t.get('text_color', '#ffffff')};'>"
            f"{t['name']} · {t['captain'] or '—'}"
            f"<span class='chip-x'>✕</span>"
            f"</a>"
            for t in st.session_state.setup_selected_teams
        )
        st.markdown(chips, unsafe_allow_html=True)
    else:
        st.caption("No teams added yet.")

    st.divider()

    # --- Validate & Start ---
    nav_l, nav_r = st.columns([1, 1])
    with nav_l:
        if st.button("← Back to Home"):
            st.session_state.page = "home"
            st.rerun()
    with nav_r:
        if st.button("🚀 Start Auction", type="primary", use_container_width=True):
            errors = []
            if uploaded is None or df_preview is None:
                errors.append("Upload a valid players Excel file")
            if len(st.session_state.setup_selected_teams) < 2:
                errors.append("Add at least 2 teams")
            if len(st.session_state.setup_selected_teams) > 15:
                errors.append("Maximum 15 teams")

            if errors:
                for e in errors:
                    st.error(e)
            else:
                dt = datetime.combine(auction_date, auction_time)
                auction_id = str(uuid.uuid4())

                # Async: UI proceeds immediately; daemon thread syncs to Postgres.
                enqueue(
                    create_auction,
                    auction_id=auction_id,
                    name=auction_name.strip() or None,
                    auction_datetime=dt,
                    players_per_team=int(players_per_team),
                    purse=int(purse),
                    rtm_enabled=bool(rtm_enabled),
                    rtm_count=int(rtm_count) if rtm_enabled else 0,
                )

                teams_state = {}
                for t in st.session_state.setup_selected_teams:
                    enqueue(
                        add_auction_team,
                        auction_id,
                        t["id"],
                        int(purse),
                        int(rtm_count) if rtm_enabled else 0,
                    )
                    teams_state[t["name"]] = {
                        "team_id": t["id"],
                        "captain": t["captain"],
                        "color": t["color"],
                        "text_color": t.get("text_color") or "#ffffff",
                        "purse": int(purse),
                        "players": [],
                        "rtm_remaining": int(rtm_count) if rtm_enabled else 0,
                    }

                player_rows = [
                    (str(r["player_name"]), str(r["set"]), r["base_price"])
                    for r in df_preview.to_dict("records")
                ]
                enqueue(add_auction_players, auction_id, player_rows)
                invalidate_auctions_cache()

                # hydrate session state for auction flow
                st.session_state.auction_id = auction_id
                st.session_state.teams = teams_state
                st.session_state.players_df = df_preview
                st.session_state.players_per_team = int(players_per_team)
                st.session_state.purse = int(purse)
                st.session_state.rtm_enabled = bool(rtm_enabled)
                st.session_state.rtm_count = int(rtm_count) if rtm_enabled else 0
                st.session_state.bid = 5

                set_order = list(df_preview["set"].unique())
                st.session_state.set_order = set_order
                st.session_state.current_set_idx = 0
                for s in set_order:
                    players = df_preview[df_preview["set"] == s].to_dict("records")
                    random.shuffle(players)
                    st.session_state.set_players[s] = players
                    st.session_state.set_index[s] = 0

                st.session_state.page = "auction"
                st.rerun()


# =========================================================
# AUCTION
# =========================================================
elif st.session_state.page == "auction":
    # ---------------- Helpers ----------------
    def _render_team_card(name: str, data: dict, is_active: bool, min_players: int) -> str:
        bought = len(data["players"])
        pct = min(100, int(round(100 * bought / max(1, min_players))))
        over = bought > min_players
        safe_name = html.escape(name)
        safe_cap = html.escape(data.get("captain") or "—")
        bg = data["color"]
        fg = data.get("text_color") or "#ffffff"

        if data["players"]:
            rows = []
            for p in data["players"]:
                tag = "<span class='rtm-tag'>RTM</span>" if p.get("is_rtm") else ""
                rows.append(
                    f"<div class='player-row'>"
                    f"<div class='player-cell-name'>{html.escape(str(p['player']))}{tag}</div>"
                    f"<div class='player-cell-price{' rtm' if p.get('is_rtm') else ''}'>₹{p['sold']}</div>"
                    f"</div>"
                )
            player_html = f"<div class='player-list'>{''.join(rows)}</div>"
        else:
            player_html = "<div class='empty-squad'>No players yet</div>"

        min_hint = f"min {min_players}" if not over else f"+{bought - min_players} over min"

        return (
            f"<div class='team-card{' active' if is_active else ''}'>"
            f"<div class='team-card-header' style='background:{bg}; color:{fg};'>"
            f"<div class='team-card-title'>{safe_name}</div>"
            f"<div class='team-card-captain'>Captain: {safe_cap}</div>"
            f"</div>"
            f"<div class='team-card-body'>"
            f"<div class='purse-row'>"
            f"<div><div class='micro-label'>Purse</div><div class='team-purse'>₹{data['purse']}</div></div>"
            f"<div><div class='micro-label' style='text-align:right;'>Squad</div>"
            f"<div class='team-squad'>{bought}/{min_players}"
            f"<span class='squad-hint'>{min_hint}</span></div></div>"
            f"</div>"
            f"<div class='progress-bar'>"
            f"<div class='progress-bar-fill{' over' if over else ''}' style='width:{pct}%'></div>"
            f"</div>"
            f"{player_html}"
            f"</div>"
            f"</div>"
        )

    def _render_teams_grid(active_team: str | None):
        teams_items = list(st.session_state.teams.items())
        n = len(teams_items)
        cols_per_row = 3 if n <= 9 else 4 if n <= 12 else 5
        min_players = int(st.session_state.players_per_team)

        for row_start in range(0, n, cols_per_row):
            row = teams_items[row_start:row_start + cols_per_row]
            cols = st.columns(cols_per_row)
            for i, (name, data) in enumerate(row):
                with cols[i]:
                    st.markdown(
                        _render_team_card(name, data, name == active_team, min_players),
                        unsafe_allow_html=True,
                    )

    def _finalize_sale(player_obj, team_name: str, price: int, is_rtm: bool):
        td = st.session_state.teams[team_name]
        td["players"].append(
            {
                "player": player_obj["player_name"],
                "base": player_obj["base_price"],
                "sold": price,
                "is_rtm": is_rtm,
            }
        )
        td["purse"] -= price
        if is_rtm:
            td["rtm_remaining"] -= 1
        enqueue(
            record_sale,
            st.session_state.auction_id,
            player_obj["player_name"],
            td["team_id"],
            price,
            is_rtm=is_rtm,
        )

    # ---------------- Walk to next unsold player ----------------
    while st.session_state.current_set_idx < len(st.session_state.set_order):
        current_set = st.session_state.set_order[st.session_state.current_set_idx]
        idx = st.session_state.set_index[current_set]
        if idx < len(st.session_state.set_players[current_set]):
            player = st.session_state.set_players[current_set][idx]
            break
        else:
            st.session_state.current_set_idx += 1
    else:
        enqueue(update_auction_status, st.session_state.auction_id, "completed")
        invalidate_auctions_cache()
        st.session_state.page = "trade"
        st.rerun()

    # Fresh player → start bid at base price
    base_price = int(player["base_price"])
    if st.session_state.bid < base_price:
        st.session_state.bid = base_price

    # ---------------- Progress strip ----------------
    total_players = sum(len(ps) for ps in st.session_state.set_players.values())
    sold_players = sum(len(t["players"]) for t in st.session_state.teams.values())
    st.markdown(
        f"<div class='progress-strip'>"
        f"<div>Set: <b>{html.escape(str(current_set))}</b></div>"
        f"<div>Progress: <b>{sold_players}/{total_players}</b> players sold</div>"
        f"<div class='auction-id'>Auction: {st.session_state.auction_id[:8]}…</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # ---------------- HERO: current player + bid + controls ----------------
    bid_team_current = st.session_state.current_bid_team or "—"
    st.markdown(
        f"""
        <div class='hero'>
          <div class='hero-player-name'>{html.escape(str(player['player_name']))}</div>
          <div class='hero-player-meta'>Set: {html.escape(str(current_set))} · Base: ₹{base_price}</div>
          <div class='hero-bid-label'>Current Bid</div>
          <div class='hero-bid-value'>₹{st.session_state.bid}</div>
          <div class='hero-bidder'>Top bidder: <b>{html.escape(str(bid_team_current))}</b></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Bid controls: quick increments + custom input + reset
    quick_cols = st.columns([1, 1, 1, 1, 2, 1])
    increments = [1, 2, 5, 10]
    for i, inc in enumerate(increments):
        with quick_cols[i]:
            if st.button(f"+{inc}", key=f"inc_{inc}", use_container_width=True):
                st.session_state.bid += inc
                st.rerun()
    with quick_cols[4]:
        custom = st.number_input(
            "Set bid",
            min_value=base_price,
            value=st.session_state.bid,
            step=1,
            key="custom_bid_input",
            label_visibility="collapsed",
        )
        if custom != st.session_state.bid:
            st.session_state.bid = int(custom)
    with quick_cols[5]:
        if st.button("↺ Base", key="reset_bid", use_container_width=True, help="Reset to base price"):
            st.session_state.bid = base_price
            st.rerun()

    # Team selectors + sell
    sell_cols = st.columns([2, 2, 2])
    valid_teams = [t for t, d in st.session_state.teams.items() if d["purse"] >= st.session_state.bid]
    if not valid_teams:
        st.error("No team can afford this bid. Reduce bid.")
        st.stop()

    with sell_cols[0]:
        bid_team = st.selectbox("Bidding Team", valid_teams, key="bid_team_select")
        st.session_state.current_bid_team = bid_team
    with sell_cols[1]:
        if st.session_state.rtm_enabled:
            last_team = st.selectbox(
                "Previous team (RTM eligible)",
                ["NA"] + list(st.session_state.teams.keys()),
                key="last_team_select",
            )
        else:
            last_team = "NA"
            st.caption("RTM disabled for this auction")
    with sell_cols[2]:
        st.markdown("<div style='height:1.7rem'></div>", unsafe_allow_html=True)
        sell_clicked = st.button(
            f"✅ SELL to {bid_team} @ ₹{st.session_state.bid}",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.rtm_stage is not None,
        )

    if sell_clicked:
        final_team = st.session_state.current_bid_team
        price = st.session_state.bid
        if st.session_state.teams[final_team]["purse"] < price:
            st.error(f"{final_team} does not have enough purse!")
        elif (
            st.session_state.rtm_enabled
            and last_team != "NA"
            and last_team != final_team
            and st.session_state.teams[last_team]["rtm_remaining"] > 0
        ):
            st.session_state.rtm_stage = "ask"
            st.session_state.rtm_player = player
            st.session_state.rtm_price = price
            st.session_state.rtm_new_team = final_team
            st.session_state.rtm_old_team = last_team
            st.rerun()
        else:
            _finalize_sale(player, final_team, price, is_rtm=False)
            st.session_state.set_index[current_set] += 1
            st.session_state.bid = 0
            st.rerun()

    # ---------------- RTM inline panel ----------------
    if st.session_state.rtm_stage is not None:
        with st.container(border=True):
            st.markdown(
                f"**🔁 RTM — {st.session_state.rtm_old_team}** can match **{st.session_state.rtm_new_team}**'s "
                f"bid of **₹{st.session_state.rtm_price}** for **{st.session_state.rtm_player['player_name']}**."
            )

            if st.session_state.rtm_stage == "ask":
                a, b, _ = st.columns([1, 1, 3])
                with a:
                    if st.button("Use RTM", key="rtm_use", use_container_width=True):
                        st.session_state.rtm_stage = "counter"
                        st.rerun()
                with b:
                    if st.button("Skip RTM", key="rtm_skip", use_container_width=True):
                        _finalize_sale(
                            st.session_state.rtm_player,
                            st.session_state.rtm_new_team,
                            st.session_state.rtm_price,
                            is_rtm=False,
                        )
                        st.session_state.rtm_stage = None
                        st.session_state.set_index[current_set] += 1
                        st.session_state.bid = 0
                        st.rerun()

            elif st.session_state.rtm_stage == "counter":
                new_price = st.number_input(
                    "Counter-bid price",
                    min_value=int(st.session_state.rtm_price),
                    value=int(st.session_state.rtm_price),
                    step=1,
                    key="rtm_counter_input",
                )
                if st.button("Submit counter", key="rtm_submit", type="primary"):
                    st.session_state.rtm_counter_price = int(new_price)
                    st.session_state.rtm_stage = "decision"
                    st.rerun()

            elif st.session_state.rtm_stage == "decision":
                st.write(
                    f"Counter-bid: **₹{st.session_state.rtm_counter_price}** — does "
                    f"**{st.session_state.rtm_old_team}** accept?"
                )
                a, b, _ = st.columns([1, 1, 3])
                with a:
                    if st.button("Accept (new team wins)", key="rtm_accept", use_container_width=True):
                        team = st.session_state.rtm_new_team
                        price = st.session_state.rtm_counter_price
                        if st.session_state.teams[team]["purse"] < price:
                            st.error(f"{team} cannot afford this price!")
                        else:
                            _finalize_sale(st.session_state.rtm_player, team, price, is_rtm=False)
                            st.session_state.rtm_stage = None
                            st.session_state.set_index[current_set] += 1
                            st.session_state.bid = 0
                            st.rerun()
                with b:
                    if st.button("Reject (RTM wins)", key="rtm_reject", use_container_width=True):
                        team = st.session_state.rtm_old_team
                        price = st.session_state.rtm_counter_price
                        if st.session_state.teams[team]["purse"] < price:
                            st.error(f"{team} cannot afford RTM!")
                        else:
                            _finalize_sale(st.session_state.rtm_player, team, price, is_rtm=True)
                            st.session_state.rtm_stage = None
                            st.session_state.set_index[current_set] += 1
                            st.session_state.bid = 0
                            st.rerun()

    # ---------------- RTM remaining strip ----------------
    if st.session_state.rtm_enabled:
        pills = []
        for tname, tdata in st.session_state.teams.items():
            cnt = tdata["rtm_remaining"]
            has = "has" if cnt > 0 else "none"
            pills.append(
                f"<div class='rtm-item'>"
                f"<span class='rtm-team-dot' style='background:{tdata['color']};'></span>"
                f"<span>{html.escape(tname)}</span>"
                f"<span class='rtm-count {has}'>{cnt}</span>"
                f"</div>"
            )
        st.markdown(
            f"<div class='rtm-strip'><div class='micro-label' "
            f"style='color:#92400e; align-self:center; margin-right:0.4rem;'>RTM remaining</div>"
            f"{''.join(pills)}</div>",
            unsafe_allow_html=True,
        )

    # ---------------- Team cards grid ----------------
    _render_teams_grid(active_team=st.session_state.current_bid_team)

    # Finish-early escape hatch
    st.divider()
    c1, c2, _ = st.columns([1, 1, 3])
    with c1:
        if st.button("Finish auction now", key="finish_auction"):
            enqueue(update_auction_status, st.session_state.auction_id, "completed")
            invalidate_auctions_cache()
            st.session_state.page = "trade"
            st.rerun()
    with c2:
        if st.button("Back to Home", key="auction_home"):
            st.session_state.page = "home"
            st.rerun()


# =========================================================
# TRADE WINDOW
# =========================================================
elif st.session_state.page == "trade":
    st.title("Trade Window")
    teams = list(st.session_state.teams.keys())
    col1, col2 = st.columns(2)
    with col1:
        t1 = st.selectbox("Team 1", teams)
        st.dataframe(pd.DataFrame(st.session_state.teams[t1]["players"]))
    with col2:
        t2 = st.selectbox("Team 2", teams)
        st.dataframe(pd.DataFrame(st.session_state.teams[t2]["players"]))

    p1 = st.selectbox("Player Team 1", [p["player"] for p in st.session_state.teams[t1]["players"]])
    p2 = st.selectbox("Player Team 2", [p["player"] for p in st.session_state.teams[t2]["players"]])

    if st.button("Execute Trade"):
        team1 = st.session_state.teams[t1]["players"]
        team2 = st.session_state.teams[t2]["players"]
        player1 = next(p for p in team1 if p["player"] == p1)
        player2 = next(p for p in team2 if p["player"] == p2)
        team1.remove(player1)
        team2.remove(player2)
        team1.append(player2)
        team2.append(player1)
        st.success("Trade Completed")

    if st.button("Finish Trade"):
        st.session_state.page = "summary"
        st.rerun()


# =========================================================
# SUMMARY
# =========================================================
elif st.session_state.page == "summary":
    st.title("Auction Summary")
    st.markdown(f"<div class='auction-id'>Auction ID: {st.session_state.auction_id}</div>", unsafe_allow_html=True)

    for team, data in st.session_state.teams.items():
        st.markdown(
            f"<div class='team-head' style='background:{data['color']}; color:{data.get('text_color', '#ffffff')}; font-size:1.3rem;'>{team}</div>",
            unsafe_allow_html=True,
        )
        st.write("Remaining Purse:", data["purse"])
        st.dataframe(pd.DataFrame(data["players"]), use_container_width=True)

    def export():
        output = BytesIO()
        with pd.ExcelWriter(output) as writer:
            for team, data in st.session_state.teams.items():
                pd.DataFrame(data["players"]).to_excel(writer, sheet_name=team[:30])
        return output.getvalue()

    st.download_button("Download Results", export(), "auction.xlsx")

    if st.button("Back to Home"):
        # reset runtime state but keep auth
        keep = {"authenticated", "admin_username"}
        for k in list(st.session_state.keys()):
            if k not in keep:
                del st.session_state[k]
        st.rerun()
