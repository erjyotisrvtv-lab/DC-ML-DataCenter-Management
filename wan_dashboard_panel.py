
from pathlib import Path

import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parent


def load_csv(filename):
    path = BASE / filename
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, ValueError, pd.errors.EmptyDataError):
        return pd.DataFrame()


def show_wan_dashboard():
    st.header("WAN BGP & ML Intelligence")
    st.caption(
        "Distributed Cloud Data Center Management "
        "| Routing Health | Failure Detection | ML Correlation"
    )

    bgp = load_csv("wan_bgp_peer_health.csv")
    events = load_csv("wan_bgp_events.csv")
    corr = load_csv("wan_ml_correlation.csv")
    ml = load_csv("ml_results.csv")

    if bgp.empty:
        st.warning("No WAN BGP monitoring data found.")
        return

    # Latest observation per monitored peer
    bgp = bgp.copy()
    bgp["timestamp"] = pd.to_datetime(
        bgp["timestamp"], errors="coerce"
    )
    bgp = bgp.sort_values("timestamp")
    latest = bgp.drop_duplicates(
        subset=["router", "neighbor_ip"], keep="last"
    ).copy()

    latest["healthy"] = (
        latest["bgp_status"].eq("ESTABLISHED")
        & latest["collection_status"].eq("SUCCESS")
        & latest["error"].fillna("").eq("")
    )

    healthy = int(latest["healthy"].sum())
    total = len(latest)

    failures = (
        int(events["event"].eq("FAILURE").sum())
        if not events.empty else 0
    )
    recoveries = (
        int(events["event"].eq("RECOVERY").sum())
        if not events.empty else 0
    )

    st.subheader("WAN Routing Health")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Healthy BGP Peers", f"{healthy}/{total}")
    c2.metric("WAN Routers", latest["router"].nunique())
    c3.metric("Failure Events", failures)
    c4.metric("Recovery Events", recoveries)

    last_time = bgp["timestamp"].max()
    st.caption(f"Last recorded collection: {last_time}")

    if healthy == total and total > 0:
        st.success("All monitored BGP peers were healthy at last collection.")
    else:
        st.warning(
            f"{total - healthy} BGP peer(s) unhealthy "
            "or not verified at last collection."
        )

    st.subheader("BGP Neighbor Status")

    columns = [
        "router", "neighbor_ip", "session_type",
        "bgp_status", "prefix_count",
        "session_uptime", "collection_status"
    ]

    st.dataframe(
        latest[columns],
        width="stretch",
        hide_index=True
    )

    st.subheader("BGP Failure & Recovery History")

    if not events.empty:
        st.dataframe(
            events.sort_values(
                "timestamp", ascending=False
            ),
            width="stretch",
            hide_index=True
        )

        counts = (
            events.groupby(["router", "event"])
            .size()
            .unstack(fill_value=0)
        )

        st.bar_chart(counts)
    else:
        st.info("No recorded BGP transitions.")

    st.subheader("ML Anomaly Monitoring")

    if not ml.empty and "anomaly_status" in ml:
        ml_counts = ml["anomaly_status"].value_counts()

        m1, m2, m3 = st.columns(3)

        m1.metric("Normal", int(ml_counts.get("Normal", 0)))
        m2.metric(
            "Insufficient Data",
            int(ml_counts.get("INSUFFICIENT_DATA", 0))
        )
        m3.metric(
            "ML Anomalies",
            int(ml_counts.get("Anomaly", 0))
        )

        visible = [
            col for col in [
                "router", "anomaly_status",
                "anomaly_score", "severity",
                "evaluated_at"
            ]
            if col in ml.columns
        ]

        st.dataframe(
            ml[visible],
            width="stretch",
            hide_index=True
        )
    else:
        st.info("ML evaluation data unavailable.")

    st.subheader("WAN + ML Correlation")

    if not corr.empty:
        st.dataframe(
            corr,
            width="stretch",
            hide_index=True
        )
        st.caption(
            "Correlation is based on recorded time windows. "
            "A matching event does not establish causation."
        )
    else:
        st.info("Run wan_ml_correlation.py to generate data.")

    st.caption(
        "Historical CSV monitoring. Refresh or rerun "
        "collectors for updated observations."
    )


if __name__ == "__main__":
    st.set_page_config(
        page_title="WAN BGP Intelligence",
        layout="wide"
    )
    show_wan_dashboard()
