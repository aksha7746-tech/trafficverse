import streamlit as st
from google.cloud import bigquery
from google import genai
import pandas as pd
import matplotlib.pyplot as plt
import json
import os

GEMINI_MODEL = "gemini-3.6-flash"


@st.cache_resource
def get_gemini_client():
    """Creates a Gemini API client. Reads the key from Streamlit secrets
    first (recommended for Cloud Run deployment), falling back to the
    GEMINI_API_KEY environment variable (handy for local/Cloud Shell dev).
    """
    api_key = None

    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        return None

    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def parse_scenario_with_gemini(client, scenario, known_corridors):
    """Uses Gemini to extract the affected corridor and time period from
    free-text scenario input. Returns a dict {"corridor": ..., "period": ...}
    or None if the call fails or the model can't confidently extract both.
    """

    if client is None:
        return None

    corridor_list_str = ", ".join(known_corridors)

    prompt = f"""You are a traffic-operations assistant. A user describes a
road-closure or disruption scenario in free text. Extract two fields:

1. "corridor": the road/corridor being affected. It MUST be exactly one of
   this list (copy it verbatim, case-sensitive): [{corridor_list_str}]
   If none of these are clearly referenced, respond with "UNKNOWN".

2. "period": the time period. It MUST be exactly one of:
   "Morning Peak", "Evening Peak", "Morning", "Evening".
   Treat rush-hour / heavy-traffic-hour phrasing as "Morning Peak" or
   "Evening Peak". Treat generic "this morning" / "in the morning" (with no
   peak/rush-hour signal) as "Morning". Same logic for evening.
   If genuinely unclear, respond with "Morning Peak" as a default.

Scenario: "{scenario}"

Respond with ONLY a JSON object with keys "corridor" and "period". No other
text."""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )

        parsed = json.loads(response.text)

        corridor = parsed.get("corridor")
        period = parsed.get("period")

        if corridor not in known_corridors:
            corridor = None

        valid_periods = {"Morning Peak", "Evening Peak", "Morning", "Evening"}
        if period not in valid_periods:
            period = None

        if corridor is None and period is None:
            return None

        return {"corridor": corridor, "period": period}

    except Exception:
        return None


def generate_decision_text_with_gemini(client, result):
    """Uses Gemini to write a short (1-2 sentence) traffic-management
    recommendation based on the simulation's computed metrics. Returns
    None if the call fails, so the caller can fall back to a static
    template.
    """

    if client is None:
        return None

    prompt = f"""You are a senior traffic operations advisor. Based on the
following counterfactual simulation results for closing a road corridor,
write a single short, decisive recommendation (max 2 sentences) for a city
traffic control room. Be concrete and actionable. Do not repeat the raw
numbers back verbatim; give guidance.

- Affected corridor: {result['affected_corridor']}
- Time period: {result['period']}
- Risk level: {result['risk']}
- Estimated congestion increase: {result['congestion_increase']:.0f}%
- Redirected traffic volume: {result['redirected_volume']:.0f} vehicles
- Estimated network speed after closure: {result['estimated_speed']:.1f} km/h
  (down from baseline {result['network_speed']:.1f} km/h)

Respond with plain text only, no markdown, no preamble."""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        text = response.text.strip()
        return text if text else None
    except Exception:
        return None


def styled_bar_chart(labels, values, ylabel, colors=("#4C9BE8", "#E8734C")):
    """Static, non-interactive bar chart styled for a dark background."""

    fig, ax = plt.subplots(figsize=(6, 3.2))

    bars = ax.bar(labels, values, color=list(colors)[:len(labels)])

    fig.patch.set_alpha(0)
    ax.set_facecolor("none")

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#888888")
    ax.spines["bottom"].set_color("#888888")

    ax.tick_params(colors="#DDDDDD")
    ax.set_ylabel(ylabel, color="#DDDDDD")

    max_val = max(values) if values else 0
    ax.set_ylim(0, max_val * 1.2 if max_val > 0 else 1)

    for bar, val in zip(bars, values):
        ax.annotate(
            f"{val:,.0f}",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 6),
            textcoords="offset points",
            ha="center",
            color="#FFFFFF",
            fontsize=10,
            fontweight="bold"
        )

    fig.tight_layout()
    return fig

st.set_page_config(
    page_title="TrafficVerse",
    page_icon="🚦",
    layout="wide"
)

PROJECT_ID = "project-d9bb51ba-d27c-4e8e-b52"

TABLE_ID = (
    "project-d9bb51ba-d27c-4e8e-b52."
    "trafficverse.traffic_volume_profiles"
)


@st.cache_resource
def get_bigquery_client():
    return bigquery.Client(project=PROJECT_ID)


@st.cache_data
def load_traffic_data():

    client = get_bigquery_client()

    query = f"""
        SELECT
            corridor,
            time,
            period,
            vehicle_type,
            vehicle_volume,
            average_speed_kmh
        FROM `{TABLE_ID}`
        LIMIT 320
    """

    return client.query(query).to_dataframe()


def keyword_match_scenario(scenario, corridors):
    """Fallback rule-based parser, used only when Gemini is unavailable
    or does not return a confident extraction."""

    scenario_lower = scenario.lower()

    if "morning peak" in scenario_lower:
        selected_period = "Morning Peak"
    elif "evening peak" in scenario_lower:
        selected_period = "Evening Peak"
    elif "morning" in scenario_lower:
        selected_period = "Morning"
    elif "evening" in scenario_lower:
        selected_period = "Evening"
    else:
        selected_period = "Morning Peak"

    affected_corridor = None

    for corridor in corridors:
        if corridor.lower() in scenario_lower:
            affected_corridor = corridor
            break

    if affected_corridor is None:

        corridor_aliases = {
            "outer ring road": "Outer Ring Road",
            "orr": "Outer Ring Road",
            "silk board": "Silk Board Junction",
            "silkboard": "Silk Board Junction",
            "hosur": "Hosur Road",
            "btm": "BTM Layout",
            "electronic city": "Electronic City Road",
            "hsr": "HSR Layout",
            "madiwala": "Madiwala",
            "bommanahalli": "Bommanahalli"
        }

        for keyword, corridor_name in corridor_aliases.items():
            if keyword in scenario_lower:
                affected_corridor = corridor_name
                break

    if affected_corridor is None:
        affected_corridor = "Outer Ring Road"

    return affected_corridor, selected_period


def run_simulation(data, scenario, gemini_client=None):

    corridors = list(data["corridor"].unique())

    gemini_result = parse_scenario_with_gemini(
        gemini_client, scenario, corridors
    )

    fallback_corridor, fallback_period = keyword_match_scenario(
        scenario, corridors
    )

    used_ai_parsing = False

    if gemini_result:
        affected_corridor = gemini_result.get("corridor") or fallback_corridor
        selected_period = gemini_result.get("period") or fallback_period
        used_ai_parsing = True
    else:
        affected_corridor = fallback_corridor
        selected_period = fallback_period

    period_data = data[
        data["period"].str.lower() == selected_period.lower()
    ].copy()

    if period_data.empty:
        period_data = data.copy()

    corridor_stats = (
        period_data
        .groupby("corridor")
        .agg(
            total_volume=("vehicle_volume", "sum"),
            average_speed=("average_speed_kmh", "mean")
        )
        .reset_index()
    )

    affected = corridor_stats[
        corridor_stats["corridor"] == affected_corridor
    ]

    if affected.empty:
        affected_corridor = corridor_stats.iloc[0]["corridor"]
        affected = corridor_stats[
            corridor_stats["corridor"] == affected_corridor
        ]

    baseline_volume = float(affected.iloc[0]["total_volume"])
    baseline_speed = float(affected.iloc[0]["average_speed"])

    REDIRECT_FRACTION = 0.80
    redirected_volume = baseline_volume * REDIRECT_FRACTION

    alternatives = corridor_stats[
        corridor_stats["corridor"] != affected_corridor
    ].copy()

    alternatives["available_score"] = (
        alternatives["average_speed"] / alternatives["total_volume"]
    )

    alternatives = alternatives.sort_values(
        "available_score", ascending=False
    )

    max_score = alternatives["available_score"].max()
    if max_score and max_score > 0:
        alternatives["suitability_score"] = (
            alternatives["available_score"] / max_score * 100
        )
    else:
        alternatives["suitability_score"] = 0

    top_alternatives = alternatives.head(3).reset_index(drop=True)
    top_alternatives.index = top_alternatives.index + 1

    network_baseline = corridor_stats["total_volume"].sum()

    network_speed = (
        (corridor_stats["average_speed"] * corridor_stats["total_volume"]).sum()
        / network_baseline
    )

    estimated_speed_drop = min(
        35,
        5 + redirected_volume / max(network_baseline, 1) * 40
    )

    estimated_speed = max(5, network_speed - estimated_speed_drop)

    congestion_increase = min(
        100,
        15 + redirected_volume / max(baseline_volume, 1) * 50
    )

    if congestion_increase >= 70:
        risk = "🔴 HIGH"
        fallback_decision = (
            "🚫 **Do not proceed without a mitigation plan.** "
            "Congestion impact is severe — reroute emergency and transit "
            "traffic before implementation."
        )
    elif congestion_increase >= 40:
        risk = "🟠 MEDIUM"
        fallback_decision = (
            "⚠️ **Proceed with caution.** Moderate network impact expected. "
            "Pre-stage traffic signals on alternative corridors and notify "
            "commuters in advance."
        )
    else:
        risk = "🟢 LOW"
        fallback_decision = (
            "✅ **Safe to proceed.** Network-level impact is limited; "
            "standard monitoring should be sufficient."
        )

    result = {
        "period": selected_period,
        "affected_corridor": affected_corridor,
        "baseline_volume": baseline_volume,
        "baseline_speed": baseline_speed,
        "redirected_volume": redirected_volume,
        "redirect_fraction": REDIRECT_FRACTION,
        "network_baseline": network_baseline,
        "network_speed": network_speed,
        "estimated_speed": estimated_speed,
        "congestion_increase": congestion_increase,
        "risk": risk,
        "decision": fallback_decision,
        "alternatives": top_alternatives,
        "used_ai_parsing": used_ai_parsing,
        "used_ai_decision": False
    }

    ai_decision = generate_decision_text_with_gemini(gemini_client, result)
    if ai_decision:
        result["decision"] = ai_decision
        result["used_ai_decision"] = True

    return result


# -----------------------------
# TRAFFICVERSE UI
# -----------------------------

st.title("🚦 TrafficVerse")

st.subheader("Multi-Agent Conversational Traffic Simulation")

st.write(
    "Simulate traffic interventions and explore their "
    "potential impact before deploying them on real roads."
)


try:
    traffic_data = load_traffic_data()
    st.success(
        f"✅ Connected to BigQuery successfully — "
        f"{len(traffic_data)} traffic records loaded."
    )
except Exception as e:
    st.error("Could not connect to BigQuery.")
    st.code(str(e))
    st.stop()

gemini_client = get_gemini_client()

if gemini_client is None:
    st.warning(
        "⚠️ GEMINI_API_KEY not found — running in rule-based fallback mode. "
        "Set GEMINI_API_KEY as an environment variable or Streamlit secret "
        "to enable Gemini-powered scenario parsing and recommendations."
    )


st.markdown("### 🧠 Describe your traffic scenario")

scenario = st.text_area(
    "What would you like to simulate?",
    placeholder=(
        "Example: Close Outer Ring Road near Bellandur "
        "for 30 minutes during morning peak."
    ),
    height=100
)


if st.button("🚀 Run Traffic Simulation"):

    if not scenario.strip():
        st.warning("Please enter a traffic scenario first.")
    else:
        with st.spinner("Running counterfactual traffic simulation..."):
            result = run_simulation(traffic_data, scenario, gemini_client)

        st.success("Simulation completed successfully.")

        st.markdown("## 🧭 TrafficVerse AI Decision Panel")

        if result["risk"].startswith("🔴"):
            st.error(result["decision"])
        elif result["risk"].startswith("🟠"):
            st.warning(result["decision"])
        else:
            st.info(result["decision"])

        badge_bits = []
        if result["used_ai_parsing"]:
            badge_bits.append("🤖 Scenario parsed by Gemini")
        else:
            badge_bits.append("⚙️ Scenario parsed by rule-based fallback")

        if result["used_ai_decision"]:
            badge_bits.append("🤖 Recommendation generated by Gemini")
        else:
            badge_bits.append("⚙️ Recommendation from static template")

        st.caption(" · ".join(badge_bits))

        st.caption(
            f"Scenario: \u201c{scenario}\u201d — "
            f"{result['period']} — {result['affected_corridor']}"
        )

        st.markdown("## 📊 Before vs. After Comparison")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Affected Corridor",
                result["affected_corridor"]
            )

        with col2:
            speed_delta = result["estimated_speed"] - result["network_speed"]
            st.metric(
                "Network Speed",
                f"{result['estimated_speed']:.1f} km/h",
                delta=f"{speed_delta:.1f} km/h",
                delta_color="inverse"
            )

        with col3:
            st.metric(
                "Redirected Traffic",
                f"{result['redirected_volume']:.0f} veh",
                delta=f"{result['redirect_fraction'] * 100:.0f}% of baseline",
                delta_color="off"
            )

        with col4:
            st.metric(
                "Risk Level",
                result["risk"]
            )

        st.write(
            f"**Baseline network speed:** {result['network_speed']:.1f} km/h "
            f"→ **Estimated after closure:** {result['estimated_speed']:.1f} km/h"
        )
        st.write(
            f"**Congestion increase:** {result['congestion_increase']:.1f}%"
        )

        st.markdown("## 📈 Congestion Impact")

        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            speed_fig = styled_bar_chart(
                ["Baseline", "After Closure"],
                [result["network_speed"], result["estimated_speed"]],
                ylabel="Speed (km/h)"
            )
            st.pyplot(speed_fig, use_container_width=True)

        with chart_col2:
            volume_fig = styled_bar_chart(
                ["Baseline Volume", "Redirected Volume"],
                [result["baseline_volume"], result["redirected_volume"]],
                ylabel="Vehicles"
            )
            st.pyplot(volume_fig, use_container_width=True)

        st.markdown("## 🛣️ Recommended Alternative Corridors")

        alternatives = result["alternatives"]

        if not alternatives.empty:

            display_data = alternatives[
                ["corridor", "total_volume", "average_speed", "suitability_score"]
            ].copy()

            display_data.columns = [
                "Corridor",
                "Traffic Volume",
                "Average Speed (km/h)",
                "Suitability Score"
            ]

            display_data["Suitability Score"] = display_data[
                "Suitability Score"
            ].round(1)

            display_data.index.name = "Rank"

            st.dataframe(
                display_data,
                use_container_width=True
            )
        else:
            st.write("No alternative corridors available for this period.")

        st.markdown("## 🚑 Emergency Routing Recommendation")

        if result["risk"].startswith("🔴"):
            st.error(
                "Avoid routing emergency vehicles through the affected "
                "corridor. Use the highest-ranked alternative corridor above."
            )
        elif result["risk"].startswith("🟠"):
            st.warning(
                "Emergency routing should prioritize alternative corridors "
                "and avoid the affected corridor where possible."
            )
        else:
            st.info(
                "The simulated intervention shows relatively low "
                "network-level risk. Emergency routing can continue with "
                "normal monitoring."
            )

        with st.expander("⚙️ Simulation Assumptions & Methodology"):
            st.markdown(
                f"""
- **Redirect fraction:** {result['redirect_fraction'] * 100:.0f}% of the
  affected corridor's baseline traffic is assumed to divert to other
  corridors when it is closed or restricted.
- **Speed drop model:** Estimated network speed drop scales with the
  redirected volume relative to total network volume, capped at 35 km/h.
- **Congestion increase:** Scales with redirected volume relative to the
  affected corridor's own baseline volume, capped at 100%.
- **Alternative ranking:** Corridors are ranked by a suitability score
  combining higher average speed and lower existing traffic volume —
  corridors that are faster and less congested rank higher.
- **Data source:** BigQuery table `traffic_volume_profiles`
  ({int(result['network_baseline'])} total vehicles across the network
  in the selected period).
                """
            )

        st.caption(
            "TrafficVerse MVP: counterfactual estimates are based on the "
            "current traffic dataset and simulation assumptions. They are "
            "not yet calibrated against live traffic conditions."
        )
