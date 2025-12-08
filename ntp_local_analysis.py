#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

"""
Local NTP Server Analysis
Author: elvisimprsntr + Copilot
Date: 2025-12-08

Description:
- Parses loopstats, peerstats, and clockstats files
- Visualizes offset, jitter, frequency drift
- Compares NMEA vs PPS timing
- Generates compliance scoring and correlation plots
- Dashboard-style summary

Dependencies:
- Python 3.11
- pandas==2.2.2
- matplotlib==3.9.2
- seaborn==0.13.2
"""

# --- File Paths ---
base = Path(__file__).parent
loop_file = base / "loopstats"
peer_file = base / "peerstats"
clock_file = base / "clockstats"

# --- Parsing Functions ---
def parse_loopstats(path):
    cols = ["mjd", "seconds", "offset", "frequency", "jitter", "stability", "poll"]
    return pd.read_csv(path, sep=r"\s+", names=cols)

def parse_peerstats(path):
    cols = ["mjd", "seconds", "peer", "status", "offset", "delay", "dispersion", "jitter"]
    return pd.read_csv(path, sep=r"\s+", names=cols)

def parse_clockstats(path):
    return pd.read_csv(path, sep=r"\s+", names=["mjd","seconds","refclock","rest"], engine="python")

# --- Convert MJD + seconds to datetime ---
def mjd_to_datetime(mjd, seconds):
    mjd = pd.to_numeric(mjd, errors="coerce")
    seconds = pd.to_numeric(seconds, errors="coerce")
    return pd.to_datetime("1858-11-17") + pd.to_timedelta(mjd, unit="D") + pd.to_timedelta(seconds, unit="s")

# --- Load Data ---
loop = parse_loopstats(loop_file)
peer = parse_peerstats(peer_file)
clock = parse_clockstats(clock_file)

loop["ts"] = mjd_to_datetime(loop["mjd"], loop["seconds"])
peer["ts"] = mjd_to_datetime(peer["mjd"], peer["seconds"])
clock["ts"] = mjd_to_datetime(clock["mjd"], clock["seconds"])

# --- Compliance Thresholds for Local PPS ---
THRESHOLD_OFFSET = 0.00005   # 50 microseconds
THRESHOLD_JITTER = 0.00002   # 20 microseconds

# --- Compliance Scoring ---
peer_stats = peer.groupby("peer").agg(
    mean_offset=("offset", lambda x: abs(x).mean()),
    jitter=("offset","std"),
    samples=("offset","count"),
    outliers=("offset", lambda x: (abs(x) > THRESHOLD_OFFSET).sum())
)

peer_stats["accuracy_score"] = 1 - (peer_stats["mean_offset"] / THRESHOLD_OFFSET)
peer_stats["stability_score"] = 1 - (peer_stats["jitter"] / THRESHOLD_JITTER)
peer_stats["outlier_penalty"] = peer_stats["outliers"] / peer_stats["samples"]
peer_stats["monitor_score"] = (
    0.5*peer_stats["accuracy_score"] +
    0.4*peer_stats["stability_score"] -
    0.1*peer_stats["outlier_penalty"]
)

print("\nLocal PPS Compliance Scoring Table:")
print(peer_stats.sort_values("monitor_score", ascending=False))

# --- Loopstats Offset vs Time ---
plt.figure(figsize=(12,6))
plt.plot(loop["ts"], loop["offset"], ".", alpha=0.4, label="Offset samples")
rolling_mean = loop.set_index("ts")["offset"].rolling("1h").mean()
plt.plot(rolling_mean.index, rolling_mean.values, color="red", linewidth=2, label="Rolling mean (1h)")
plt.axhline(0, color="black", linewidth=0.8)
plt.title("Loopstats Offset vs Time")
plt.xlabel("Time")
plt.ylabel("Offset (s)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("loopstats_offset_vs_time.png")

# --- Frequency Drift vs Time ---
plt.figure(figsize=(12,6))
plt.plot(loop["ts"], loop["frequency"], alpha=0.6)
plt.title("Frequency Drift vs Time")
plt.xlabel("Time")
plt.ylabel("Frequency Drift (ppm)")
plt.grid(True)
plt.tight_layout()
plt.savefig("loopstats_frequency_vs_time.png")

# --- Peer Offset vs Time ---
plt.figure(figsize=(12,6))
sns.lineplot(x="ts", y="offset", hue="peer", data=peer, marker="o")
plt.title("Peer Offset vs Time")
plt.xlabel("Time")
plt.ylabel("Offset (s)")
plt.grid(True)
plt.tight_layout()
plt.savefig("peerstats_offset_vs_time.png")

# --- Peer Jitter Distribution ---
plt.figure(figsize=(8,6))
sns.boxplot(x="peer", y="jitter", data=peer)
plt.xticks(rotation=90)
plt.title("Peer Jitter Distribution")
plt.xlabel("Peer")
plt.ylabel("Jitter (s)")
plt.tight_layout()
plt.savefig("peerstats_jitter_distribution.png")

# --- NMEA vs PPS Offset ---
nmea_msgs = clock[clock["rest"].str.contains("GPGGA", na=False)].copy()
pps_peer = peer[peer["peer"].str.contains("127.127.20.0", na=False)].copy()

plt.figure(figsize=(12,6))
plt.plot(nmea_msgs["ts"], [0]*len(nmea_msgs), "o", label="NMEA messages")
plt.plot(pps_peer["ts"], pps_peer["offset"], ".", alpha=0.5, label="PPS offsets")
plt.title("NMEA vs PPS Timing")
plt.xlabel("Time")
plt.ylabel("Offset (s)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("nmea_vs_pps_offset.png")

# --- Correlation Matrix ---
corr_df = pd.DataFrame({
    "offset": loop["offset"],
    "frequency": loop["frequency"],
    "jitter": loop["jitter"]
})
pps_off = peer["offset"]
min_len = min(len(corr_df), len(pps_off))
corr_df = corr_df.iloc[:min_len].copy()
corr_df["pps_offset"] = pps_off.iloc[:min_len].values
corr_df = corr_df.dropna()

plt.figure(figsize=(7,6))
sns.heatmap(corr_df.corr(), annot=True, cmap="coolwarm", center=0)
plt.title("Correlation Matrix: Offset, Frequency Drift, Jitter, PPS Offset")
plt.tight_layout()
plt.savefig("correlation_matrix_local_ntp.png")

# --- Extra Plots ---
plt.figure(figsize=(8,6))
plt.scatter(loop["offset"], loop["jitter"], alpha=0.5)
plt.title("Offset vs Jitter")
plt.xlabel("Offset (s)")
plt.ylabel("Jitter (s)")
plt.grid(True)
plt.tight_layout()
plt.savefig("offset_vs_jitter.png")

plt.figure(figsize=(8,6))
plt.hist(loop["frequency"].dropna(), bins=50, color="steelblue", edgecolor="black")
plt.title("Frequency Drift Distribution")
plt.xlabel("Frequency Drift (ppm)")
plt.ylabel("Count")
plt.grid(True)
plt.tight_layout()
plt.savefig("frequency_drift_histogram.png")

loop["hour"] = loop["ts"].dt.hour
pivot = loop.pivot_table(index="hour", values="offset", aggfunc="mean")
plt.figure(figsize=(6,6))
sns.heatmap(pivot, annot=True, cmap="coolwarm", center=0)
plt.title("Average Offset by Hour of Day")
plt.tight_layout()
plt.savefig("offset_by_hour_heatmap.png")

nmea_times = nmea_msgs["ts"].dropna()
pps_times = pps_peer["ts"].dropna().iloc[:len(nmea_times)]
if len(nmea_times) == len(pps_times) and len(nmea_times) > 0:
    delta_ms = (nmea_times.values - pps_times.values).astype("timedelta64[ms]").astype(float)
    plt.figure(figsize=(8,6))
    plt.hist(delta_ms, bins=50, color="darkred", edgecolor="black")
    plt.title("NMEA vs PPS Offset Distribution")
    plt.xlabel("Offset (ms)")
    plt.ylabel("Count")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("nmea_vs_pps_histogram.png")

rolling_std = loop.set_index("ts")["offset"].rolling("10min").std()
plt.figure(figsize=(12,6))
plt.plot(rolling_std.index, rolling_std.values, color="purple")
plt.title("Rolling Stability (10 min std of offset)")
plt.xlabel("Time")
plt.ylabel("Std Dev (s)")
plt.grid(True)
plt.tight_layout()
plt.savefig("rolling_stability.png")

# --- Dashboard (2x3 grid) ---
fig, axes = plt.subplots(2, 3, figsize=(20,12))

# Panel 1: Loopstats Offset
axes[0,0].plot(loop["ts"], loop["offset"], ".", alpha=0.3)
axes[0,0].set_title("Loopstats Offset vs Time")
axes[0,0].set_xlabel("Time")
axes[0,0].set_ylabel("Offset (s)")
axes[0,0].grid(True)

# Panel 2: Frequency Drift
axes[0,1].plot(loop["ts"], loop["frequency"], ".", alpha=0.3)
axes[0,1].set_title("Frequency Drift vs Time")
axes[0,1].set_xlabel("Time")
axes[0,1].set_ylabel("Frequency Drift (ppm)")
axes[0,1].grid(True)

# Panel 3: Peer Offset
sns.lineplot(x="ts", y="offset", hue="peer", data=peer, ax=axes[0,2])
axes[0,2].set_title("Peer Offset vs Time")
axes[0,2].set_xlabel("Time")
axes[0,2].set_ylabel("Offset (s)")
axes[0,2].grid(True)

# Panel 4: Peer Jitter Distribution
sns.boxplot(x="peer", y="jitter", data=peer, ax=axes[1,0])
axes[1,0].set_title("Peer Jitter Distribution")
axes[1,0].set_xlabel("Peer")
axes[1,0].set_ylabel("Jitter (s)")
axes[1,0].tick_params(axis="x", rotation=90)

# Panel 5: NMEA vs PPS
axes[1,1].plot(nmea_msgs["ts"], [0]*len(nmea_msgs), "o", label="NMEA")
axes[1,1].plot(pps_peer["ts"], pps_peer["offset"], ".", alpha=0.5, label="PPS")
axes[1,1].set_title("NMEA vs PPS Offset")
axes[1,1].set_xlabel("Time")
axes[1,1].set_ylabel("Offset (s)")
axes[1,1].legend()
axes[1,1].grid(True)

# Panel 6: Correlation Matrix
sns.heatmap(corr_df.corr(), annot=True, cmap="coolwarm", center=0, ax=axes[1,2])
axes[1,2].set_title("Correlation Matrix")

plt.tight_layout()
plt.savefig("ntp_local_dashboard.png")

# --- Final Output ---
print("Analysis complete. Plots saved:")
for name in [
    "loopstats_offset_vs_time.png",
    "loopstats_frequency_vs_time.png",
    "peerstats_offset_vs_time.png",
    "peerstats_jitter_distribution.png",
    "nmea_vs_pps_offset.png",
    "correlation_matrix_local_ntp.png",
    "offset_vs_jitter.png",
    "frequency_drift_histogram.png",
    "offset_by_hour_heatmap.png",
    "nmea_vs_pps_histogram.png",
    "rolling_stability.png",
    "ntp_local_dashboard.png",
]:
    print(f" - {name}")
