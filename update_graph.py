import math
from typing import Any, TypedDict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import ctx


class XAxis(TypedDict):
    range: list[str]


class YAxis(TypedDict):
    range: list[float]


class PrevLayout(TypedDict):
    xaxis: XAxis
    yaxis: YAxis


def update_price_graph(
    df: pd.DataFrame,
    trace_colourmap: dict[str, str],
    trace_options: dict[str, str],
    log_scale: bool,
    percent_scale: bool,
    auto_scale: bool,
    relayout_data: dict[str, Any],
    prev_layout: PrevLayout | None,
    layout: go.Layout,
):
    layout.update(
        title="Price",
        yaxis_tickformat="5~g",
    )

    start_date = None
    end_date = None
    prev_start_date = None

    if not relayout_data.get("xaxis.autorange"):
        if "xaxis.range[0]" in relayout_data:
            start_date = pd.to_datetime(relayout_data["xaxis.range[0]"])
        elif prev_layout:
            start_date = pd.to_datetime(prev_layout["xaxis"]["range"][0])

        if "xaxis.range[1]" in relayout_data:
            end_date = pd.to_datetime(relayout_data["xaxis.range[1]"])
        elif prev_layout:
            end_date = pd.to_datetime(prev_layout["xaxis"]["range"][1])
        if start_date and end_date:
            layout.update(xaxis_range=[start_date, end_date])

    if prev_layout:
        prev_start_date = pd.to_datetime(prev_layout["xaxis"]["range"][0])

    price_adj = 0
    hoverinfo = None

    if percent_scale:
        layout.update(title="% Change")
        layout.update(yaxis_tickformat="+.2~%")

        prev_zoom_df = df.copy(deep=True)

        for column in df.columns:
            visible_series = df.loc[start_date:, column].dropna()
            if not visible_series.empty:
                baseline_value = visible_series.iloc[0]
                df[column] = df[column].div(baseline_value).sub(1)
            else:
                df[column] = np.nan

        for column in prev_zoom_df.columns:
            visible_series = prev_zoom_df.loc[prev_start_date:, column].dropna()
            if not visible_series.empty:
                baseline_value = visible_series.iloc[0]
                prev_zoom_df[column] = prev_zoom_df[column].div(baseline_value).sub(1)
            else:
                prev_zoom_df[column] = np.nan

        if not log_scale:
            if auto_scale or ctx.triggered_id == "auto-scale-switch":
                pass
            elif (
                "xaxis.range[0]" in relayout_data and "yaxis.range[0]" in relayout_data
            ):
                yaxis_min = float(relayout_data["yaxis.range[0]"])
                yaxis_max = float(relayout_data["yaxis.range[1]"])
                zoom_basis = (
                    prev_zoom_df.loc[start_date:end_date]
                    .apply(lambda col: col.between(yaxis_min, yaxis_max))
                    .sum()
                    .idxmax()
                )
                scaling_factor = (
                    prev_zoom_df.add(1).loc[start_date:, zoom_basis].iloc[0]
                )
                layout.update(
                    yaxis_range=[
                        (yaxis_min + 1) / scaling_factor - 1,
                        (yaxis_max + 1) / scaling_factor - 1,
                    ]
                )
            elif (
                ("xaxis.range[0]" in relayout_data or "xaxis.range[1]" in relayout_data)
                and "yaxis.range[0]" not in relayout_data
                and prev_layout
            ):
                yaxis_min = float(prev_layout["yaxis"]["range"][0])
                yaxis_max = float(prev_layout["yaxis"]["range"][1])
                scaling_factor = prev_zoom_df.add(1).loc[start_date:].iloc[0].iloc[0]
                layout.update(
                    yaxis_range=[
                        (yaxis_min + 1) / scaling_factor - 1,
                        (yaxis_max + 1) / scaling_factor - 1,
                    ]
                )

        else:
            price_adj = 1
            hoverinfo = "text+name+x"
            max_val = df.loc[start_date:end_date].max().max()
            min_val = df.loc[start_date:end_date].min().min()
            if (math.log10(max_val + 1) - math.log10(min_val + 1)) < 2:
                ytickvals = [n / 10 for n in range(0, 20)] + [
                    base * 10**exp + 1
                    for exp in range(math.floor(math.log10(max_val + 1)) + 1)
                    for base in range(1, 10)
                ]
            else:
                ytickvals = [0.1, 0.5, 0.8, 1, 1.2, 1.5, 2] + [
                    base * 10**exp + 1
                    for exp in range(math.floor(math.log10(max_val + 1)) + 1)
                    for base in [1, 2, 5]
                ]
            yticktexts = [f"{tick - 1:+.0%}" for tick in ytickvals]
            layout.update(yaxis_tickvals=ytickvals, yaxis_ticktext=yticktexts)

            if auto_scale or ctx.triggered_id == "auto-scale-switch":
                pass
            elif (
                "xaxis.range[0]" in relayout_data and "yaxis.range[0]" in relayout_data
            ):
                yaxis_min = 10 ** float(relayout_data["yaxis.range[0]"])
                yaxis_max = 10 ** float(relayout_data["yaxis.range[1]"])
                zoom_basis = (
                    prev_zoom_df.add(1)
                    .loc[start_date:end_date]
                    .apply(lambda col: col.between(yaxis_min, yaxis_max))
                    .sum()
                    .idxmax()
                )
                scaling_factor = (
                    prev_zoom_df.add(1).loc[start_date:, zoom_basis].iloc[0]
                )
                layout.update(
                    yaxis_range=[
                        np.log10(yaxis_min / scaling_factor),
                        np.log10(yaxis_max / scaling_factor),
                    ]
                )
            elif (
                ("xaxis.range[0]" in relayout_data or "xaxis.range[1]" in relayout_data)
                and "yaxis.range[0]" not in relayout_data
                and prev_layout
            ):
                yaxis_min = 10 ** float(prev_layout["yaxis"]["range"][0])
                yaxis_max = 10 ** float(prev_layout["yaxis"]["range"][1])
                scaling_factor = prev_zoom_df.add(1).loc[start_date:].iloc[0].iloc[0]
                layout.update(
                    yaxis_range=[
                        np.log10(yaxis_min / scaling_factor),
                        np.log10(yaxis_max / scaling_factor),
                    ]
                )
        if auto_scale or ctx.triggered_id == "auto-scale-switch":
            pass
        elif (
            ("yaxis.range[0]" in relayout_data or "yaxis.range[1]" in relayout_data)
            and "xaxis.range[0]" not in relayout_data
            and prev_layout
        ):
            yaxis_min = float(
                relayout_data.get("yaxis.range[0]", prev_layout["yaxis"]["range"][0])
            )
            yaxis_max = float(
                relayout_data.get("yaxis.range[1]", prev_layout["yaxis"]["range"][1])
            )
            layout.update(yaxis_range=[yaxis_min, yaxis_max])

    if log_scale:
        layout.update(yaxis_type="log")

    if auto_scale or ctx.triggered_id == "auto-scale-switch":
        min_val = df.loc[start_date:end_date].min().min() + price_adj
        max_val = df.loc[start_date:end_date].max().max() + price_adj
        if log_scale:
            min_val = np.log10(min_val)
            max_val = np.log10(max_val)
        yaxis_range = [
            min_val - (max_val - min_val) * 0.055,
            max_val + (max_val - min_val) * 0.055,
        ]
        layout.update(yaxis_range=yaxis_range)

    data = [
        go.Scatter(
            x=df.index,
            y=df[column].add(price_adj),
            name=trace_options[column],
            line=go.scatter.Line(color=trace_colourmap[column]),
            hoverinfo=hoverinfo,
            hovertext=np.array(["%+.2f%%" % x for x in df[column].mul(100).values])
            if log_scale and percent_scale
            else None,
        )
        for column in df.columns
    ]

    return data, layout


def update_drawdown_graph(
    df: pd.DataFrame,
    trace_colourmap: dict[str, str],
    trace_options: dict[str, str],
    layout: go.Layout,
):
    layout.update(
        title="Drawdown",
        yaxis_tickformat=".2%",
    )

    data = [
        go.Scatter(
            x=df.index,
            y=df[column],
            name=trace_options[column],
            line=go.scatter.Line(color=trace_colourmap[column]),
        )
        for column in df.columns
    ]

    return data, layout


def update_rolling_returns_graph(
    df: pd.DataFrame,
    trace_colourmap: dict[str, str],
    trace_options: dict[str, str],
    return_duration: str,
    return_duration_options: dict[str, str],
    return_annualisation: str,
    return_annualisation_options: dict[str, str],
    baseline_trace: str,
    baseline_trace_options: dict[str, str],
    rolling_returns_presentation: str,
    rolling_returns_distribution_chart_type: str,
    layout: go.Layout,
):
    layout.update(yaxis_tickformat=".2%")

    title = (
        f"{return_duration_options[return_duration]} "
        f"{return_annualisation_options[return_annualisation]} Rolling Returns"
    )

    if baseline_trace != "None":
        df = df.sub(df[baseline_trace], axis=0, level=0).dropna(
            subset=df.columns.difference([baseline_trace]), how="all"
        )
        title += f" vs {baseline_trace_options[baseline_trace]}"

    layout.update(
        title=title,
    )

    if rolling_returns_presentation == "timeseries":
        data = [
            go.Scatter(
                x=df.index,
                y=df[column],
                name=trace_options[column],
                line=go.scatter.Line(
                    color=trace_colourmap[column],
                    dash=("dash" if column == baseline_trace else None),
                ),
            )
            for column in df.columns
        ]

    elif rolling_returns_presentation == "dist":
        layout.update(
            xaxis_tickformat="+.2%",
        )

        if rolling_returns_distribution_chart_type == "hist":
            vertical_line = go.layout.Shape(
                type="line",
                x0=0,
                x1=0,
                y0=0,
                y1=1,
                yref="paper",
                line=go.layout.shape.Line(
                    color=trace_colourmap[baseline_trace]
                    if baseline_trace != "None"
                    else "grey",
                    width=1,
                    dash="dash",
                ),
                opacity=0.7,
            )
            layout.update(
                barmode="overlay",
                shapes=[vertical_line],
            )
            data = [
                go.Histogram(
                    x=df[column],
                    name=trace_options[column],
                    marker=go.histogram.Marker(color=trace_colourmap[column]),
                    histnorm="probability",
                    opacity=0.7,
                    showlegend=True,
                )
                for column in df.columns
                if column != baseline_trace
            ]

            if baseline_trace != "None":
                data.insert(
                    0,
                    go.Histogram(
                        x=[None],
                        name=trace_options[baseline_trace],
                        marker=go.histogram.Marker(
                            color=trace_colourmap[baseline_trace]
                        ),
                        histnorm="probability",
                        opacity=0.7,
                        showlegend=True,
                    ),
                )
        elif rolling_returns_distribution_chart_type == "box":
            layout.update(
                hovermode="closest",
                yaxis_autorange="reversed",
            )

            data = [
                go.Box(
                    x=df[column],
                    name=trace_options[column],
                    marker=go.box.Marker(color=trace_colourmap[column]),
                    boxpoints="outliers",
                    showlegend=True,
                )
                for column in df.columns
                if column != baseline_trace
            ]

            if baseline_trace != "None":
                data.insert(
                    0,
                    go.Box(
                        x=[None],
                        name=trace_options[baseline_trace],
                        marker=go.box.Marker(color=trace_colourmap[baseline_trace]),
                        boxpoints="outliers",
                        showlegend=True,
                    ),
                )
        else:
            raise ValueError("Invalid rolling_returns_distribution_chart_type")

    else:
        raise ValueError("Invalid chart_type")
    return data, layout


def update_calendar_returns_graph(
    df: pd.DataFrame,
    trace_colourmap: dict[str, str],
    trace_options: dict[str, str],
    return_interval: str,
    return_interval_options: dict[str, str],
    baseline_trace: str,
    baseline_trace_options: dict[str, str],
    layout: go.Layout,
):
    layout.update(
        xaxis_ticklabelmode="period",
        yaxis_tickformat=".2%",
        barmode="group",
    )

    title = f"{return_interval_options[return_interval]} Returns"

    if baseline_trace != "None":
        df = (
            df.sub(df[baseline_trace], axis=0, level=0)
            .dropna(subset=df.columns.difference([baseline_trace]), how="all")
            .drop(columns=baseline_trace)
        )
        title += f" vs {baseline_trace_options[baseline_trace]}"

    layout.update(title=title)

    if return_interval == "1mo":
        index_offset = pd.offsets.BMonthEnd(0)
        xperiod = "M1"
        layout.update(xaxis_tickformat="%b %Y")
    elif return_interval == "3mo":
        index_offset = pd.offsets.BQuarterEnd(0)
        xperiod = "M3"
        layout.update(xaxis_tickformat="Q%q %Y")
    elif return_interval == "1y":
        index_offset = pd.offsets.BYearEnd(0)
        xperiod = "M12"
        layout.update(xaxis_tickformat="%Y")
    else:
        raise ValueError("Invalid return_interval")

    hovertext = df.index.to_series().apply(
        lambda x: x.strftime("As of %d %b %Y") if x != x + index_offset else ""
    )
    data = [
        go.Bar(
            x=df.index + index_offset,
            y=df[column],
            xperiod=xperiod,
            xperiodalignment="middle",
            name=trace_options[column],
            hovertext=hovertext,
            marker=go.bar.Marker(color=trace_colourmap[column]),
        )
        for column in df.columns
        if column != baseline_trace
    ]

    return data, layout


def update_graph(
    df: pd.DataFrame,
    trace_colourmap: dict[str, str],
    trace_options: dict[str, str],
    y_var: str,
    log_scale: bool,
    percent_scale: bool,
    auto_scale: bool,
    return_duration: str,
    return_duration_options: dict[str, str],
    return_interval: str,
    return_interval_options: dict[str, str],
    return_annualisation: str,
    return_annualisation_options: dict[str, str],
    baseline_trace: str,
    baseline_trace_options: dict[str, str],
    rolling_returns_presentation: str,
    rolling_returns_distribution_chart_type: str,
    relayout_data: dict[str, Any] | None,
    uirevision: str,
    prev_layout: PrevLayout | None,
):
    layout = go.Layout(
        autosize=True,
        hovermode="x",
        showlegend=True,
        legend=go.layout.Legend(x=0, valign="top", bgcolor="rgba(255,255,255,0.5)"),
        uirevision=y_var,
        yaxis_side="right",
        yaxis_automargin=True,
        yaxis_uirevision=uirevision,
        margin=go.layout.Margin(t=90, b=30, l=10, r=90, autoexpand=True),
    )

    if relayout_data is None or ctx.triggered_id not in ["graph", "portfolio-graph"]:
        relayout_data = {"autosize": True}

    if y_var == "price":
        data, layout = update_price_graph(
            df,
            trace_colourmap,
            trace_options,
            log_scale,
            percent_scale,
            auto_scale,
            relayout_data,
            prev_layout,
            layout,
        )

        return data, layout

    if y_var == "drawdown":
        data, layout = update_drawdown_graph(df, trace_colourmap, trace_options, layout)
        return data, layout

    if y_var == "rolling_returns":
        data, layout = update_rolling_returns_graph(
            df,
            trace_colourmap,
            trace_options,
            return_duration,
            return_duration_options,
            return_annualisation,
            return_annualisation_options,
            baseline_trace,
            baseline_trace_options,
            rolling_returns_presentation,
            rolling_returns_distribution_chart_type,
            layout,
        )
        return data, layout

    if y_var == "calendar_returns":
        data, layout = update_calendar_returns_graph(
            df,
            trace_colourmap,
            trace_options,
            return_interval,
            return_interval_options,
            baseline_trace,
            baseline_trace_options,
            layout,
        )
        return data, layout
    raise ValueError("Invalid y_var")


__all__ = ["PrevLayout", "update_graph"]
