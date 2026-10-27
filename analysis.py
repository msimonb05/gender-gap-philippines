from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

DATA_DIR = Path("data")
OUT_DIR = DATA_DIR / "analysis"

SEED = 20261026
N_BOOT = 10_000
CI_LEVEL = 0.95
ALPHA = 0.05
BASE_YEAR = 2006
END_YEAR = 2025
PRE = (2006, 2019)
POST = (2021, 2025)
SEASON_YEARS = (2022, 2025)
QUARTERLY_ROUND_MONTHS = [1, 4, 7, 10]

HYPOTHESES = [
    ("H1", "gap_pct", "poverty_incidence_pct"),
    ("H2", "gap_pct", "lit_gap_f_minus_m"),
    ("H3", "func_lit_rate_female", "poverty_incidence_pct"),
]


def load(name):
    return pd.read_csv(DATA_DIR / f"{name}.csv")


def holm(pvalues):
    p = np.asarray(pvalues, dtype=float)
    m = len(p)
    order = np.argsort(p)
    adjusted_sorted = np.maximum.accumulate((m - np.arange(m)) * p[order])
    adjusted = np.empty(m)
    adjusted[order] = np.minimum(adjusted_sorted, 1.0)
    return adjusted


assert np.allclose(holm([0.01, 0.04, 0.03]), [0.03, 0.06, 0.06]), "holm() self-check failed"


def parity_scorecard(annual):
    latest = annual[annual["year"] == END_YEAR]
    assert len(latest) == 1, f"no single annual row for {END_YEAR}"
    latest = latest.iloc[0]

    rows = []
    for label, col, higher_is in [
        ("Labor force participation rate", "lfpr", "better"),
        ("Employment rate", "emp_rate", "better"),
        ("Unemployment rate", "unemp_rate", "worse"),
        ("Underemployment rate", "underemp_rate", "worse"),
    ]:
        rows.append({
            "indicator": label,
            "period": str(END_YEAR),
            "female": latest[f"{col}_female"],
            "male": latest[f"{col}_male"],
            "higher_is": higher_is,
        })

    national_gap = load("national_wage_gap")["national_gap_pct"].iloc[0]
    rows.append({
        "indicator": "Average monthly wage (time-rated, full-time)",
        "period": "Aug 2024",
        "f_to_m": 1 - national_gap / 100,
        "higher_is": "better",
    })

    lit = load("national_literacy").iloc[0]
    rows.append({
        "indicator": "Functional literacy rate (10-64)",
        "period": "2024",
        "female": lit["func_lit_rate_female"],
        "male": lit["func_lit_rate_male"],
        "higher_is": "better",
    })

    enrollment = load("school_enrollment")
    for level in ["Primary", "Secondary", "Tertiary"]:
        latest_level = enrollment[enrollment["Level"] == level].sort_values("year_start").iloc[-1]
        rows.append({
            "indicator": f"Girls-to-boys ratio, {level.lower()}",
            "period": f"SY {latest_level['school_year']}",
            "f_to_m": latest_level["ratio"],
            "higher_is": "better",
        })

    df = pd.DataFrame(rows)
    df["f_to_m"] = df["f_to_m"].fillna(df["female"] / df["male"])
    assert df["f_to_m"].notna().all() and df["f_to_m"].gt(0).all(), "invalid female/male ratio"
    df["f_to_m"] = df["f_to_m"].round(3)
    df.to_csv(OUT_DIR / "scorecard.csv", index=False)
    return df


def labor_force_decomposition(annual):
    start = annual[annual["year"] == BASE_YEAR].iloc[0]
    end = annual[annual["year"] == END_YEAR].iloc[0]

    rows = []
    for sex in ["male", "female"]:
        p0, p1 = start[f"pop15_{sex}_thousands"], end[f"pop15_{sex}_thousands"]
        l0, l1 = start[f"lf_{sex}_thousands"], end[f"lf_{sex}_thousands"]
        r0, r1 = l0 / p0, l1 / p1
        dp, dr = p1 - p0, r1 - r0
        parts = {
            "population effect": r0 * dp,
            "participation effect": p0 * dr,
            "interaction": dp * dr,
        }
        total = l1 - l0
        assert abs(sum(parts.values()) - total) <= 1e-9 * abs(total), f"decomposition does not add up for {sex}"
        for component, value in parts.items():
            rows.append({"sex": sex, "component": component, "thousands": value, "share_of_change_pct": value / total * 100})
        rows.append({"sex": sex, "component": "total change", "thousands": total, "share_of_change_pct": 100.0})

    df = pd.DataFrame(rows).round(3)
    df.to_csv(OUT_DIR / "lf_decomposition.csv", index=False)
    return df


def lfpr_gap_trend(annual):
    df = annual[annual["year"].between(BASE_YEAR, END_YEAR)][["year", "lfpr_male", "lfpr_female"]].copy()
    df["gap_pts"] = df["lfpr_male"] - df["lfpr_female"]
    df["period"] = np.select(
        [df["year"].between(*PRE), df["year"].between(*POST)], ["pre", "post"], default="excluded"
    )
    df["fitted_gap_pts"] = np.nan

    rows = []
    for name, (first, last) in [("pre", PRE), ("post", POST)]:
        d = df[df["year"].between(first, last)]
        assert len(d) == last - first + 1, f"missing years in {name} period"
        fit = stats.linregress(d["year"], d["gap_pts"])
        t_crit = stats.t.ppf((1 + CI_LEVEL) / 2, len(d) - 2)
        rows.append({
            "period": f"{first}-{last}",
            "n_years": len(d),
            "slope_pts_per_year": fit.slope,
            "ci_low": fit.slope - t_crit * fit.stderr,
            "ci_high": fit.slope + t_crit * fit.stderr,
            "r_squared": fit.rvalue**2,
            "mean_gap_pts": d["gap_pts"].mean(),
        })
        df.loc[d.index, "fitted_gap_pts"] = fit.intercept + fit.slope * d["year"]

    trend = pd.DataFrame(rows).round(3)
    df.round(3).to_csv(OUT_DIR / "lfpr_gap_annual.csv", index=False)
    trend.to_csv(OUT_DIR / "lfpr_gap_trend.csv", index=False)
    return df, trend


def annual_vs_survey_mean(annual):
    monthly = load("labor_participation")
    monthly["year"] = monthly["date"].str[:4].astype(int)
    means = monthly.groupby("year")[["lfpr_male", "lfpr_female"]].mean()
    joined = annual.set_index("year")[["lfpr_male", "lfpr_female"]].join(
        means.add_suffix("_survey_mean"), how="inner"
    )
    joined = joined.loc[BASE_YEAR:END_YEAR]
    return max(
        (joined["lfpr_male"] - joined["lfpr_male_survey_mean"]).abs().max(),
        (joined["lfpr_female"] - joined["lfpr_female_survey_mean"]).abs().max(),
    )


def seasonality():
    m = load("labor_participation")
    m["date"] = pd.to_datetime(m["date"], format="%Y-%m")
    m = m[m["date"].dt.year.between(*SEASON_YEARS)].copy()
    m["year"] = m["date"].dt.year
    m["month"] = m["date"].dt.month

    counts = m.groupby("year").size()
    assert len(counts) == SEASON_YEARS[1] - SEASON_YEARS[0] + 1, "missing years in seasonality window"
    assert (counts == 12).all(), f"not 12 months per year: {counts.to_dict()}"

    long = m.melt(id_vars=["year", "month"], value_vars=["lfpr_male", "lfpr_female"], var_name="sex", value_name="lfpr")
    long["sex"] = long["sex"].map({"lfpr_male": "Male", "lfpr_female": "Female"})
    long["deviation_pts"] = long["lfpr"] - long.groupby(["sex", "year"])["lfpr"].transform("mean")

    out = (
        long.groupby(["sex", "month"])["deviation_pts"]
        .agg(mean_deviation_pts="mean", min_deviation_pts="min", max_deviation_pts="max")
        .reset_index()
        .round(3)
    )
    out.to_csv(OUT_DIR / "seasonality.csv", index=False)
    return out


def quarterly_round_bias(season):
    rounds = season[season["month"].isin(QUARTERLY_ROUND_MONTHS)]
    assert len(rounds) == 2 * len(QUARTERLY_ROUND_MONTHS), "missing round months in seasonality table"
    dev = rounds.groupby("sex")["mean_deviation_pts"].mean()
    out = pd.DataFrame([{
        "male_mean_deviation_pts": dev["Male"],
        "female_mean_deviation_pts": dev["Female"],
        "implied_gap_bias_pts": dev["Male"] - dev["Female"],
    }]).round(3)
    out.to_csv(OUT_DIR / "seasonality_round_months.csv", index=False)
    return out


def regional_correlations():
    wage = load("wage_gap_by_region")[["region", "gap_pct"]]
    lit = load("literacy_rate")
    lit["lit_gap_f_minus_m"] = lit["func_lit_rate_female"] - lit["func_lit_rate_male"]
    poverty = load("poverty_by_region")[["region", "poverty_incidence_pct"]]

    merged = (
        lit[["region", "func_lit_rate_female", "lit_gap_f_minus_m"]]
        .merge(poverty, on="region", how="inner", validate="one_to_one")
        .merge(wage, on="region", how="left", validate="one_to_one")
    )
    assert len(merged) == 18, f"expected 18 regions after merge, got {len(merged)}"
    assert merged["gap_pct"].isna().sum() == 1, "expected only NIR to lack a wage gap"

    rng = np.random.default_rng(SEED)
    rows = []
    for hid, x, y in HYPOTHESES:
        d = merged.dropna(subset=[x, y])
        result = stats.spearmanr(d[x], d[y])
        boot = stats.bootstrap(
            (d[x].to_numpy(), d[y].to_numpy()),
            lambda a, b: stats.spearmanr(a, b).statistic,
            paired=True,
            vectorized=False,
            n_resamples=N_BOOT,
            confidence_level=CI_LEVEL,
            method="percentile",
            rng=rng,
        )
        ci = boot.confidence_interval
        assert np.isfinite([ci.low, ci.high]).all(), f"bootstrap CI not finite for {hid}"
        rows.append({
            "hypothesis": hid,
            "x": x,
            "y": y,
            "n": len(d),
            "spearman_rho": result.statistic,
            "ci_low": ci.low,
            "ci_high": ci.high,
            "p_raw": result.pvalue,
        })

    out = pd.DataFrame(rows)
    assert out["n"].to_list() == [17, 17, 18], f"unexpected sample sizes: {out['n'].to_list()}"
    out["p_holm"] = holm(out["p_raw"])
    out["significant_after_holm"] = out["p_holm"] < ALPHA
    for col, alpha in [("rho_needed_unadjusted", ALPHA), ("rho_needed_strictest_holm", ALPHA / len(out))]:
        t_crit = stats.t.ppf(1 - alpha / 2, out["n"] - 2)
        out[col] = t_crit / np.sqrt(out["n"] - 2 + t_crit**2)
    out = out.round(4)

    merged.to_csv(OUT_DIR / "regional_merged.csv", index=False)
    out.to_csv(OUT_DIR / "regional_correlations.csv", index=False)
    return out


def main():
    OUT_DIR.mkdir(exist_ok=True)
    annual = load("employment_annual")

    print("parity scorecard")
    print(parity_scorecard(annual).to_string(index=False))
    print("\nlabor force decomposition")
    print(labor_force_decomposition(annual).to_string(index=False))
    print("\nlfpr gap trend")
    gap, trend = lfpr_gap_trend(annual)
    print(gap.to_string(index=False))
    print(trend.to_string(index=False))
    print(f"max |PSA annual LFPR - mean of survey rounds|: {annual_vs_survey_mean(annual):.3f} pts")
    print("\nseasonality")
    season = seasonality()
    print(season.to_string(index=False))
    print("\nexploratory: deviation in the old quarterly survey months (Jan/Apr/Jul/Oct)")
    print(quarterly_round_bias(season).to_string(index=False))
    print("\nregional correlations")
    print(regional_correlations().to_string(index=False))


if __name__ == "__main__":
    main()
