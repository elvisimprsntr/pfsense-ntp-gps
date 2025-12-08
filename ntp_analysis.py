#!/usr/bin/env python3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import LabelEncoder

"""
Data Analysis Script
Generated with assistance from Microsoft Copilot
Author: elvisimprsntr
Date: 2025-12-08

Description:
- Analyzes NTP benchmarking data
- Filters out servers with invalid RTT/offset
- Produces correlation matrix and time-of-day plots

Dependencies:
- Python 3.11
- pandas==2.2.2
- matplotlib==3.9.2
- seaborn==0.13.2

Data Source:
- Internal monitoring export (CSV)
"""

# --- Threshold Parameters ---
THRESHOLD_OFFSET = 0.010   # 10ms offset compliance
THRESHOLD_JITTER = 0.010   # 10ms jitter compliance
THRESHOLD_RTT = 100        # 100ms RTT compliance

# Load CSV
df = pd.read_csv("ntp.txt")

# Drop rows with missing offsets
df = df.dropna(subset=["offset"])

# Convert timestamp column to datetime
df["ts"] = pd.to_datetime(df["ts"])

# Derive country code from monitor_name (first 2 letters)
df["country_code"] = df["monitor_name"].str[:2]

# --- NEW FILTER: exclude candidate servers by monitor_name ---
df = df[~df["monitor_name"].str.contains("candidate", case=False)]

# --- 1. Offset vs Time (overall, with rolling mean) ---
plt.figure(figsize=(12,6))
plt.plot(df["ts"], df["offset"], marker=".", linestyle="none", alpha=0.4, label="Offset samples")

df_sorted = df.sort_values("ts")
rolling_mean = df_sorted.set_index("ts")["offset"].rolling("1h").mean()
plt.plot(rolling_mean.index, rolling_mean.values, color="red", linewidth=2, label="Rolling mean (1h)")

plt.axhline(0, color="black", linewidth=0.8)
plt.title("NTP Offset vs Time, Rolling Mean")
plt.xlabel("Time")
plt.ylabel("Offset (seconds)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("offset_vs_time_filtered.png")

# --- 2. Offset Histogram (overall) ---
plt.figure(figsize=(8,6))
plt.hist(df["offset"], bins=50, color="steelblue", edgecolor="black")
plt.title("Offset Distribution")
plt.xlabel("Offset (seconds)")
plt.ylabel("Count")
plt.grid(True)
plt.tight_layout()
plt.savefig("offset_histogram_filtered.png")

# --- 3. RTT vs Offset Scatterplot ---
plt.figure(figsize=(8,6))
plt.scatter(df["rtt"], df["offset"], alpha=0.6)
plt.title("RTT vs Offset")
plt.xlabel("RTT (ms)")
plt.ylabel("Offset (seconds)")
plt.grid(True)
plt.tight_layout()
plt.savefig("rtt_vs_offset_filtered.png")

# --- 4. Outlier listing (> threshold) ---
outliers = df[abs(df["offset"]) > THRESHOLD_OFFSET]
print(f"Outliers (offset > {THRESHOLD_OFFSET*1000:.0f}ms)")
print(outliers[["ts","monitor_name","offset","rtt"]])

# --- 5. Offset vs Country boxplots ---
plt.figure(figsize=(12,6))
countries_sorted = sorted(df["country_code"].dropna().unique())
sns.boxplot(x="country_code", y="offset", data=df, order=countries_sorted)
plt.xticks(rotation=90)
plt.title("Offset Distribution by Country Code")
plt.xlabel("Country Code")
plt.ylabel("Offset (seconds)")
plt.tight_layout()
plt.savefig("offset_boxplot_per_country_filtered.png")

# --- 6. RTT vs Country Code (sorted alphabetically) ---
plt.figure(figsize=(10,6))
sns.boxplot(x="country_code", y="rtt", data=df, order=countries_sorted)
plt.xticks(rotation=90)
plt.title("RTT Distribution by Country Code")
plt.xlabel("Country Code")
plt.ylabel("RTT (ms)")
plt.tight_layout()
plt.savefig("rtt_vs_country_filtered.png")

# --- 7. Score vs Time ---
plt.figure(figsize=(12,6))
plt.plot(df["ts"], df["score"], marker=".", linestyle="none", alpha=0.6, color="darkred")
plt.title("Score vs Time")
plt.xlabel("Time")
plt.ylabel("Score")
plt.grid(True)
plt.tight_layout()
plt.savefig("score_vs_time_filtered.png")

# --- 8. Correlation Matrix with Label-encoded Country Codes + Hour of Day ---
le = LabelEncoder()
df["country_encoded"] = le.fit_transform(df["country_code"].astype(str))

# Add hour of day as numeric feature
df["hour"] = df["ts"].dt.hour

# Build correlation matrix including hour
corr_label = df[["offset","rtt","score","country_encoded","hour"]].corr()

plt.figure(figsize=(7,6))
sns.heatmap(corr_label, annot=True, cmap="coolwarm", center=0)
plt.title("Correlation Matrix (with Country + Hour of Day)")
plt.tight_layout()
plt.savefig("correlation_matrix_with_country_hour.png")

# --- 9. Peer Summary Table (samples, outliers, jitter) ---
peer_summary = df.groupby("monitor_name").agg(
    samples=("offset","count"),
    outliers=("offset", lambda x: (abs(x) > THRESHOLD_OFFSET).sum()),
    jitter=("offset","std")
).sort_values("outliers", ascending=False)

print("\nPeer Summary (samples, outliers, jitter):")
print(peer_summary)

# --- 10. Time-of-Day Offset Plot ---
df["hour"] = df["ts"].dt.hour
plt.figure(figsize=(12,6))
sns.boxplot(x="hour", y="offset", data=df)
plt.title("Offset Distribution by Hour of Day")
plt.xlabel("Hour of Day")
plt.ylabel("Offset (seconds)")
plt.grid(True)
plt.tight_layout()
plt.savefig("offset_vs_hour_filtered.png")

# --- 11. Monitor Scoring ---
peer_stats = df.groupby("monitor_name").agg(
    mean_offset=("offset", lambda x: abs(x).mean()),
    jitter=("offset","std"),
    median_rtt=("rtt","median"),
    samples=("offset","count"),
    outliers=("offset", lambda x: (abs(x) > THRESHOLD_OFFSET).sum())
)

peer_stats["accuracy_score"] = 1 - (peer_stats["mean_offset"] / THRESHOLD_OFFSET)
peer_stats["stability_score"] = 1 - (peer_stats["jitter"] / THRESHOLD_JITTER)
peer_stats["latency_score"] = 1 - (peer_stats["median_rtt"] / THRESHOLD_RTT)
peer_stats["outlier_penalty"] = peer_stats["outliers"] / peer_stats["samples"]

peer_stats["monitor_score"] = (
    0.4*peer_stats["accuracy_score"] +
    0.3*peer_stats["stability_score"] +
    0.2*peer_stats["latency_score"] -
    0.1*peer_stats["outlier_penalty"]
)

print("\nMonitor Scoring Table:")
print(peer_stats.sort_values("monitor_score", ascending=False))

# --- 12. Monitor Score Leaderboard (bar chart) ---
plt.figure(figsize=(12,6))
peer_stats_sorted = peer_stats.sort_values("monitor_score", ascending=False)
sns.barplot(
    x=peer_stats_sorted.index,
    y=peer_stats_sorted["monitor_score"],
    hue=peer_stats_sorted.index,
    palette="viridis",
    legend=False
)
plt.xticks(rotation=90)
plt.title("Monitor Score Leaderboard")
plt.xlabel("Monitor")
plt.ylabel("Composite Score")
plt.tight_layout()
plt.savefig("monitor_score_leaderboard.png")

# --- 13. Country-level Leaderboard ---
country_stats = peer_stats.copy()
country_stats["country_code"] = country_stats.index.str[:2]
country_scores = country_stats.groupby("country_code")["monitor_score"].mean().sort_values(ascending=False)

print("\nCountry-level Scoring Table:")
print(country_scores)

plt.figure(figsize=(10,6))
sns.barplot(
    x=country_scores.index,
    y=country_scores.values,
    hue=country_scores.index,
    palette="plasma",
    legend=False
)
plt.title("Country-level Monitor Score Leaderboard")
plt.xlabel("Country Code")
plt.ylabel("Average Composite Score")
plt.tight_layout()
plt.savefig("country_score_leaderboard.png")

# --- 14. Compliance Threshold Summary per Country ---
country_compliance = (
    df.groupby("country_code")["offset"]
      .agg(lambda x: (abs(x) < THRESHOLD_OFFSET).mean() * 100)
      .sort_values(ascending=False)
)

print(f"\nCompliance Threshold Summary per Country (% samples within {THRESHOLD_OFFSET*1000:.0f}ms):")
print(country_compliance)

plt.figure(figsize=(10,6))
sns.barplot(
    x=country_compliance.index,
    y=country_compliance.values,
    hue=country_compliance.index,
    palette="coolwarm",
    legend=False
)
plt.title(f"Compliance Threshold per Country (Offset < {THRESHOLD_OFFSET*1000:.0f}ms)")
plt.xlabel("Country Code")
plt.ylabel("Compliance (%)")
plt.tight_layout()
plt.savefig("country_compliance_summary.png")

# --- 15. Combined Dashboard-style Plot (now 2x3 grid with correlation matrix) ---
fig, axes = plt.subplots(2, 3, figsize=(20,12))

# Panel 1: Offset vs Time (with rolling mean)
axes[0,0].plot(df["ts"], df["offset"], marker=".", linestyle="none", alpha=0.3, label="Offset samples")
rolling_mean = df_sorted.set_index("ts")["offset"].rolling("1h").mean()
axes[0,0].plot(rolling_mean.index, rolling_mean.values, color="red", linewidth=2, label="Rolling mean (1h)")
axes[0,0].axhline(0, color="black", linewidth=0.8)
axes[0,0].set_title("Offset vs Time")
axes[0,0].set_xlabel("Time")
axes[0,0].set_ylabel("Offset (s)")
axes[0,0].legend()
axes[0,0].grid(True)

# Panel 2: RTT Distribution by Country
countries_sorted = sorted(df["country_code"].dropna().unique())
sns.boxplot(x="country_code", y="rtt", data=df, order=countries_sorted, ax=axes[0,1])
axes[0,1].set_title("RTT Distribution by Country")
axes[0,1].set_xlabel("Country")
axes[0,1].set_ylabel("RTT (ms)")
axes[0,1].tick_params(axis="x", rotation=90)

# Panel 3: Monitor Score Leaderboard (top 15)
peer_stats_sorted = peer_stats.sort_values("monitor_score", ascending=False).head(15)
sns.barplot(
    x=peer_stats_sorted.index,
    y=peer_stats_sorted["monitor_score"],
    hue=peer_stats_sorted.index,
    palette="viridis",
    legend=False,
    ax=axes[0,2]
)
axes[0,2].set_title("Top 15 Monitor Scores")
axes[0,2].set_xlabel("Monitor")
axes[0,2].set_ylabel("Score")
axes[0,2].tick_params(axis="x", rotation=90)

# Panel 4: Country Compliance Summary
sns.barplot(
    x=country_compliance.index,
    y=country_compliance.values,
    hue=country_compliance.index,
    palette="coolwarm",
    legend=False,
    ax=axes[1,0]
)
axes[1,0].set_title(f"Compliance per Country (<{THRESHOLD_OFFSET*1000:.0f}ms Offset)")
axes[1,0].set_xlabel("Country")
axes[1,0].set_ylabel("Compliance (%)")
axes[1,0].tick_params(axis="x", rotation=90)

# Panel 5: Offset Distribution by Hour of Day
sns.boxplot(x="hour", y="offset", data=df, ax=axes[1,1])
axes[1,1].set_title("Offset Distribution by Hour of Day")
axes[1,1].set_xlabel("Hour")
axes[1,1].set_ylabel("Offset (s)")
axes[1,1].grid(True)

# Panel 6: Correlation Matrix (with hour + country)
corr_label = df[["offset","rtt","score","country_encoded","hour"]].corr()
sns.heatmap(corr_label, annot=True, cmap="coolwarm", center=0, ax=axes[1,2])
axes[1,2].set_title("Correlation Matrix (Country + Hour)")

plt.tight_layout()
plt.savefig("ntp_dashboard_extended.png")
