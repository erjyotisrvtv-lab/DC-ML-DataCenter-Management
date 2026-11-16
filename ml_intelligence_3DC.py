
"""3-DC read-only ML intelligence: history, forecasting, risk,
fault correlation and synthetic evaluation.

Place beside:
    dc_metrics.csv
    ml_detection_3DC_from_original_UPDATED.py

Run:
    python ml_intelligence_3DC.py
    python ml_intelligence_3DC.py --self-test

No router configuration commands are sent.
"""

from pathlib import Path
from datetime import datetime
import argparse
import importlib.util
import os
import tempfile

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest


ROOT = Path(__file__).resolve().parent
BASE = ROOT / "ml_detection_3DC_from_original_UPDATED.py"
FEATURES = [
    "cpu_percent",
    "memory_percent",
    "input_kbps",
    "output_kbps",
]


def core():
    if not BASE.exists():
        raise FileNotFoundError(
            f"Copy {BASE.name} beside this script"
        )

    spec = importlib.util.spec_from_file_location(
        "existing_ml_engine", BASE
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def save_atomic(frame, name):
    with tempfile.NamedTemporaryFile(
        mode="w",
        dir=ROOT,
        prefix=".intelligence_",
        suffix=".csv",
        delete=False,
        encoding="utf-8",
        newline="",
    ) as f:
        tmp = Path(f.name)
        frame.to_csv(f, index=False)

    try:
        os.replace(tmp, ROOT / name)
    finally:
        tmp.unlink(missing_ok=True)


def read_csv(name):
    path = ROOT / name

    if not path.exists():
        return pd.DataFrame()

    try:
        return pd.read_csv(path, on_bad_lines="skip")
    except (
        OSError,
        pd.errors.ParserError,
        pd.errors.EmptyDataError,
    ):
        return pd.DataFrame()


def history_append(snapshot):
    old = read_csv("ml_history.csv")
    frame = pd.concat([old, snapshot], ignore_index=True)

    frame = frame.drop_duplicates(
        ["evaluated_at", "router"],
        keep="last",
    )
    frame = frame.sort_values("evaluated_at").tail(30000)

    save_atomic(frame, "ml_history.csv")
    return frame


def severity(row):
    status = str(row.get("anomaly_status", ""))

    if status == "Anomaly":
        score = pd.to_numeric(
            row.get("anomaly_score"),
            errors="coerce",
        )
        return (
            "HIGH"
            if pd.notna(score) and score < -0.10
            else "MEDIUM"
        )

    if status == "Normal":
        return "NONE"

    return "UNKNOWN"


def forecasts(data, horizon_minutes=5):
    """
    Recent linear-trend forecasting for variable metrics.

    Constant metrics use persistence forecasting.
    These are illustrative forecasts, not trained ML predictions.
    """
    out = []

    for router in core().ROUTERS:
        group = data[data.router.eq(router)].sort_values(
            "timestamp"
        )

        for metric in ["cpu_percent", "memory_percent"]:
            valid = (
                group[["timestamp", metric]]
                .dropna()
                .tail(40)
                .copy()
            )

            row = dict(
                router=router,
                metric=metric,
                horizon_minutes=horizon_minutes,
                method="recent_linear_trend",
                prediction=np.nan,
                current=np.nan,
                n_samples=len(valid),
                mae_backtest=np.nan,
                status="INSUFFICIENT_DATA",
            )

            if (
                len(valid) >= 12
                and valid[metric].nunique() > 1
            ):
                seconds = (
                    valid.timestamp
                    - valid.timestamp.iloc[0]
                ).dt.total_seconds().to_numpy(dtype=float)

                y = valid[metric].to_numpy(dtype=float)

                if seconds[-1] > 0:
                    cut = max(8, int(len(y) * 0.75))
                    xfit = seconds[:cut] / 60

                    if np.ptp(xfit) > 0:
                        coef = np.polyfit(
                            xfit,
                            y[:cut],
                            1,
                        )

                        heldout = np.polyval(
                            coef,
                            seconds[cut:] / 60,
                        )

                        row["mae_backtest"] = round(
                            float(
                                np.mean(
                                    np.abs(
                                        heldout - y[cut:]
                                    )
                                )
                            ),
                            4,
                        )

                        full_coef = np.polyfit(
                            seconds / 60,
                            y,
                            1,
                        )

                        pred = float(
                            np.polyval(
                                full_coef,
                                seconds[-1] / 60
                                + horizon_minutes,
                            )
                        )

                        row.update(
                            prediction=round(
                                float(np.clip(pred, 0, 100)),
                                3,
                            ),
                            current=round(float(y[-1]), 3),
                            status="FORECAST",
                            timestamp=(
                                valid.timestamp.iloc[-1]
                                .isoformat()
                            ),
                        )

            # Persistence forecasting for constant readings.
            if (
                len(valid) >= 12
                and valid[metric].nunique() == 1
                and valid["timestamp"].nunique() >= 2
            ):
                current_value = float(
                    valid[metric].iloc[-1]
                )

                row.update(
                    method="persistence",
                    prediction=round(current_value, 3),
                    current=round(current_value, 3),
                    mae_backtest=0.0,
                    status="FORECAST",
                    timestamp=(
                        valid.timestamp.iloc[-1].isoformat()
                    ),
                )

            out.append(row)

    return pd.DataFrame(out)


def fault_evidence():
    """
    Only flag explicitly inventoried interfaces.
    """
    interface = read_csv("interface_health.csv")
    inventory = read_csv("interface_inventory.csv")
    results = []

    required_interface = {
        "router",
        "interface",
        "timestamp",
        "admin_status",
        "protocol_status",
    }
    required_inventory = {
        "router",
        "interface",
        "monitor",
    }

    if (
        not interface.empty
        and not inventory.empty
        and required_interface.issubset(interface.columns)
        and required_inventory.issubset(inventory.columns)
    ):
        interface["timestamp"] = pd.to_datetime(
            interface.timestamp,
            errors="coerce",
        )

        interface = (
            interface.dropna(subset=["timestamp"])
            .sort_values("timestamp")
            .drop_duplicates(
                ["router", "interface"],
                keep="last",
            )
        )

        inventory = inventory[
            inventory.monitor.astype(str)
            .str.lower()
            .str.strip()
            .isin(["yes", "true", "1"])
        ]

        for item in (
            inventory[["router", "interface"]]
            .drop_duplicates()
            .itertuples(index=False)
        ):
            matched = interface[
                (interface.router == item.router)
                & (interface.interface == item.interface)
            ]

            if matched.empty:
                state = "UNKNOWN"
            else:
                last = matched.iloc[-1]

                age = (
                    pd.Timestamp.now()
                    - last.timestamp
                ).total_seconds()

                if not 0 <= age <= 300:
                    state = "STALE"
                else:
                    admin_up = (
                        str(last.admin_status)
                        .lower()
                        .strip()
                        == "up"
                    )
                    protocol_up = (
                        str(last.protocol_status)
                        .lower()
                        .strip()
                        == "up"
                    )

                    state = (
                        "UP"
                        if admin_up and protocol_up
                        else "DOWN"
                    )

            results.append(
                dict(
                    router=item.router,
                    interface=item.interface,
                    link_status=state,
                )
            )

    return pd.DataFrame(
        results,
        columns=[
            "router",
            "interface",
            "link_status",
        ],
    )


def routing_observations():
    """
    Identify observed non-healthy routing peers.
    Missing expected peers require a separate inventory.
    """
    routing = read_csv("routing_health.csv")

    needed = {
        "router",
        "protocol",
        "state",
        "timestamp",
    }

    if routing.empty or not needed.issubset(
        routing.columns
    ):
        return {}

    routing["timestamp"] = pd.to_datetime(
        routing.timestamp,
        errors="coerce",
    )

    routing = routing.dropna(subset=["timestamp"])

    if routing.empty:
        return {}

    newest = routing.timestamp.max()

    routing = routing[
        routing.timestamp.ge(
            newest - pd.Timedelta(minutes=3)
        )
    ]

    routing = routing[
        (
            pd.Timestamp.now() - routing.timestamp
        )
        .dt.total_seconds()
        .between(0, 300)
    ]

    observed = {}

    for r in routing.itertuples(index=False):
        protocol = str(r.protocol).upper().strip()
        state = str(r.state).upper().strip()

        if protocol == "OSPF":
            healthy = "FULL" in state
        elif protocol == "BGP":
            healthy = (
                "ESTABLISHED" in state
                or state.isdigit()
            )
        else:
            healthy = True

        if protocol in ("OSPF", "BGP") and not healthy:
            router = str(r.router).strip().upper()
            observed.setdefault(router, []).append(
                f"{protocol}:{state}"
            )

    return observed


def correlation(snapshot, faults):
    rows = []
    routing_alerts = routing_observations()

    for record in snapshot.to_dict("records"):
        router = record["router"]

        if not faults.empty:
            f = faults[faults.router.eq(router)]
        else:
            f = pd.DataFrame()

        down = (
            f[f.link_status.eq("DOWN")]
            if not f.empty
            else pd.DataFrame()
        )

        unknown = (
            f[
                f.link_status.isin(
                    ["STALE", "UNKNOWN"]
                )
            ]
            if not f.empty
            else pd.DataFrame()
        )

        ml = record["anomaly_status"]
        routing_issues = routing_alerts.get(
            str(router).strip().upper(),
            [],
        )

        fault_present = (
            not down.empty
            or bool(routing_issues)
        )

        if fault_present and ml == "Anomaly":
            level = "CORRELATED"
            recommendation = (
                "Check listed interfaces and metrics; "
                "co-occurrence is not causation"
            )

        elif fault_present:
            level = "NETWORK_FAULT"
            recommendation = (
                "Investigate interface failure even "
                "though ML did not flag an anomaly"
            )

        elif ml == "Anomaly":
            level = "ML_ONLY"
            recommendation = (
                "Inspect resource/traffic pattern; "
                "check other telemetry"
            )

        elif not unknown.empty or f.empty:
            level = "UNVERIFIED"
            recommendation = (
                "Interface baseline/observations "
                "missing or stale"
            )

        else:
            level = "NO_FLAG"
            recommendation = (
                "Continue monitoring; this is not "
                "a guarantee of health"
            )

        rows.append(
            dict(
                router=router,
                correlation=level,
                ml_status=ml,
                monitored_down=len(down),
                unknown_interfaces=len(unknown),
                failed_interfaces=(
                    ", ".join(
                        down.interface.astype(str)
                    )
                    if not down.empty
                    else ""
                ),
                nonhealthy_observed_routing=(
                    ", ".join(routing_issues)
                ),
                recommendation=recommendation,
            )
        )

    return pd.DataFrame(rows)


def risk_scores(snapshot, correlations):
    """
    Heuristic operations risk indicator (0-100).
    Not an ML failure probability.
    """
    merged = snapshot.merge(
        correlations,
        on="router",
        how="left",
    )

    merged["dc"] = merged.router.str.extract(
        r"^(DC[123])-"
    )

    rows = []

    for dc, g in merged.groupby("dc"):
        anomaly = int(
            g.anomaly_status.eq("Anomaly").sum()
        )

        down = int(
            g.monitored_down.fillna(0).sum()
        )

        unknown = int(
            (
                ~g.anomaly_status.isin(
                    ["Normal", "Anomaly"]
                )
            ).sum()
        )

        unverified = int(
            g.correlation.eq("UNVERIFIED").sum()
        )

        score = min(
            100,
            15 * anomaly
            + 30 * min(down, 2)
            + 10 * unknown
            + 5 * unverified,
        )

        rows.append(
            dict(
                dc=dc,
                risk_score=score,
                ml_anomalies=anomaly,
                down_links=down,
                ml_unknown=unknown,
                unverified_routers=unverified,
                interpretation=(
                    "Heuristic triage score, "
                    "not failure probability"
                ),
            )
        )

    return pd.DataFrame(rows)


def synthetic_evaluation(data):
    """
    Offline holdout stress test.
    Injected spikes are synthetic, not real fault labels.
    Live CSV input is not modified.
    """
    rows = []

    for router, group in data.groupby("router"):
        group = (
            group.sort_values("timestamp")
            .tail(250)
        )

        fields = [
            f
            for f in [
                "cpu_percent",
                "memory_percent",
            ]
            if (
                group[f].notna().sum() >= 50
                and group[f].nunique() > 1
            )
        ]

        if not fields:
            continue

        valid = group[fields].dropna()

        if len(valid) < 50:
            continue

        split = max(
            35,
            int(len(valid) * 0.7),
        )

        train = valid.iloc[:split].copy()
        test = valid.iloc[split:].copy()

        if len(test) < 10:
            continue

        model = IsolationForest(
            n_estimators=100,
            contamination=0.05,
            random_state=42,
            n_jobs=1,
        ).fit(train)

        clean_pred = (
            model.predict(test) == -1
        )

        stressed = test.copy()

        target = (
            "cpu_percent"
            if "cpu_percent" in fields
            else "memory_percent"
        )

        stressed[target] = np.maximum(
            stressed[target].to_numpy(),
            95.0,
        )

        stressed[target] = np.minimum(
            stressed[target],
            100.0,
        )

        stress_pred = (
            model.predict(stressed) == -1
        )

        tp = int(stress_pred.sum())
        fn = int(len(stress_pred) - tp)
        fp = int(clean_pred.sum())
        tn = int(len(clean_pred) - fp)

        rows.append(
            dict(
                router=router,
                normal_test=len(clean_pred),
                synthetic_test=len(stress_pred),
                tp=tp,
                fn=fn,
                fp=fp,
                tn=tn,
                precision=(
                    round(tp / (tp + fp), 3)
                    if tp + fp
                    else np.nan
                ),
                recall=(
                    round(tp / (tp + fn), 3)
                    if tp + fn
                    else np.nan
                ),
                false_positive_rate=(
                    round(fp / (fp + tn), 3)
                    if fp + tn
                    else np.nan
                ),
                test_type=(
                    f"OFFLINE SYNTHETIC {target}>=95; "
                    "NOT real fault labels"
                ),
            )
        )

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--self-test",
        action="store_true",
        help=(
            "Also run offline synthetic "
            "anomaly evaluation"
        ),
    )

    args = parser.parse_args()

    base = core()
    data = base.load_metrics()

    snapshot = base.evaluate(data)

    snapshot["severity"] = snapshot.apply(
        severity,
        axis=1,
    )

    base.atomic_write(
        snapshot,
        ROOT / "ml_results.csv",
    )

    history_append(snapshot)

    forecast = forecasts(data)
    save_atomic(
        forecast,
        "ml_forecast.csv",
    )

    faults = fault_evidence()

    correlated = correlation(
        snapshot,
        faults,
    )

    save_atomic(
        correlated,
        "ml_fault_correlation.csv",
    )

    save_atomic(
        risk_scores(snapshot, correlated),
        "dc_risk_scores.csv",
    )

    if args.self_test:
        evaluation = synthetic_evaluation(data)

        if not evaluation.empty:
            save_atomic(
                evaluation,
                "ml_model_evaluation.csv",
            )

            print(
                "Offline synthetic evaluation: "
                f"{len(evaluation)} router tests "
                "(not real incident labels)"
            )
        else:
            print(
                "Insufficient varied training data "
                "for synthetic evaluation"
            )

    print(
        f"[{datetime.now():%H:%M:%S}] "
        f"Evaluated {len(snapshot)} routers: "
        f"{snapshot.anomaly_status.value_counts().to_dict()}"
    )

    print(
        "Updated ml_results.csv, ml_history.csv, "
        "ml_forecast.csv, ml_fault_correlation.csv, "
        "dc_risk_scores.csv"
    )


if __name__ == "__main__":
    main()
