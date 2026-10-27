import re
from io import BytesIO
from pathlib import Path

import markdown
import pandas as pd
import seaborn as sns
from flask import Flask, abort, render_template, request, send_file
from markdown.extensions.toc import slugify
from markupsafe import escape
from matplotlib import rc_context
from matplotlib.figure import Figure
from matplotlib.ticker import FixedLocator, MaxNLocator, ScalarFormatter

DATA_DIR = Path("data")
REPORT = Path("content/mapping-gender-parity-philippines.md")
SIGN_VIEWS = {
    "psa": {
        "factor": 1,
        "xlabel": "Gender wage gap (%)",
        "subtitle": "PSA sign: positive = men earn more, negative = women earn more",
    },
    "female": {
        "factor": -1,
        "xlabel": "Female earnings advantage (%)",
        "subtitle": "Flipped sign: positive = women earn more, negative = men earn more",
    },
}
THEMES = {
    "light": {
        "bg": "#ffffff",
        "fg": "#595758",
        "grid": "#ffc8fb",
        "ref": "#8a8688",
        "female": "#c2407f",
        "male": "#595758",
        "seq": ["#595758", "#c2407f", "#ff92c2"],
    },
    "dark": {
        "bg": "#1f1e1f",
        "fg": "#ffeef2",
        "grid": "#595758",
        "ref": "#a9a3a6",
        "female": "#ff92c2",
        "male": "#d9d2d6",
        "seq": ["#d9d2d6", "#ff92c2", "#ffc8fb"],
    },
}
FIGURE_TABLES = {
    "wage_gap": ["wage_gap_by_region", "national_wage_gap"],
    "wage_gap_female": ["wage_gap_by_region", "national_wage_gap"],
    "labor_participation": ["labor_participation"],
    "labor_force_persons": ["labor_force_persons"],
    "school_enrollment": ["school_enrollment"],
    "literacy": ["literacy_rate", "national_literacy"],
    "scorecard": ["analysis/scorecard"],
    "lf_decomposition": ["analysis/lf_decomposition"],
    "lfpr_gap_trend": ["analysis/lfpr_gap_trend", "analysis/lfpr_gap_annual"],
    "seasonality": ["analysis/seasonality", "analysis/seasonality_round_months"],
    "regional_correlations": ["analysis/regional_correlations", "analysis/regional_merged"],
}
FIGURE_SOURCES = {"wage_gap_female": ("wage_gap", "sign=female&")}
AUTHOR_ALIASES = {
    "PSA": "Philippine Statistics Authority",
    "PIDS": "Philippine Institute for Development Studies",
}

FORMULA_RE = re.compile(r"^\$\$\n(.+?)\n\$\$$", re.M | re.S)
FIGURE_RE = re.compile(
    r"<p><strong>(Figure [^<]+)</strong></p>\s*<p><em>(.+?)</em></p>\s*"
    r'<p><img alt="([^"]*)" src="figures/(\w+)\.png" /></p>\s*<p><em>Note\.</em>(.*?)</p>',
    re.S,
)
CITE_RE = re.compile(r"\(([A-Z][^()]*?), ((?:\d{4}[a-z]?|n\.d\.)(?:, \d{4}[a-z]?)*)\)")
NARRATIVE_RE = re.compile(r"\bPSA \((\d{4}[a-z]?(?:, \d{4}[a-z]?)*)\)")
REFERENCE_RE = re.compile(r"([^,(]+?)[,.] .*?\((\d{4}[a-z]?|n\.d\.)", re.S)

app = Flask(__name__)


def load(name):
    return pd.read_csv(DATA_DIR / f"{name}.csv")


def sign_view(sign):
    if sign not in SIGN_VIEWS:
        abort(400, f"sign must be one of {sorted(SIGN_VIEWS)}")
    return SIGN_VIEWS[sign]


def theme_view(theme):
    if theme not in THEMES:
        abort(400, f"theme must be one of {sorted(THEMES)}")
    return THEMES[theme]


def theme_rc(t):
    return {
        "figure.facecolor": t["bg"],
        "axes.facecolor": t["bg"],
        "savefig.facecolor": t["bg"],
        "axes.edgecolor": t["fg"],
        "axes.labelcolor": t["fg"],
        "axes.titlecolor": t["fg"],
        "xtick.color": t["fg"],
        "ytick.color": t["fg"],
        "text.color": t["fg"],
        "legend.facecolor": t["bg"],
        "legend.edgecolor": t["grid"],
        "legend.labelcolor": t["fg"],
        "font.family": "sans-serif",
    }


def sex_palette(t):
    return {"Female": t["female"], "Male": t["male"]}


def wage_gap_chart(t):
    view = sign_view(request.args.get("sign", "psa"))
    df = load("wage_gap_by_region")
    national = load("national_wage_gap")["national_gap_pct"].iloc[0] * view["factor"]
    plot = df.assign(value=df["gap_pct"] * view["factor"]).sort_values("value")
    plot["favors"] = ["Women earn more" if g < 0 else "Men earn more" if g > 0 else "No gap" for g in plot["gap_pct"]]

    fig = Figure(figsize=(9, 7))
    ax = fig.subplots()
    palette = {"Women earn more": t["female"], "Men earn more": t["male"], "No gap": t["ref"]}
    sns.barplot(data=plot, x="value", y="region", hue="favors", palette=palette, dodge=False, ax=ax)
    ax.axvline(0, color=t["fg"], linewidth=0.8)
    ax.axvline(national, color=t["ref"], linestyle="--", label=f"Philippines ({national:+.1f}%)")
    ax.set(
        xlabel=view["xlabel"],
        ylabel="",
        title=f"Gender wage gap by region, August 2024\n{view['subtitle']}",
    )
    ax.legend()
    return fig


def labor_participation_chart(t):
    df = load("labor_participation")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m")
    long = df.melt(id_vars="date", value_vars=["lfpr_male", "lfpr_female"], var_name="sex", value_name="lfpr")
    long["sex"] = long["sex"].map({"lfpr_male": "Male", "lfpr_female": "Female"})

    fig = Figure(figsize=(10, 5))
    ax = fig.subplots()
    sns.lineplot(data=long, x="date", y="lfpr", hue="sex", style="sex", palette=sex_palette(t), markers=True, markersize=4, ax=ax)
    ax.set(
        xlabel="Survey month (quarterly until 2020, monthly from 2021)",
        ylabel="Labor force participation rate (%)",
        title="Labor force participation rate by sex, April 2005 - July 2026",
    )
    return fig


def labor_force_persons_chart(t):
    df = load("labor_force_persons")
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m")
    df["Male"] = df["male_thousands"] / 1000
    df["Female"] = df["female_thousands"] / 1000
    long = df.melt(id_vars="date", value_vars=["Male", "Female"], var_name="sex", value_name="millions")

    fig = Figure(figsize=(10, 5))
    ax = fig.subplots()
    sns.lineplot(data=long, x="date", y="millions", hue="sex", style="sex", palette=sex_palette(t), markers=True, markersize=4, ax=ax)
    ax.set(
        xlabel="Survey month",
        ylabel="Persons in the labor force (millions)",
        title="Persons in the labor force by sex, April 2005 - July 2026",
    )
    return fig


def school_enrollment_chart(t):
    df = load("school_enrollment")
    levels = df["Level"].unique()

    fig = Figure(figsize=(10, 5))
    ax = fig.subplots()
    sns.lineplot(data=df, x="year_start", y="ratio", hue="Level", style="Level", palette=dict(zip(levels, t["seq"])), markers=True, ax=ax)
    ax.axhline(1.0, color=t["ref"], linestyle="--", label="Parity (1.0)")
    ax.set(
        xlabel="School year (start year)",
        ylabel="Girls per boy enrolled",
        title="Ratio of girls to boys in school, SY 2008-09 to 2023-24\nTertiary not reported after SY 2013-14",
    )
    ax.legend()
    return fig


def literacy_chart(t):
    df = load("literacy_rate").sort_values("func_lit_rate_both", ascending=False)
    national = load("national_literacy")["func_lit_rate_both"].iloc[0]
    long = df.melt(
        id_vars="region",
        value_vars=["func_lit_rate_male", "func_lit_rate_female"],
        var_name="sex",
        value_name="rate",
    )
    long["sex"] = long["sex"].map({"func_lit_rate_male": "Male", "func_lit_rate_female": "Female"})

    fig = Figure(figsize=(9, 8))
    ax = fig.subplots()
    sns.barplot(data=long, x="rate", y="region", hue="sex", palette=sex_palette(t), ax=ax)
    ax.axvline(national, color=t["ref"], linestyle="--", label=f"Philippines, both sexes ({national:.1f}%)")
    ax.set(
        xlabel="Functional literacy rate (%), population 10-64",
        ylabel="",
        title="Functional literacy rate by region and sex, 2024 FLEMMS",
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    return fig


def scorecard_chart(t):
    df = load("analysis/scorecard")
    df["label"] = df["indicator"] + " (" + df["period"] + ")"
    df["higher_is"] = "higher is " + df["higher_is"]

    fig = Figure(figsize=(10, 6))
    ax = fig.subplots()
    palette = {"higher is better": t["seq"][0], "higher is worse": t["seq"][1]}
    sns.scatterplot(data=df, x="f_to_m", y="label", hue="higher_is", style="higher_is", palette=palette, s=90, ax=ax)
    ax.axvline(1.0, color=t["ref"], linestyle="--", label="Parity (1.0)")
    ax.set_xscale("log")
    ax.xaxis.set_major_locator(FixedLocator([0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3]))
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.xaxis.set_minor_locator(FixedLocator([]))
    ax.set_xlim(0.6, 1.3)
    ax.set(
        xlabel="Female / male ratio (log scale)",
        ylabel="",
        title="Gender parity scorecard: female / male ratio, latest available year",
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    return fig


def lf_decomposition_chart(t):
    df = load("analysis/lf_decomposition")
    totals = df[df["component"] == "total change"].set_index("sex")["thousands"]
    parts = df[df["component"] != "total change"].copy()
    parts["millions"] = parts["thousands"] / 1000
    parts["sex"] = parts["sex"].map(lambda s: f"{s}\n(total change {totals[s] / 1000:+.2f} M)")
    components = parts["component"].unique()

    fig = Figure(figsize=(9, 5))
    ax = fig.subplots()
    sns.barplot(data=parts, x="sex", y="millions", hue="component", palette=dict(zip(components, t["seq"])), ax=ax)
    ax.axhline(0, color=t["fg"], linewidth=0.8)
    ax.set(
        xlabel="",
        ylabel="Contribution to labor force change (millions)",
        title="Why did the labor force grow, 2006 to 2025?\nShift-share decomposition: population vs participation",
    )
    return fig


def lfpr_gap_trend_chart(t):
    df = load("analysis/lfpr_gap_annual")
    trend = load("analysis/lfpr_gap_trend")

    fig = Figure(figsize=(10, 5))
    ax = fig.subplots()
    palette = {"pre": t["seq"][0], "excluded": t["ref"], "post": t["seq"][1]}
    sns.scatterplot(data=df, x="year", y="gap_pts", hue="period", style="period", palette=palette, s=60, ax=ax)
    for name, row in zip(["pre", "post"], trend.itertuples()):
        d = df[df["period"] == name]
        ax.plot(
            d["year"],
            d["fitted_gap_pts"],
            color=palette[name],
            linestyle="-" if name == "pre" else "--",
            label=f"{row.period}: {row.slope_pts_per_year:+.2f} pts/yr (95% CI {row.ci_low:+.2f} to {row.ci_high:+.2f})",
        )
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    ax.set(
        xlabel="Year",
        ylabel="Male minus female LFPR (percentage points)",
        title="Gender gap in labor force participation, annual, 2006-2025\n2020 (COVID) excluded from both fits",
    )
    ax.legend()
    return fig


def seasonality_chart(t):
    df = load("analysis/seasonality")
    styles = {"Female": ("o", "-"), "Male": ("s", "--")}

    fig = Figure(figsize=(10, 5))
    ax = fig.subplots()
    for sex, d in df.groupby("sex"):
        color = sex_palette(t)[sex]
        marker, linestyle = styles[sex]
        ax.plot(d["month"], d["mean_deviation_pts"], color=color, marker=marker, linestyle=linestyle, label=f"{sex}, mean 2022-2025")
        ax.fill_between(d["month"], d["min_deviation_pts"], d["max_deviation_pts"], color=color, alpha=0.2, label=f"{sex}, min-max across years")
    for i, month in enumerate([1, 4, 7, 10]):
        ax.axvline(month, color=t["ref"], linestyle=":", label="Old quarterly survey months" if i == 0 else None)
    ax.axhline(0, color=t["fg"], linewidth=0.8)
    ax.set_xticks(range(1, 13), ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    ax.set(
        xlabel="Calendar month",
        ylabel="LFPR minus that year's average (pts)",
        title="Seasonal pattern in monthly LFPR, 2022-2025",
    )
    ax.legend(loc="upper left", bbox_to_anchor=(1, 1))
    return fig


REGIONAL_LABELS = {
    "gap_pct": "Wage gap (%), positive = men earn more",
    "poverty_incidence_pct": "Poverty incidence among families, 2023 (%)",
    "lit_gap_f_minus_m": "Functional literacy, female minus male (pts)",
    "func_lit_rate_female": "Female functional literacy rate (%)",
}


def regional_correlations_chart(t):
    merged = load("analysis/regional_merged")
    merged["short"] = merged["region"].str.split(" - ").str[0].str.removeprefix("Region ")
    results = load("analysis/regional_correlations")

    fig = Figure(figsize=(17, 5.5))
    axes = fig.subplots(1, len(results))
    for ax, row in zip(axes, results.itertuples()):
        d = merged.dropna(subset=[row.x, row.y])
        sns.scatterplot(data=d, x=row.x, y=row.y, color=t["female"], ax=ax)
        for r in d.itertuples():
            ax.annotate(r.short, (getattr(r, row.x), getattr(r, row.y)), fontsize=7, xytext=(3, 3), textcoords="offset points")
        ax.set(
            xlabel=REGIONAL_LABELS[row.x],
            ylabel=REGIONAL_LABELS[row.y],
            title=f"{row.hypothesis}: rho = {row.spearman_rho:.2f}, 95% CI [{row.ci_low:.2f}, {row.ci_high:.2f}]\nHolm p = {row.p_holm:.4f}, n = {row.n}",
        )
    fig.tight_layout()
    return fig


def formula_chart(t):
    tex = FORMULA_RE.search(REPORT.read_text(encoding="utf-8")).group(1).replace(r"\text", r"\mathrm")
    fig = Figure(figsize=(5, 0.9))
    fig.text(0.5, 0.5, f"${tex}$", ha="center", va="center", fontsize=16)
    return fig


CHARTS = {
    "wage_gap": wage_gap_chart,
    "labor_participation": labor_participation_chart,
    "labor_force_persons": labor_force_persons_chart,
    "school_enrollment": school_enrollment_chart,
    "literacy": literacy_chart,
    "scorecard": scorecard_chart,
    "lf_decomposition": lf_decomposition_chart,
    "lfpr_gap_trend": lfpr_gap_trend_chart,
    "seasonality": seasonality_chart,
    "regional_correlations": regional_correlations_chart,
    "formula": formula_chart,
}


def ref_id(key):
    return "ref-" + re.sub(r"\W+", "-", "-".join(key)).strip("-").lower()


def parse_references(html):
    refs = {}

    def anchor(m):
        key = REFERENCE_RE.match(m[1]).groups()
        refs[key] = m[1]
        return f'<p id="{ref_id(key)}">{m[1]}</p>'

    return re.sub(r"<p>(.*?)</p>", anchor, html, flags=re.S), refs


def cite_author(text):
    text = re.sub(r" \[[^\]]+\]", "", text).split(" et al.")[0].split(" &amp; ")[0]
    return AUTHOR_ALIASES.get(text, text)


def citation(refs, author, years, text):
    keys = [(cite_author(author), y) for y in years.split(", ")]
    missing = [k for k in keys if k not in refs]
    if missing:
        raise ValueError(f"citation {text!r} has no reference entry for {missing}")
    title = escape("<br><br>".join(refs[k] for k in keys))
    return f'<a class="cite" href="#{ref_id(keys[0])}" data-bs-toggle="tooltip" data-bs-html="true" data-bs-title="{title}">{text}</a>'


def figure_card(m):
    number, title, alt, stem, note = m.groups()
    chart, extra = FIGURE_SOURCES.get(stem, (stem, ""))
    tables = {name: load(name).to_html(index=False, border=0, classes="table table-sm table-striped") for name in FIGURE_TABLES[stem]}
    return render_template(
        "_figure.html",
        number=number,
        title=title,
        alt=alt,
        stem=stem,
        src=f"/chart/{chart}.svg?{extra}",
        note=note,
        tables=tables,
    )


def render_report():
    source = FORMULA_RE.sub(
        '<p class="formula"><img data-chart="/chart/formula.svg?" src="/chart/formula.svg?theme=light" '
        'alt="gap = (male wage - female wage) / male wage x 100"></p>',
        REPORT.read_text(encoding="utf-8"),
    )
    md = markdown.Markdown(extensions=["tables", "toc"], extension_configs={"toc": {"slugify": lambda value, sep: "s-" + slugify(value, sep)}})
    html = md.convert(source)
    body, marker, refs_html = html.partition('<h2 id="s-references">References</h2>')
    refs_html, refs = parse_references(refs_html)
    body = CITE_RE.sub(lambda m: citation(refs, m[1], m[2], m[0]), body)
    body = NARRATIVE_RE.sub(lambda m: citation(refs, "PSA", m[1], m[0]), body)
    body = body.replace("<table>", '<div class="table-responsive"><table class="table table-sm">').replace("</table>", "</table></div>")
    body = FIGURE_RE.sub(figure_card, body)
    return body + marker + refs_html, md.toc_tokens[0]["children"]


@app.route("/")
def report():
    content, toc = render_report()
    return render_template("report.html", content=content, toc=toc)


@app.route("/chart/<name>.svg")
def chart(name):
    if name not in CHARTS:
        abort(404)
    t = theme_view(request.args.get("theme", "light"))
    buf = BytesIO()
    with rc_context(theme_rc(t)):
        CHARTS[name](t).savefig(buf, format="svg", bbox_inches="tight")
    buf.seek(0)
    return send_file(buf, mimetype="image/svg+xml")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
