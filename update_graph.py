import math
from functools import cached_property
from typing import Annotated, Generic, Literal, NotRequired, TypedDict, TypeVar

import numpy as np
import plotly.graph_objects as go
import polars as pl
from dash import ctx
from pydantic import BaseModel, ConfigDict, Field, Json, TypeAdapter, computed_field

from funcs.loaders_pl import add_bmonth_end
from models import (
    DistributionChartType,
    Interval,
    ReturnAnnualisation,
    ReturnDuration,
    ReturnInterval,
    RollingReturnsPresentation,
    YVar,
)
from schemas import Holding


class XAxis(TypedDict):
    range: list[str]


class YAxis(TypedDict):
    range: list[float]


class PrevLayout(TypedDict):
    xaxis: XAxis
    yaxis: YAxis


RelayoutData = TypedDict(
    "RelayoutData",
    {
        "autosize": NotRequired[bool],
        "xaxis.range[0]": NotRequired[str],
        "xaxis.range[1]": NotRequired[str],
        "yaxis.range[0]": NotRequired[float],
        "yaxis.range[1]": NotRequired[float],
        "xaxis.autorange": NotRequired[bool],
        "yaxis.autorange": NotRequired[bool],
    },
)


def filter_start_date(start_date: str | None):
    return (
        (pl.col("date") >= pl.lit(start_date).str.to_datetime())
        if start_date is not None
        else pl.lit(True)
    )


def filter_end_date(end_date: str | None):
    return (
        (pl.col("date") <= pl.lit(end_date).str.to_datetime())
        if end_date is not None
        else pl.lit(True)
    )


def _get_scaling_factor(
    prev_zoom_df: pl.DataFrame,
    start_date: str | None,
    end_date: str | None,
    yaxis_min: float,
    yaxis_max: float,
) -> float:
    start_date_filter = filter_start_date(start_date)
    end_date_filter = filter_end_date(end_date)

    masked_df = (
        prev_zoom_df.filter(start_date_filter & end_date_filter)
        .drop("date")
        .with_columns(
            pl.when(pl.all().ge(yaxis_min) & pl.all().le(yaxis_max))
            .then(pl.all())
            .otherwise(pl.lit(None))
        )
    )
    basis_scores = (masked_df.max() - masked_df.min()) * masked_df.count()

    if basis_scores.select(pl.all_horizontal(pl.all().is_null())).item():
        masked_df = prev_zoom_df.filter(start_date_filter & end_date_filter).drop(
            "date"
        )
        basis_scores = (masked_df.max() - masked_df.min()) * masked_df.count()
    if basis_scores.select(pl.all_horizontal(pl.all().is_null())).item():
        masked_df = prev_zoom_df.drop("date")
        basis_scores = (masked_df.max() - masked_df.min()) * masked_df.count()
    if basis_scores.select(pl.all_horizontal(pl.all().is_null())).item():
        zoom_basis = prev_zoom_df.drop("date").columns[0]
    else:
        zoom_basis = (
            basis_scores.transpose(include_header=True)
            .filter(pl.col("column_0").eq(pl.col("column_0").max()))["column"]
            .head(1)
            .item()
        )
    scaling_factor = (
        prev_zoom_df.filter(start_date_filter)
        .select(pl.col(zoom_basis).first(ignore_nulls=True))
        .item()
    )
    return scaling_factor


def update_price_graph(
    df: pl.DataFrame,
    trace_colourmap: dict[str, str],
    trace_options: dict[str, str],
    log_scale: bool,
    percent_scale: bool,
    auto_scale: bool,
    relayout_data: RelayoutData,
    prev_layout: PrevLayout | None,
    layout: go.Layout,
):
    layout.update(
        title="Price",
        yaxis_tickformat="5~g",
    )

    if log_scale:
        layout.update(yaxis_type="log")

    start_date = None
    end_date = None

    if (
        prev_layout
        and "xaxis.autorange" not in relayout_data
        and ctx.triggered_id not in ["y-var-selection"]
    ):
        start_date = relayout_data.get(
            "xaxis.range[0]", prev_layout["xaxis"]["range"][0]
        )
        end_date = relayout_data.get("xaxis.range[1]", prev_layout["xaxis"]["range"][1])

        layout.update(xaxis_range=[start_date, end_date])

    prev_zoom_df = df

    if percent_scale:
        layout.update(title="% Change")
        layout.update(yaxis_tickformat="+.2~%")

        df = df.with_columns(
            pl.col(col)
            .truediv(
                pl.col(col)
                .filter(filter_start_date(start_date))
                .first(ignore_nulls=True)
            )
            .sub(1)
            for col in df.drop("date").columns
        )

        if log_scale:
            df = df.with_columns(pl.all().exclude("date").add(1))
            max_val = (
                df.filter(filter_start_date(start_date) & filter_end_date(end_date))
                .drop("date")
                .max()
                .max_horizontal()
                .item()
            )
            if max_val < 3:
                ytickvals = [n / 10 for n in range(0, 20)] + [2, 2.2, 2.5, 3]
            else:
                ytickvals = [0.1, 0.5, 0.8, 1, 1.2, 1.5, 2] + [
                    base * 10**exp + 1
                    for exp in range(math.ceil(math.log10(max_val)) + 1)
                    for base in [1, 2, 5]
                ]
            yticktexts = [f"{tick - 1:+.0%}" for tick in ytickvals]
            layout.update(yaxis_tickvals=ytickvals, yaxis_ticktext=yticktexts)

    data = [
        go.Scatter(
            x=df["date"],
            y=df[column],
            name=trace_options[column],
            line=go.scatter.Line(color=trace_colourmap[column]),
            customdata=(df[column] - 1).round(4)
            if log_scale and percent_scale
            else None,
            hovertemplate="%{customdata:+.2%}" if log_scale and percent_scale else None,
        )
        for column in df.drop("date").columns
    ]

    if (
        auto_scale
        or not prev_layout
        or "yaxis.autorange" in relayout_data
        or ctx.triggered_id
        not in [
            "selected-securities",
            "portfolios",
            "graph",
            "portfolio-graph",
        ]
    ):
        filtered = df.filter(
            filter_start_date(start_date) & filter_end_date(end_date)
        ).drop("date")

        min_val = filtered.min().min_horizontal().item()
        max_val = filtered.max().max_horizontal().item()
        if log_scale:
            min_val = np.log10(min_val)
            max_val = np.log10(max_val)
        yaxis_range = [
            min_val - (max_val - min_val) * 0.055,
            max_val + (max_val - min_val) * 0.055,
        ]
        layout.update(yaxis_range=yaxis_range)

        return data, layout

    yaxis_min = relayout_data.get("yaxis.range[0]", prev_layout["yaxis"]["range"][0])
    yaxis_max = relayout_data.get("yaxis.range[1]", prev_layout["yaxis"]["range"][1])

    if not percent_scale:
        layout.update(yaxis_range=[yaxis_min, yaxis_max])
        return data, layout

    prev_start_date = pl.lit(prev_layout["xaxis"]["range"][0]).str.to_datetime()

    prev_zoom_df = prev_zoom_df.with_columns(
        pl.all()
        .exclude("date")
        .truediv(
            pl.all()
            .exclude("date")
            .filter(pl.col("date") >= prev_start_date)
            .first(ignore_nulls=True)
        )
        .sub(1)
    )

    if log_scale:
        prev_zoom_df = prev_zoom_df.with_columns(
            pl.all().exclude("date").add(1).log10()
        )

    scaling_factor = _get_scaling_factor(
        prev_zoom_df, start_date, end_date, yaxis_min, yaxis_max
    )

    if not log_scale:
        yaxis_range = [
            (yaxis_min + 1) / (scaling_factor + 1) - 1,
            (yaxis_max + 1) / (scaling_factor + 1) - 1,
        ]
    else:
        yaxis_range = [
            yaxis_min - scaling_factor,
            yaxis_max - scaling_factor,
        ]
    layout.update(yaxis_range=yaxis_range)

    return data, layout


def update_drawdown_graph(
    df: pl.DataFrame,
    trace_colourmap: dict[str, str],
    trace_options: dict[str, str],
    layout: go.Layout,
):
    df = df.with_columns(
        pl.all().exclude("date").truediv(pl.all().exclude("date").cum_max()).sub(1)
    )

    layout.update(
        title="Drawdown",
        yaxis_tickformat=".2%",
    )

    data = [
        go.Scatter(
            x=df["date"],
            y=df[column],
            name=trace_options[column],
            line=go.scatter.Line(color=trace_colourmap[column]),
        )
        for column in df.drop("date").columns
    ]

    return data, layout


def update_rolling_returns_graph(
    df: pl.DataFrame,
    trace_colourmap: dict[str, str],
    trace_options: dict[str, str],
    interval: Interval,
    return_duration: ReturnDuration,
    return_annualisation: ReturnAnnualisation,
    baseline_trace: str,
    rolling_returns_presentation: RollingReturnsPresentation,
    rolling_returns_distribution_chart_type: DistributionChartType,
    layout: go.Layout,
):
    return_durations = {
        "1mo": 1,
        "3mo": 3,
        "6mo": 6,
        "1y": 12,
        "2y": 24,
        "3y": 36,
        "5y": 60,
        "10y": 120,
        "15y": 180,
        "20y": 240,
        "25y": 300,
        "30y": 360,
    }
    if interval == Interval.MONTHLY:
        df = df.with_columns(
            pl.all().exclude("date").pct_change(return_durations[return_duration])
        )
    elif interval == Interval.DAILY:
        series_names = df.drop("date").columns
        df = (
            df.with_columns(
                lookup_date=pl.col("date")
                .dt.offset_by(f"-{return_durations[return_duration]}mo")
                .dt.add_business_days(0, roll="backward")
            )
            .join(
                df,
                left_on="lookup_date",
                right_on="date",
                how="left",
                maintain_order="left",
            )
            .select(
                "date",
                *(pl.col(col) / pl.col(f"{col}_right") - 1 for col in series_names),
            )
        )
    else:
        raise ValueError("Invalid interval")
    if return_annualisation == ReturnAnnualisation.ANNUALISED:
        df = df.with_columns(
            pl.all()
            .exclude("date")
            .add(1)
            .pow(12 / return_durations[return_duration])
            .sub(1)
        )
    df = df.filter(pl.any_horizontal(pl.all().exclude("date").is_not_null()))

    layout.update(yaxis_tickformat=".2%")

    title = f"{return_duration.label} {return_annualisation.label} Rolling Returns"

    if baseline_trace != "None":
        df = df.with_columns(pl.all().exclude("date").sub(baseline_trace)).filter(
            pl.any_horizontal(pl.all().exclude("date", baseline_trace).is_not_null())
        )
        title += f" vs {trace_options[baseline_trace]}"

    layout.update(
        title=title,
    )

    if rolling_returns_presentation == RollingReturnsPresentation.TIMESERIES:
        data = [
            go.Scatter(
                x=df["date"],
                y=df[column],
                name=trace_options[column],
                line=go.scatter.Line(
                    color=trace_colourmap[column],
                    dash=("dash" if column == baseline_trace else None),
                ),
            )
            for column in df.drop("date").columns
        ]

    elif rolling_returns_presentation == RollingReturnsPresentation.DISTRIBUTION:
        layout.update(
            xaxis_tickformat="+.2%",
        )

        if rolling_returns_distribution_chart_type == DistributionChartType.HISTOGRAM:
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
                for column in df.drop("date").columns
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
        elif rolling_returns_distribution_chart_type == DistributionChartType.BOX_PLOT:
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
                for column in df.drop("date").columns
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
    df: pl.DataFrame,
    trace_colourmap: dict[str, str],
    trace_options: dict[str, str],
    return_interval: ReturnInterval,
    baseline_trace: str,
    layout: go.Layout,
):
    data_df = (
        df.sort("date")
        .group_by_dynamic("date", every=return_interval, label="right")
        .agg(
            pl.all().exclude("date").last(ignore_nulls=True),
        )
        .with_columns(
            pl.col("date").pipe(add_bmonth_end, -1),
            pl.all().exclude("date").pct_change(),
        )
        .filter(pl.any_horizontal(pl.all().exclude("date").is_not_null()))
    )
    hovertext_df = (
        df.sort("date")
        .group_by_dynamic("date", every=return_interval, label="right")
        .agg(
            pl.col("date").filter(pl.col(c).is_not_null()).last().alias(c)
            for c in df.columns
            if c != "date"
        )
        .with_columns(pl.col("date").pipe(add_bmonth_end, -1))
        .with_columns(
            pl.when(pl.all().exclude("date").ne(pl.col("date")))
            .then(
                (
                    pl.lit("As of ") + pl.all().exclude("date").dt.strftime("%d %b %Y")
                ).name.keep()
            )
            .otherwise(pl.lit(None))
        )
    )

    layout.update(
        xaxis_ticklabelmode="period",
        yaxis_tickformat=".2%",
        barmode="group",
    )

    title = f"{return_interval.label} Returns"

    if baseline_trace != "None":
        data_df = (
            data_df.with_columns(pl.all().exclude("date").sub(baseline_trace))
            .drop(baseline_trace)
            .filter(pl.any_horizontal(pl.all().exclude("date").is_not_null()))
        )
        hovertext_df = hovertext_df.join(data_df, on="date", how="semi")
        title += f" vs {trace_options[baseline_trace]}"

    layout.update(title=title)

    if return_interval == ReturnInterval.MONTHLY:
        xperiod = "M1"
        layout.update(xaxis_tickformat="%b %Y")
    elif return_interval == ReturnInterval.QUARTERLY:
        xperiod = "M3"
        layout.update(xaxis_tickformat="Q%q %Y")
    elif return_interval == ReturnInterval.ANNUAL:
        xperiod = "M12"
        layout.update(xaxis_tickformat="%Y")
    else:
        raise ValueError("Invalid return_interval")

    data = [
        go.Bar(
            x=data_df["date"],
            y=data_df[column],
            xperiod=xperiod,
            xperiodalignment="middle",
            name=trace_options[column],
            hovertext=hovertext_df[column],
            marker=go.bar.Marker(color=trace_colourmap[column]),
        )
        for column in data_df.drop("date").columns
        if column != baseline_trace
    ]

    return data, layout


GraphTypeT = TypeVar("GraphTypeT", bound=YVar)


class BaseGraphParam(BaseModel, Generic[GraphTypeT]):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    df: pl.DataFrame
    trace_colourmap: dict[str, str]
    uirevision: str

    y_var: GraphTypeT

    @cached_property
    def trace_options(self) -> dict[str, str]:
        holdings = TypeAdapter(list[Json[Holding]]).validate_python(
            self.df.drop("date").columns
        )
        return {
            holding.model_dump_json(): holding.label.replace("\n", "<br>")
            for holding in holdings
        }

    @computed_field
    @property
    def layout(self) -> go.Layout:
        return go.Layout(
            autosize=True,
            hovermode="x",
            showlegend=True,
            legend=go.layout.Legend(x=0, valign="top", bgcolor="rgba(255,255,255,0.5)"),
            uirevision=self.y_var,
            yaxis_side="right",
            yaxis_automargin=True,
            yaxis_uirevision=self.uirevision,
            margin=go.layout.Margin(t=90, b=30, l=10, r=90, autoexpand=True),
        )


class PriceGraphParams(BaseGraphParam[Literal[YVar.PRICE]]):
    log_scale: bool
    percent_scale: bool
    auto_scale: bool
    relayout_data: RelayoutData
    prev_layout: PrevLayout | None

    def update_graph(self) -> tuple[list[go.Scatter], go.Layout]:
        return update_price_graph(
            self.df,
            self.trace_colourmap,
            self.trace_options,
            self.log_scale,
            self.percent_scale,
            self.auto_scale,
            self.relayout_data,
            self.prev_layout,
            self.layout,
        )


class DrawdownGraphParams(BaseGraphParam[Literal[YVar.DRAWDOWN]]):
    def update_graph(self) -> tuple[list[go.Scatter], go.Layout]:
        return update_drawdown_graph(
            self.df, self.trace_colourmap, self.trace_options, self.layout
        )


class RollingReturnsGraphParams(BaseGraphParam[Literal[YVar.ROLLING_RETURNS]]):
    interval: Interval
    return_duration: ReturnDuration
    return_annualisation: ReturnAnnualisation
    baseline_trace: str
    rolling_returns_presentation: RollingReturnsPresentation
    rolling_returns_distribution_chart_type: DistributionChartType

    def update_graph(
        self,
    ) -> tuple[list[go.Scatter] | list[go.Histogram] | list[go.Box], go.Layout]:
        return update_rolling_returns_graph(
            self.df,
            self.trace_colourmap,
            self.trace_options,
            self.interval,
            self.return_duration,
            self.return_annualisation,
            self.baseline_trace,
            self.rolling_returns_presentation,
            self.rolling_returns_distribution_chart_type,
            self.layout,
        )


class CalendarReturnsGraphParams(BaseGraphParam[Literal[YVar.CALENDAR_RETURNS]]):
    return_interval: ReturnInterval
    baseline_trace: str

    def update_graph(
        self,
    ) -> tuple[list[go.Bar], go.Layout]:
        return update_calendar_returns_graph(
            self.df,
            self.trace_colourmap,
            self.trace_options,
            self.return_interval,
            self.baseline_trace,
            self.layout,
        )


type GraphParams = Annotated[
    PriceGraphParams
    | DrawdownGraphParams
    | RollingReturnsGraphParams
    | CalendarReturnsGraphParams,
    Field(discriminator="y_var"),
]
