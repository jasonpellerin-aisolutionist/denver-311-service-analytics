"""Generate the Tableau Public workbook (tableau/denver311_dashboard.twb) from the exports.

Open the result in Tableau Public (Desktop), check each sheet, then File > Save to Tableau
Public As. The file points at tableau/exports/ by absolute path, so it is regenerated per
machine and not committed. `--install-palettes` also writes the project palettes to
~/Documents/My Tableau Repository/Preferences.tps so they appear in every color menu.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from denver311 import EXPORT_DIR, ROOT

OUT = ROOT / "tableau" / "denver311_dashboard.twb"
PREFERENCES = Path.home() / "Documents" / "My Tableau Repository" / "Preferences.tps"
BUILD = "2026.2.3 (20262.26.0912.1023)"

NAVY, TEAL, BLUE, SLATE = "#1e3a5f", "#0f766e", "#2563eb", "#64748b"
STEEL, SEAFOAM, INK, BODY = "#5b8db8", "#5eada5", "#0f172a", "#334155"
CATEGORICAL = [NAVY, TEAL, BLUE, SLATE, STEEL, SEAFOAM]
SEQUENTIAL = "Denver 311 Sequential"
DIVERGING = "Denver 311 Wait Index"

PALETTES = f"""
    <color-palette name='Denver 311 Categorical' type='regular'>
      {"".join(f"<color>{c}</color>" for c in CATEGORICAL)}
    </color-palette>
    <color-palette name='{SEQUENTIAL}' type='ordered-sequential'>
      <color>#f1f5f9</color><color>{NAVY}</color>
    </color-palette>
    <color-palette name='{DIVERGING}' type='ordered-diverging'>
      <color>{TEAL}</color><color>#f8fafc</color><color>{NAVY}</color>
    </color-palette>"""

KPI_METRICS = [
    "Field requests, 2019-2025",
    "Field share of contacts",
    "Like-for-like field requests, 2019 to 2025",
    "App share of field requests, 2025",
    "Type-years with a record gap",
]
TOP_CATEGORIES = [
    "Streets & Traffic",
    "Neighborhood Inspection",
    "Public Safety (non-emergency)",
    "Solid Waste",
    "General Information",
    "Licensing & Permits",
]
LOS_TYPES = [
    "Pothole",
    "Signal Hazard (Traffic)",
    "Transportation Signal Maintenance",
    "Transportation Sign Maintenance",
    "Signal Timing",
]
DIMENSION_NUMBERS = {"year", "nbhd_id", "council_district", "month_of_year", "los_business_days"}
SOURCE_NOTE = (
    "Source: Denver Open Data Catalog, 311 Service Requests 2019-2025 (CC BY 3.0). "
    "Benchmark = each type's own 2019 P90, derived for this analysis, not a city target. "
    "Code: github.com/jasonpellerin-aisolutionist/denver-311-service-analytics"
)


def a(value: object) -> str:
    """Escape a value for a single-quoted XML attribute."""
    s = str(value)
    for old, new in (
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ("'", "&apos;"),
        ('"', "&quot;"),
    ):
        s = s.replace(old, new)
    return s


def t(value: str) -> str:
    """Escape XML text content."""
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def member(value: str) -> str:
    """A string member as Tableau stores it in filters and color maps."""
    return a(f'"{value}"')


def ident(seed: str) -> str:
    """Stable 28-character lowercase id, like the ones Tableau generates."""
    digest = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while len(out) < 28:
        digest, r = divmod(digest, 36)
        out += alphabet[r]
    return out


def simple_id(seed: str) -> str:
    return "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, "denver311/" + seed)).upper() + "}"


@dataclass
class Calc:
    name: str
    formula: str
    datatype: str
    role: str
    kind: str
    fmt: str | None = None


@dataclass
class Datasource:
    caption: str
    filename: str
    spatial: bool = False
    calcs: list[Calc] = field(default_factory=list)
    formats: dict[str, str] = field(default_factory=dict)
    geo_columns: list[tuple[str, str]] = field(default_factory=list)
    styles: str = ""
    aliases: str = ""

    def __post_init__(self) -> None:
        self.name = "federated." + ident(self.caption)
        self.conn = ("ogrdirect." if self.spatial else "textscan.") + ident(self.filename)
        self.columns = (
            self.geo_columns if self.spatial else infer_columns(EXPORT_DIR / self.filename)
        )

    def ref(self, instance: str) -> str:
        return f"[{self.name}].[{instance}]"

    def column_decls(self) -> str:
        out = []
        for col, dtype in self.columns:
            role, kind = role_of(col, dtype)
            fmt = self.formats.get(col)
            fmt_attr = f" default-format='{a(fmt)}'" if fmt else ""
            out.append(
                f"<column datatype='{dtype}'{fmt_attr} name='[{a(col)}]' role='{role}' type='{kind}' />"
            )
        for c in self.calcs:
            fmt_attr = f" default-format='{a(c.fmt)}'" if c.fmt else ""
            out.append(
                f"<column caption='{a(c.name)}' datatype='{c.datatype}'{fmt_attr} "
                f"name='[{a(c.name)}]' role='{c.role}' type='{c.kind}'>"
                f"<calculation class='tableau' formula='{a(c.formula)}' /></column>"
            )
        return "\n        ".join(out)

    def xml(self) -> str:
        directory = a(EXPORT_DIR.resolve())
        if self.spatial:
            layer = a(Path(self.filename).stem)
            relation = f"<relation connection='{self.conn}' name='{layer}' table='[{layer}]' type='table' />"
        else:
            cols = "".join(
                f"<column datatype='{dtype}' name='{a(col)}' ordinal='{i}' />"
                for i, (col, dtype) in enumerate(self.columns)
            )
            relation = (
                f"<relation connection='{self.conn}' name='{a(self.filename)}' "
                f"table='[{a(self.filename.replace('.', '#'))}]' type='table'>"
                f"<columns character-set='UTF-8' header='yes' locale='en_US' separator=','>{cols}</columns>"
                f"</relation>"
            )
        conn_class = "ogrdirect" if self.spatial else "textscan"
        return f"""
    <datasource caption='{a(self.caption)}' inline='true' name='{self.name}' version='18.1'>
      <connection class='federated'>
        <named-connections>
          <named-connection caption='{a(Path(self.filename).stem)}' name='{self.conn}'>
            <connection class='{conn_class}' directory='{directory}' filename='{a(self.filename)}' password='' server='' />
          </named-connection>
        </named-connections>
        {relation}
      </connection>
      <aliases enabled='yes' />
        {self.aliases}
        {self.column_decls()}
      <layout dim-ordering='alphabetic' dim-percentage='0.5' measure-ordering='alphabetic' measure-percentage='0.4' show-structure='true' />
      <style>
        <style-rule element='mark'>{self.styles}
        </style-rule>
      </style>
      <semantic-values>
        <semantic-value key='[Country].[Name]' value='&quot;United States&quot;' />
      </semantic-values>
    </datasource>"""


def infer_columns(path: Path) -> list[tuple[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    header, body = rows[0], rows[1:]
    out = []
    for i, col in enumerate(header):
        values = [r[i] for r in body if i < len(r) and r[i] != ""]
        out.append((col, infer_type(col, values)))
    return out


def infer_type(col: str, values: list[str]) -> str:
    if col == "month":
        return "datetime"
    if values and all(v in ("true", "false") for v in values):
        return "boolean"
    try:
        [int(v) for v in values]
        return "integer"
    except ValueError:
        pass
    try:
        [float(v) for v in values]
        return "real"
    except ValueError:
        return "string"


def role_of(col: str, dtype: str) -> tuple[str, str]:
    if col in DIMENSION_NUMBERS:
        return "dimension", "ordinal"
    if dtype in ("integer", "real"):
        return "measure", "quantitative"
    if dtype == "datetime":
        return "dimension", "ordinal"
    return "dimension", "nominal"


def color_map(field_name: str, pairs: list[tuple[str, str]]) -> str:
    maps = "".join(f"<map to='{c}'><bucket>{member(v)}</bucket></map>" for v, c in pairs)
    return f"\n          <encoding attr='color' field='{a(field_name)}' type='palette'>{maps}</encoding>"


def measure_names_map(pairs: list[tuple[str, str]]) -> str:
    maps = "".join(f"<map to='{c}'><bucket>{member(ref)}</bucket></map>" for ref, c in pairs)
    return f"\n          <encoding attr='color' field='[:Measure Names]' type='palette'>{maps}</encoding>"


def measure_names_aliases(pairs: list[tuple[str, str]]) -> str:
    items = "".join(f"<alias key='{member(ref)}' value='{a(label)}' />" for ref, label in pairs)
    return (
        "<column datatype='string' name='[:Measure Names]' role='dimension' type='nominal'>"
        f"<aliases>{items}</aliases></column>"
    )


# ---- data sources -------------------------------------------------------------------------

kpis = Datasource(
    "KPIs",
    "kpi_summary.csv",
    calcs=[
        Calc(
            "Display value",
            'IF [unit] = "share" THEN STR(INT(ROUND([value] * 100))) + "%" '
            'ELSEIF [unit] = "change" THEN "+" + STR(ROUND([value] * 1000) / 10) + "%" '
            'ELSEIF [value] >= 1000 THEN STR(INT(ROUND([value] / 1000))) + "K" '
            "ELSE STR(INT([value])) END",
            "string",
            "dimension",
            "nominal",
        )
    ],
)

type_year = Datasource(
    "Type Year",
    "type_year.csv",
    calcs=[
        Calc("P50 days", "[p50_hours] / 24", "real", "measure", "quantitative", "n#,##0.0"),
        Calc("P90 days", "[p90_hours] / 24", "real", "measure", "quantitative", "n#,##0.0"),
        Calc(
            "2019 benchmark (P90 days)",
            "[p90_hours_2019] / 24",
            "real",
            "measure",
            "quantitative",
            "n#,##0.0",
        ),
        Calc(
            "Benchmark label",
            'IF [record_gap] THEN "gap" ELSE STR(INT(ROUND([share_within_2019_p90] * 100))) + "%" END',
            "string",
            "dimension",
            "nominal",
        ),
    ],
    formats={
        "share_within_2019_p90": "p0%",
        "share_closed_within_1h": "p0%",
        "share_closed_after_30d": "p0%",
    },
)
P50 = type_year.ref("avg:P50 days:qk")
P90 = type_year.ref("avg:P90 days:qk")
type_year.aliases = measure_names_aliases([(P50, "Median (P50)"), (P90, "90th percentile (P90)")])
type_year.styles = measure_names_map([(P50, TEAL), (P90, NAVY)])

los = Datasource("Published LOS", "published_los.csv", formats={"share_within_los": "p0%"})
los.styles = color_map("[none:request_type:nk]", list(zip(LOS_TYPES, CATEGORICAL, strict=False)))

monthly = Datasource(
    "Monthly",
    "monthly_category.csv",
    calcs=[Calc("Month", "DATE([month])", "date", "dimension", "ordinal")],
)
monthly.styles = color_map(
    "[none:request_category:nk]", list(zip(TOP_CATEGORIES, CATEGORICAL, strict=True))
)

channel_year = Datasource(
    "Channel Year",
    "channel_year.csv",
    calcs=[
        Calc(
            "Channel group",
            'IF [channel] = "Phone" OR [channel] = "App (PocketGov)" THEN [channel] ELSE "Other channels" END',
            "string",
            "dimension",
            "nominal",
        )
    ],
    formats={"share_of_field": "p0%", "share_of_contacts": "p0%"},
)
channel_year.styles = color_map(
    "[none:Channel group:nk]",
    [("Phone", NAVY), ("App (PocketGov)", TEAL), ("Other channels", SLATE)],
)

channel_speed = Datasource(
    "Channel Speed",
    "channel_speed.csv",
    calcs=[
        Calc(
            "App slower by (hours)",
            "[app_minus_phone_hours]",
            "real",
            "measure",
            "quantitative",
            "n#,##0.0",
        )
    ],
    formats={"phone_p50_hours": "n#,##0.0", "app_p50_hours": "n#,##0.0"},
)
PHONE = channel_speed.ref("avg:phone_p50_hours:qk")
APP = channel_speed.ref("avg:app_p50_hours:qk")
channel_speed.aliases = measure_names_aliases(
    [(PHONE, "Phone median hours"), (APP, "App median hours")]
)
channel_speed.styles = measure_names_map([(PHONE, NAVY), (APP, TEAL)])

neighborhoods = Datasource(
    "Neighborhoods",
    "neighborhoods_metrics.geojson",
    spatial=True,
    geo_columns=[
        ("Geometry", "spatial"),
        ("nbhd_id", "integer"),
        ("neighborhood", "string"),
        ("council_district", "integer"),
        ("population", "integer"),
        ("per_capita_income", "integer"),
        ("pct_poverty", "real"),
        ("pct_renters", "real"),
        ("field_requests", "integer"),
        ("field_requests_2025", "integer"),
        ("field_requests_per_1k_per_year", "real"),
        ("top_category", "string"),
        ("share_open_in_file", "real"),
        ("wait_index", "real"),
        ("ranked_requests", "integer"),
        ("p50_days", "real"),
    ],
    formats={"wait_index": "n0.000", "p50_days": "n#,##0.0", "per_capita_income": 'c"$"#,##0'},
)

DATASOURCES = [kpis, type_year, los, monthly, channel_year, channel_speed, neighborhoods]


# ---- worksheets ---------------------------------------------------------------------------

DERIVATION = {
    "none": "None",
    "sum": "Sum",
    "avg": "Avg",
    "tmn": "Month-Trunc",
    "collect": "Collect",
}
TYPE_OF = {"nk": "nominal", "ok": "ordinal", "qk": "quantitative"}


@dataclass
class Sheet:
    name: str
    title: str
    ds: Datasource
    rows: str
    cols: str
    mark: str
    encodings: list[tuple[str, str]] = field(default_factory=list)
    instances: list[str] = field(default_factory=list)
    filters: str = ""
    sorts: str = ""
    style: str = ""
    mapped: bool = False
    filter_cards: list[tuple[str, str]] = field(default_factory=list)
    color_legend: str | None = None

    def instance_xml(self) -> str:
        out = []
        for inst in self.instances:
            prefix, col, tk = inst.split(":")
            out.append(
                f"<column-instance column='[{a(col)}]' derivation='{DERIVATION[prefix]}' "
                f"name='[{a(inst)}]' pivot='key' type='{TYPE_OF[tk]}' />"
            )
        return "\n            ".join(out)

    def xml(self) -> str:
        enc = "".join(f"<{kind} column='{a(ref)}' />" for kind, ref in self.encodings)
        mapsources = "<mapsources><mapsource name='Tableau' /></mapsources>" if self.mapped else ""
        return f"""
    <worksheet name='{a(self.name)}'>
      <layout-options>
        <title>
          <formatted-text>
            <run bold='true' fontcolor='{INK}' fontsize='12'>{t(self.title)}</run>
          </formatted-text>
        </title>
      </layout-options>
      <table>
        <view>
          <datasources>
            <datasource caption='{a(self.ds.caption)}' name='{self.ds.name}' />
          </datasources>
          {mapsources}
          <datasource-dependencies datasource='{self.ds.name}'>
            {self.ds.aliases}
            {self.ds.column_decls()}
            {self.instance_xml()}
          </datasource-dependencies>
          {self.filters}
          {self.sorts}
          <aggregation value='true' />
        </view>
        <style>{self.style}
        </style>
        <panes>
          <pane selection-relaxation-option='selection-relaxation-allow'>
            <view>
              <breakdown value='auto' />
            </view>
            <mark class='{self.mark}' />
            <encodings>{enc}</encodings>
          </pane>
        </panes>
        <rows>{a(self.rows) if self.rows else ""}</rows>
        <cols>{a(self.cols) if self.cols else ""}</cols>
      </table>
      <simple-id uuid='{simple_id("sheet/" + self.name)}' />
    </worksheet>"""

    def window_xml(self) -> str:
        right = "".join(
            f"<card mode='{mode}' param='{a(ref)}' type='filter' />"
            for ref, mode in self.filter_cards
        )
        if self.color_legend:
            right += (
                f"<card pane-specification-id='0' param='{a(self.color_legend)}' type='color' />"
            )
        right_edge = f"<edge name='right'><strip size='200'>{right}</strip></edge>" if right else ""
        return f"""
    <window class='worksheet' name='{a(self.name)}'>
      <cards>
        <edge name='left'>
          <strip size='160'><card type='pages' /><card type='filters' /><card type='marks' /></strip>
        </edge>
        <edge name='top'>
          <strip size='2147483647'><card type='columns' /></strip>
          <strip size='2147483647'><card type='rows' /></strip>
          <strip size='31'><card type='title' /></strip>
        </edge>
        {right_edge}
      </cards>
      <simple-id uuid='{simple_id("window/" + self.name)}' />
    </window>"""


def member_filter(ds: Datasource, level: str, values: list[str], quoted: bool = True) -> str:
    items = "".join(
        f"<groupfilter function='member' level='[{a(level)}]' member='{member(v) if quoted else a(v)}' />"
        for v in values
    )
    marker = "user:ui-domain='database' user:ui-enumeration='inclusive' user:ui-marker='enumerate'"
    body = (
        items
        if len(values) == 1
        else f"<groupfilter function='union' {marker}>{items}</groupfilter>"
    )
    if len(values) == 1:
        body = body.replace(" />", f" {marker} />", 1)
    return f"<filter class='categorical' column='{a(ds.ref(level))}'>{body}</filter>"


def measure_names_filter(ds: Datasource, refs: list[str]) -> str:
    items = "".join(
        f"<groupfilter function='member' level='[:Measure Names]' member='{member(r)}' />"
        for r in refs
    )
    return (
        f"<filter class='categorical' column='{a(ds.ref(':Measure Names'))}'>"
        f"<groupfilter function='union' user:op='manual'>{items}</groupfilter></filter>"
    )


def interpolated(field_ref: str, palette: str, lo: float, hi: float) -> str:
    return (
        f"\n          <style-rule element='mark'><encoding attr='color' field='{a(field_ref)}' "
        f"max='{hi}' min='{lo}' palette='{a(palette)}' type='interpolated' /></style-rule>"
    )


def manual_sort(ds: Datasource, level: str, values: list[str]) -> str:
    buckets = "".join(f"<bucket>{member(v)}</bucket>" for v in values)
    return (
        f"<manual-sort column='{a(ds.ref(level))}' direction='ASC'>"
        f"<dictionary>{buckets}</dictionary></manual-sort>"
    )


MAP_STYLE = """
          <style-rule element='map'>
            <format attr='washout' value='0.5' />
            <format attr='map-style' value='light' />
          </style-rule>"""

sheets = [
    Sheet(
        "KPI tiles",
        "Denver 311 at a glance, 2019-2025",
        kpis,
        rows="",
        cols=kpis.ref("none:metric:nk"),
        mark="Automatic",
        encodings=[("text", kpis.ref("none:Display value:nk"))],
        instances=["none:metric:nk", "none:Display value:nk"],
        filters=member_filter(kpis, "none:metric:nk", KPI_METRICS),
        sorts=manual_sort(kpis, "none:metric:nk", KPI_METRICS),
    ),
    Sheet(
        "Type speed",
        "Days to close by request type: median and 90th percentile",
        type_year,
        rows=type_year.ref("none:request_type:nk"),
        cols=type_year.ref("Multiple Values"),
        mark="Circle",
        encodings=[("color", type_year.ref(":Measure Names"))],
        instances=["none:request_type:nk", "none:year:ok", "avg:P50 days:qk", "avg:P90 days:qk"],
        filters=member_filter(type_year, "none:year:ok", ["2025"], quoted=False)
        + measure_names_filter(type_year, [P50, P90]),
        sorts=f"<computed-sort column='{a(type_year.ref('none:request_type:nk'))}' direction='DESC' using='{a(P90)}' />",
        filter_cards=[(type_year.ref("none:year:ok"), "dropdown")],
        color_legend=type_year.ref(":Measure Names"),
    ),
    Sheet(
        "Benchmark heatmap",
        "Share closed within each type's own 2019 P90 (derived benchmark; gap = incomplete record)",
        type_year,
        rows=type_year.ref("none:request_type:nk"),
        cols=type_year.ref("none:year:ok"),
        mark="Square",
        encodings=[
            ("color", type_year.ref("avg:share_within_2019_p90:qk")),
            ("text", type_year.ref("none:Benchmark label:nk")),
        ],
        instances=[
            "none:request_type:nk",
            "none:year:ok",
            "avg:share_within_2019_p90:qk",
            "none:Benchmark label:nk",
            "avg:requests_total:qk",
        ],
        sorts=f"<computed-sort column='{a(type_year.ref('none:request_type:nk'))}' direction='DESC' using='{a(type_year.ref('avg:requests_total:qk'))}' />",
        style=interpolated(type_year.ref("avg:share_within_2019_p90:qk"), SEQUENTIAL, 0, 1),
    ),
    Sheet(
        "Against DOTI goals",
        "Share closed within DOTI Level of Service goals, business days (denvergov.org)",
        los,
        rows=los.ref("avg:share_within_los:qk"),
        cols=los.ref("none:year:ok"),
        mark="Line",
        encodings=[("color", los.ref("none:request_type:nk"))],
        instances=["none:year:ok", "avg:share_within_los:qk", "none:request_type:nk"],
        color_legend=los.ref("none:request_type:nk"),
    ),
    Sheet(
        "Monthly trend",
        "Field requests per month, top six categories",
        monthly,
        rows=monthly.ref("sum:field_requests:qk"),
        cols=monthly.ref("tmn:Month:qk"),
        mark="Line",
        encodings=[("color", monthly.ref("none:request_category:nk"))],
        instances=["tmn:Month:qk", "sum:field_requests:qk", "none:request_category:nk"],
        filters=member_filter(monthly, "none:request_category:nk", TOP_CATEGORIES),
        color_legend=monthly.ref("none:request_category:nk"),
    ),
    Sheet(
        "Neighborhood wait map",
        "Wait index by neighborhood (0.50 = typical for the same request type and year)",
        neighborhoods,
        rows=neighborhoods.ref("Latitude (generated)"),
        cols=neighborhoods.ref("Longitude (generated)"),
        mark="Multipolygon",
        encodings=[
            ("color", neighborhoods.ref("avg:wait_index:qk")),
            ("lod", neighborhoods.ref("none:neighborhood:nk")),
            ("lod", neighborhoods.ref("avg:p50_days:qk")),
            ("lod", neighborhoods.ref("avg:field_requests_per_1k_per_year:qk")),
            ("lod", neighborhoods.ref("avg:per_capita_income:qk")),
            ("lod", neighborhoods.ref("avg:pct_poverty:qk")),
            ("lod", neighborhoods.ref("sum:ranked_requests:qk")),
            ("geometry", neighborhoods.ref("collect:Geometry:ok")),
        ],
        instances=[
            "avg:wait_index:qk",
            "none:neighborhood:nk",
            "avg:p50_days:qk",
            "avg:field_requests_per_1k_per_year:qk",
            "avg:per_capita_income:qk",
            "avg:pct_poverty:qk",
            "sum:ranked_requests:qk",
            "none:ranked_requests:qk",
            "collect:Geometry:ok",
        ],
        filters=(
            f"<filter class='quantitative' column='{a(neighborhoods.ref('none:ranked_requests:qk'))}' "
            "included-values='in-range'><min>500</min></filter>"
        ),
        style=interpolated(neighborhoods.ref("avg:wait_index:qk"), DIVERGING, 0.45, 0.55)
        + MAP_STYLE,
        mapped=True,
        color_legend=neighborhoods.ref("avg:wait_index:qk"),
    ),
    Sheet(
        "Channel share",
        "Share of field requests by intake channel",
        channel_year,
        rows=channel_year.ref("sum:share_of_field:qk"),
        cols=channel_year.ref("none:year:ok"),
        mark="Line",
        encodings=[("color", channel_year.ref("none:Channel group:nk"))],
        instances=["none:year:ok", "sum:share_of_field:qk", "none:Channel group:nk"],
        color_legend=channel_year.ref("none:Channel group:nk"),
    ),
    Sheet(
        "Phone vs app",
        "Median hours to close: phone vs app, same request type",
        channel_speed,
        rows=channel_speed.ref("none:request_type:nk"),
        cols=channel_speed.ref("Multiple Values"),
        mark="Circle",
        encodings=[("color", channel_speed.ref(":Measure Names"))],
        instances=["none:request_type:nk", "avg:phone_p50_hours:qk", "avg:app_p50_hours:qk"],
        filters=measure_names_filter(channel_speed, [PHONE, APP]),
        sorts=f"<computed-sort column='{a(channel_speed.ref('none:request_type:nk'))}' direction='DESC' using='{a(PHONE)}' />",
        color_legend=channel_speed.ref(":Measure Names"),
    ),
]


# ---- dashboard ----------------------------------------------------------------------------

DASHBOARD = "Denver 311 Service Analytics"


def text_zone(
    zid: int, x: int, y: int, w: int, h: int, text: str, size: int, color: str, bold: bool = False
) -> str:
    weight = " bold='true'" if bold else ""
    return (
        f"<zone h='{h}' id='{zid}' type-v2='text' w='{w}' x='{x}' y='{y}'>"
        f"<formatted-text><run{weight} fontcolor='{color}' fontsize='{size}'>{t(text)}</run></formatted-text>"
        "</zone>"
    )


def sheet_zone(zid: int, name: str, x: int, y: int, w: int, h: int) -> str:
    return f"<zone h='{h}' id='{zid}' name='{a(name)}' w='{w}' x='{x}' y='{y}' />"


def legend_zone(zid: int, sheet: Sheet, x: int, y: int, w: int, h: int) -> str:
    return (
        f"<zone h='{h}' id='{zid}' name='{a(sheet.name)}' pane-specification-id='0' "
        f"param='{a(sheet.color_legend)}' type-v2='color' w='{w}' x='{x}' y='{y}' />"
    )


def dashboard_xml() -> str:
    by = {s.name: s for s in sheets}
    z = [
        text_zone(
            3,
            0,
            0,
            100000,
            4000,
            "Denver 311: Where the Work Comes From and How Fast It Closes (2019-2025)",
            20,
            INK,
            True,
        ),
        text_zone(
            4,
            0,
            4000,
            100000,
            3000,
            "3.0 million contacts. The biggest slowdowns are record-keeping gaps; where records are complete, the stories are specific and fixable.",
            12,
            BODY,
        ),
        sheet_zone(5, "KPI tiles", 0, 7000, 100000, 8000),
        sheet_zone(6, "Benchmark heatmap", 0, 15000, 60000, 29000),
        f"<zone h='4000' id='7' mode='dropdown' name='Type speed' param='{a(type_year.ref('none:year:ok'))}' type-v2='filter' w='20000' x='60000' y='15000' />",
        legend_zone(8, by["Type speed"], 80000, 15000, 20000, 4000),
        sheet_zone(9, "Type speed", 60000, 19000, 40000, 25000),
        sheet_zone(10, "Against DOTI goals", 0, 44000, 38000, 22000),
        legend_zone(11, by["Against DOTI goals"], 38000, 44000, 12000, 22000),
        sheet_zone(12, "Monthly trend", 50000, 44000, 38000, 22000),
        legend_zone(13, by["Monthly trend"], 88000, 44000, 12000, 22000),
        sheet_zone(14, "Neighborhood wait map", 0, 66000, 42000, 29000),
        legend_zone(15, by["Neighborhood wait map"], 42000, 66000, 8000, 29000),
        sheet_zone(16, "Channel share", 50000, 66000, 38000, 14500),
        legend_zone(17, by["Channel share"], 88000, 66000, 12000, 14500),
        sheet_zone(18, "Phone vs app", 50000, 80500, 38000, 14500),
        legend_zone(19, by["Phone vs app"], 88000, 80500, 12000, 14500),
        text_zone(20, 0, 95000, 100000, 5000, SOURCE_NOTE, 9, BODY),
    ]
    zones = "\n          ".join(z)
    return f"""
    <dashboard name='{a(DASHBOARD)}'>
      <style />
      <size maxheight='1400' maxwidth='1200' minheight='1400' minwidth='1200' />
      <datasources />
      <zones>
        <zone h='100000' id='2' type-v2='layout-basic' w='100000' x='0' y='0'>
          {zones}
        </zone>
      </zones>
      <simple-id uuid='{simple_id("dashboard")}' />
    </dashboard>"""


def dashboard_window() -> str:
    viewpoints = "".join(
        f"<viewpoint name='{a(s.name)}'><zoom type='entire-view' /></viewpoint>" for s in sheets
    )
    return f"""
    <window class='dashboard' maximized='true' name='{a(DASHBOARD)}'>
      <viewpoints>{viewpoints}</viewpoints>
      <active id='-1' />
      <device-preview>
        <device is-portrait='true' name='Generic Phone' type='Phone' />
      </device-preview>
      <simple-id uuid='{simple_id("window/dashboard")}' />
    </window>"""


def workbook_xml() -> str:
    return f"""<?xml version='1.0' encoding='utf-8' ?>

<workbook source-build='{BUILD}' source-platform='mac' version='18.1' xmlns:user='http://www.tableausoftware.com/xml/user'>
  <document-format-change-manifest>
    <SheetIdentifierTracking />
    <SortTagCleanup />
    <WindowsPersistSimpleIdentifiers />
  </document-format-change-manifest>
  <preferences>{PALETTES}
  </preferences>
  <datasources>{"".join(ds.xml() for ds in DATASOURCES)}
  </datasources>
  <worksheets>{"".join(s.xml() for s in sheets)}
  </worksheets>
  <dashboards>{dashboard_xml()}
  </dashboards>
  <windows source-height='30'>{"".join(s.window_xml() for s in sheets)}{dashboard_window()}
  </windows>
</workbook>
"""


def install_palettes() -> None:
    PREFERENCES.parent.mkdir(parents=True, exist_ok=True)
    PREFERENCES.write_text(
        f"<?xml version='1.0'?>\n<workbook>\n  <preferences>{PALETTES}\n  </preferences>\n</workbook>\n",
        encoding="utf-8",
    )
    print(f"wrote {PREFERENCES}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-palettes", action="store_true")
    args = parser.parse_args()
    OUT.write_text(workbook_xml(), encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} ({len(sheets)} worksheets, {len(DATASOURCES)} data sources)"
    )
    if args.install_palettes:
        install_palettes()


if __name__ == "__main__":
    main()
