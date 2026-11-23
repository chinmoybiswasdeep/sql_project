"""Figure builders. Every builder takes an aggregate DataFrame and returns a styled figure
using the shared template from ``theme``; none of them query the database."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

import theme


def wrap_label(label: str, width: int = 10) -> str:
    """Break a long category label onto several lines (Plotly uses <br>)."""
    words, lines, line = label.split(), [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    lines.append(line)
    return "<br>".join(lines)


def _finish(fig: go.Figure, title: str, x_title: str, y_title: str, height: int) -> go.Figure:
    fig.update_layout(title_text=title, height=height, template=theme.TEMPLATE_NAME)
    fig.update_xaxes(title_text=x_title)
    fig.update_yaxes(title_text=y_title)
    return fig


def hbar(
    df: pd.DataFrame, *, y: str, x: str, title: str, x_title: str, y_title: str = "",
    hover: str, customdata: list[str] | None = None, color: str = theme.PRIMARY,
    text_fmt: str | None = None, sort_desc: bool = True, x_range: list[float] | None = None,
) -> go.Figure:
    """Ranked horizontal bars, one series (no legend; the title names the measure)."""
    d = df.sort_values(x, ascending=not sort_desc) if sort_desc is not None else df
    d = d.iloc[::-1]  # Plotly draws bottom-up; largest at top
    fig = go.Figure(go.Bar(
        x=d[x], y=d[y], orientation="h", marker_color=color,
        customdata=d[customdata].to_numpy() if customdata else None,
        hovertemplate=hover + "<extra></extra>",
        text=[text_fmt.format(v) for v in d[x]] if text_fmt else None,
        textposition="outside", cliponaxis=False,
        textfont=dict(color=theme.INK_SECONDARY, size=11),
    ))
    fig.update_yaxes(showgrid=False, ticksuffix="  ")
    if x_range:
        fig.update_xaxes(range=x_range)
    fig.update_layout(bargap=0.38)
    return _finish(fig, title, x_title, y_title, theme.bar_height(len(d)))


def vbar(
    df: pd.DataFrame, *, x: str, y: str, title: str, x_title: str, y_title: str, hover: str,
    customdata: list[str] | None = None, color: str = theme.PRIMARY, height: int = 360,
    category_order: list | None = None, bargap: float = 0.42,
) -> go.Figure:
    fig = go.Figure(go.Bar(
        x=df[x], y=df[y], marker_color=color,
        customdata=df[customdata].to_numpy() if customdata else None,
        hovertemplate=hover + "<extra></extra>",
    ))
    fig.update_xaxes(showgrid=False)
    if category_order:
        fig.update_xaxes(categoryorder="array", categoryarray=category_order)
    fig.update_layout(bargap=bargap)
    return _finish(fig, title, x_title, y_title, height)


def grouped_vbar(
    df: pd.DataFrame, *, x: str, y: str, series: str, series_colors: dict[str, str],
    series_labels: dict[str, str] | None, title: str, x_title: str, y_title: str,
    category_order: list[str], hover_extra: str = "", customdata: list[str] | None = None,
    height: int = 360,
) -> go.Figure:
    fig = go.Figure()
    for key, color in series_colors.items():
        d = df[df[series] == key]
        if d.empty:
            continue
        label = (series_labels or {}).get(key, key)
        fig.add_trace(go.Bar(
            x=d[x], y=d[y], name=label, marker_color=color,
            customdata=d[customdata].to_numpy() if customdata else None,
            hovertemplate=f"<b>{label}</b> · %{{x}}<br>{y_title}: %{{y:,}}{hover_extra}"
                          "<extra></extra>",
        ))
    fig.update_layout(barmode="group")
    fig.update_xaxes(showgrid=False, categoryorder="array", categoryarray=category_order)
    return _finish(fig, title, x_title, y_title, height)


def rate_ci_dots(
    df: pd.DataFrame, *, label: str, title: str, x_title: str, y_title: str = "",
    reference_pct: float | None = None, reference_label: str = "Cohort rate",
    order: list[str] | None = None, color: str = theme.PRIMARY,
) -> go.Figure:
    """Point estimate with Wilson 95% CI whiskers, one row per group (horizontal).

    Expects columns: ``label``, rate_pct, ci_low_pct, ci_high_pct, numerator, denominator.
    """
    d = df.copy()
    if order:
        d[label] = pd.Categorical(d[label], categories=order, ordered=True)
        d = d.sort_values(label, ascending=False)
    else:
        d = d.sort_values("rate_pct", ascending=True)
    d[label] = d[label].astype(str)
    fig = go.Figure()
    if reference_pct is not None:
        fig.add_vline(
            x=reference_pct, line_width=1, line_color=theme.INK_SECONDARY,
            annotation_text=f"{reference_label} {reference_pct:.1f}%",
            annotation_position="top", annotation_font=dict(size=11, color=theme.INK_SECONDARY),
        )
    fig.add_trace(go.Scatter(
        x=d["rate_pct"], y=d[label], mode="markers",
        marker=dict(size=10, color=color, line=dict(color=theme.SURFACE, width=2)),
        error_x=dict(
            type="data", symmetric=False,
            array=d["ci_high_pct"] - d["rate_pct"], arrayminus=d["rate_pct"] - d["ci_low_pct"],
            color=color, thickness=2, width=5,
        ),
        customdata=d[["numerator", "denominator", "ci_low_pct", "ci_high_pct"]].to_numpy(),
        hovertemplate=(
            "<b>%{y}</b><br>Rate: %{x:.1f}%<br>95% CI: %{customdata[2]:.1f}%"
            " to %{customdata[3]:.1f}%<br>%{customdata[0]:,} of %{customdata[1]:,}"
            "<extra></extra>"
        ),
        showlegend=False,
    ))
    upper = max(10.0, float(d["ci_high_pct"].max()) * 1.08) if not d.empty else 100.0
    fig.update_xaxes(range=[0, min(100.0, upper)], ticksuffix="%")
    fig.update_yaxes(showgrid=False, ticksuffix="  ")
    height = max(240, 120 + 34 * len(d))
    return _finish(fig, title, x_title, y_title, height)


def median_iqr(
    df: pd.DataFrame, *, label: str, title: str, x_title: str, series: str | None = None,
    series_colors: dict[str, str] | None = None, order: list[str] | None = None,
) -> go.Figure:
    """Median dot with an IQR (p25-p75) bar per group; optional colour series with a legend.

    Expects columns: ``label``, p25, p50, p75, admissions.
    """
    fig = go.Figure()
    groups = [(None, theme.PRIMARY)] if series is None else list((series_colors or {}).items())
    cats = order or sorted(df[label].astype(str).unique())
    n_series = len(groups)
    for i, (key, color) in enumerate(groups):
        d = df if key is None else df[df[series] == key]
        if d.empty:
            continue
        d = d.set_index(label).reindex(cats).dropna(subset=["p50"]).reset_index()
        offset = 0.0 if n_series == 1 else (i - (n_series - 1) / 2) * 0.28
        y_pos = [cats.index(c) + offset for c in d[label]]
        name = key or "Median"
        fig.add_trace(go.Scatter(
            x=d["p50"], y=y_pos, mode="markers", name=name,
            marker=dict(size=10, color=color, line=dict(color=theme.SURFACE, width=2)),
            error_x=dict(type="data", symmetric=False, array=d["p75"] - d["p50"],
                         arrayminus=d["p50"] - d["p25"], color=color, thickness=2, width=0),
            customdata=d[[label, "p25", "p75", "admissions"]].to_numpy(),
            hovertemplate=(
                f"<b>%{{customdata[0]}}</b>{' · ' + key if key else ''}<br>"
                "Median: %{x:.1f} days<br>IQR: %{customdata[1]:.1f} to %{customdata[2]:.1f}"
                " days<br>Admissions: %{customdata[3]:,}<extra></extra>"
            ),
            showlegend=series is not None,
        ))
    fig.update_yaxes(
        tickmode="array", tickvals=list(range(len(cats))), ticktext=cats, showgrid=False,
        ticksuffix="  ", range=[len(cats) - 0.4, -0.6],  # first category at the top
    )
    fig.update_xaxes(rangemode="tozero")
    height = max(260, 140 + 48 * len(cats))
    return _finish(fig, title, x_title, "", height)


def heatmap(
    matrix: pd.DataFrame, *, title: str, x_title: str, y_title: str, hover_value: str,
) -> go.Figure:
    """Count heatmap on the sequential blue ramp. NaN cells render empty (e.g. suppressed)."""
    z = matrix.to_numpy(dtype=float)
    zmax = float(pd.Series(z.ravel()).max()) if z.size else 1.0
    text = [["" if pd.isna(v) else f"{int(v)}" for v in row] for row in z]
    x_labels = [wrap_label(str(c)) for c in matrix.columns]
    fig = go.Figure(go.Heatmap(
        z=z, x=x_labels, y=list(matrix.index), customdata=[list(matrix.columns)] * len(z),
        colorscale=theme.SEQUENTIAL,
        zmin=0, zmax=zmax, xgap=2, ygap=2, text=text, texttemplate="%{text}",
        textfont=dict(size=11),
        hovertemplate=f"<b>%{{y}} → %{{customdata}}</b><br>{hover_value}: %{{z:,}}<extra></extra>",
        colorbar=dict(title=dict(text=hover_value, side="right",
                                 font=dict(size=11, color=theme.INK_SECONDARY)),
                      thickness=10, outlinewidth=0, tickfont=dict(color=theme.INK_SECONDARY)),
    ))
    fig.update_xaxes(showgrid=False, showline=False, tickangle=0, side="bottom")
    fig.update_yaxes(showgrid=False, showline=False, autorange="reversed", ticksuffix="  ")
    height = max(360, 150 + 36 * len(matrix.index))
    return _finish(fig, title, x_title, y_title, height)


def dumbbell_log(
    df: pd.DataFrame, *, label: str, low: str, high: str, low_name: str, high_name: str,
    title: str, x_title: str, note: str,
) -> go.Figure:
    """Before/after dot pairs on a log axis, joined by a hairline; ``note`` labels each row
    at the right edge (e.g. the speed-up). Expects one row per ``label``."""
    d = df.sort_values(high, ascending=True)
    fig = go.Figure()
    for _, row in d.iterrows():
        fig.add_trace(go.Scatter(
            x=[row[low], row[high]], y=[row[label]] * 2, mode="lines",
            line=dict(color=theme.AXIS, width=2), hoverinfo="skip", showlegend=False,
        ))
    for col, name, color in ((high, high_name, theme.SERIES[1]), (low, low_name, theme.PRIMARY)):
        fig.add_trace(go.Scatter(
            x=d[col], y=d[label], mode="markers", name=name,
            marker=dict(size=11, color=color, line=dict(color=theme.SURFACE, width=2)),
            hovertemplate=f"<b>%{{y}}</b><br>{name}: %{{x:,.2f}} ms<extra></extra>",
        ))
    fig.add_trace(go.Scatter(
        x=[d[high].max() * 4] * len(d), y=d[label], mode="text", text=d[note],
        textposition="middle right", textfont=dict(color=theme.INK_SECONDARY, size=12),
        hoverinfo="skip", showlegend=False, cliponaxis=False,
    ))
    fig.update_xaxes(type="log", title_text=x_title)
    fig.update_yaxes(showgrid=False, ticksuffix="  ")
    fig.update_layout(margin=dict(r=90))
    height = max(260, 130 + 46 * len(d))
    return _finish(fig, title, x_title, "", height)
