from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from pathlib import Path

PROJECT_NAME = "RetailRecommendationAnalyticsReviewed"
PROJECT_ROOT = Path(__file__).resolve().parents[1] / "dashboard" / "powerbi_review"
REPORT_ROOT = PROJECT_ROOT / f"{PROJECT_NAME}.Report"
MODEL_ROOT = PROJECT_ROOT / f"{PROJECT_NAME}.SemanticModel"
PAGES_ROOT = REPORT_ROOT / "definition" / "pages"

SCHEMA_VISUAL = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "visualContainer/2.9.0/schema.json"
)
SCHEMA_PAGE = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "page/2.1.0/schema.json"
)
SCHEMA_PAGES = (
    "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
    "pagesMetadata/1.0.0/schema.json"
)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, payload: dict) -> None:
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def uid(seed: str) -> str:
    return hashlib.md5(seed.encode(), usedforsecurity=False).hexdigest()[:20]


def literal(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def solid(color: str) -> dict:
    return {"solid": {"color": {"expr": {"Literal": {"Value": f"'{color}'"}}}}}


def measure_field(table: str, measure: str) -> dict:
    return {
        "field": {
            "Measure": {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": measure,
            }
        },
        "queryRef": f"{table}.{measure}",
        "nativeQueryRef": measure,
    }


def column_field(table: str, column: str) -> dict:
    return {
        "field": {
            "Column": {
                "Expression": {"SourceRef": {"Entity": table}},
                "Property": column,
            }
        },
        "queryRef": f"{table}.{column}",
        "nativeQueryRef": column,
    }


def card_objects() -> dict:
    return {
        "labels": [{"properties": {"fontSize": literal("28D")}}],
        "categoryLabels": [{"properties": {"show": literal("false")}}],
    }


def chart_objects(labels: bool = False) -> dict:
    objects = {
        "categoryAxis": [
            {
                "properties": {
                    "fontSize": literal("9L"),
                    "showAxisTitle": literal("false"),
                }
            }
        ],
        "valueAxis": [
            {
                "properties": {
                    "fontSize": literal("9L"),
                    "showAxisTitle": literal("false"),
                    "gridlineStyle": literal("'dashed'"),
                    "gridlineColor": solid("#E2E8F0"),
                }
            }
        ],
    }
    if labels:
        objects["labels"] = [
            {
                "properties": {
                    "show": literal("true"),
                    "labelPosition": literal("'OutsideEnd'"),
                    "fontSize": literal("9L"),
                }
            }
        ]
    return objects


def line_objects() -> dict:
    result = chart_objects()
    result["lineStyles"] = [{"properties": {"strokeWidth": literal("3L")}}]
    return result


def table_objects() -> dict:
    return {
        "columnHeaders": [
            {
                "properties": {
                    "bold": literal("true"),
                    "fontSize": literal("10L"),
                    "fontColor": solid("#FFFFFF"),
                    "backColor": solid("#2563EB"),
                }
            }
        ],
        "values": [
            {
                "properties": {
                    "fontSize": literal("10L"),
                    "backColor": solid("#FFFFFF"),
                    "backColorAlternate": solid("#F8FAFC"),
                }
            }
        ],
        "grid": [
            {
                "properties": {
                    "gridHorizontal": literal("true"),
                    "gridHorizontalColor": solid("#E2E8F0"),
                    "gridVertical": literal("false"),
                    "rowPadding": literal("4L"),
                }
            }
        ],
    }


def visual(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    visual_type: str,
    query_state: dict | None = None,
    objects: dict | None = None,
    container_objects: dict | None = None,
    z: int = 1000,
) -> dict:
    payload = {
        "$schema": SCHEMA_VISUAL,
        "name": uid(name),
        "position": {
            "x": x,
            "y": y,
            "z": z,
            "height": height,
            "width": width,
            "tabOrder": 0,
        },
        "visual": {"visualType": visual_type, "drillFilterOtherVisuals": True},
    }
    if query_state:
        payload["visual"]["query"] = {"queryState": query_state}
    if objects:
        payload["visual"]["objects"] = objects
    if container_objects:
        payload["visual"]["visualContainerObjects"] = container_objects
    return payload


def title(name: str, text: str) -> dict:
    return visual(
        name,
        0,
        0,
        1280,
        52,
        "textbox",
        objects={
            "general": [
                {
                    "properties": {
                        "paragraphs": [
                            {
                                "textRuns": [
                                    {
                                        "value": text,
                                        "textStyle": {
                                            "fontFamily": "Segoe UI Semibold",
                                            "fontSize": "20px",
                                            "color": "#FFFFFF",
                                        },
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        },
        container_objects={
            "background": [
                {
                    "properties": {
                        "show": literal("true"),
                        "color": solid("#0F172A"),
                        "transparency": literal("0D"),
                    }
                }
            ],
            "visualHeader": [{"properties": {"show": literal("false")}}],
        },
        z=9000,
    )


def insight(name: str, text: str, x: int, y: int, width: int, height: int) -> dict:
    return visual(
        name,
        x,
        y,
        width,
        height,
        "textbox",
        objects={
            "general": [
                {
                    "properties": {
                        "paragraphs": [
                            {
                                "textRuns": [
                                    {
                                        "value": text,
                                        "textStyle": {
                                            "fontFamily": "Segoe UI",
                                            "fontSize": "12px",
                                            "color": "#0F172A",
                                        },
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        },
        container_objects={
            "background": [
                {
                    "properties": {
                        "show": literal("true"),
                        "color": solid("#EFF6FF"),
                        "transparency": literal("0D"),
                    }
                }
            ]
        },
        z=1500,
    )


def card(name: str, x: int, y: int, width: int, table: str, measure: str) -> dict:
    return visual(
        name,
        x,
        y,
        width,
        108,
        "card",
        {"Values": {"projections": [measure_field(table, measure + " Display")]}},
        card_objects(),
        {
            "title": [
                {
                    "properties": {
                        "show": literal("true"),
                        "text": literal("'" + measure.replace("'", "''") + "'"),
                        "fontSize": literal("11D"),
                    }
                }
            ]
        },
    )


def slicer(name: str, x: int, y: int, width: int, table: str, column: str) -> dict:
    objects = None
    if column == "Cohort":
        objects = {
            "selection": [
                {
                    "properties": {
                        "singleSelect": literal("true"),
                        "selectAllCheckboxEnabled": literal("false"),
                    }
                }
            ],
            "general": [
                {
                    "properties": {
                        "filter": {
                            "filter": {
                                "Version": 2,
                                "From": [{"Name": "m", "Entity": table, "Type": 0}],
                                "Where": [
                                    {
                                        "Condition": {
                                            "In": {
                                                "Expressions": [
                                                    {
                                                        "Column": {
                                                            "Expression": {
                                                                "SourceRef": {"Source": "m"}
                                                            },
                                                            "Property": column,
                                                        }
                                                    }
                                                ],
                                                "Values": [[{"Literal": {"Value": "'Overall'"}}]],
                                            }
                                        }
                                    }
                                ],
                            }
                        }
                    }
                }
            ],
        }
    return visual(
        name,
        x,
        y,
        width,
        108,
        "slicer",
        {"Values": {"projections": [column_field(table, column)]}},
        objects,
    )


def chart(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    visual_type: str,
    category: tuple[str, str],
    measures: list[tuple[str, str]],
    series: tuple[str, str] | None = None,
    labels: bool = False,
    caption: str | None = None,
    precision: int = 0,
) -> dict:
    query_state = {
        "Category": {"projections": [column_field(*category)]},
        "Y": {"projections": [measure_field(*measure) for measure in measures]},
    }
    if series:
        query_state["Series"] = {"projections": [column_field(*series)]}
    objects = line_objects() if visual_type in {"lineChart", "areaChart"} else chart_objects(labels)
    if labels:
        objects["labels"][0]["properties"].update(
            {
                "labelDisplayUnits": literal("1D"),
                "labelPrecision": literal(f"{precision}L"),
            }
        )
    result = visual(name, x, y, width, height, visual_type, query_state, objects)
    if caption:
        result["visual"]["visualContainerObjects"] = {
            "title": [
                {
                    "properties": {
                        "show": literal("true"),
                        "text": literal("'" + caption + "'"),
                    }
                }
            ]
        }
    if visual_type not in {"lineChart", "areaChart"}:
        result["visual"]["query"]["sortDefinition"] = {
            "sort": [
                {
                    "field": column_field(*category)["field"],
                    "direction": "Ascending",
                }
            ]
        }
    return result


def detail_table(
    name: str,
    x: int,
    y: int,
    width: int,
    height: int,
    fields: list[tuple[str, str, bool]],
) -> dict:
    projections = [
        measure_field(table, field) if is_measure else column_field(table, field)
        for table, field, is_measure in fields
    ]
    return visual(
        name,
        x,
        y,
        width,
        height,
        "tableEx",
        {"Values": {"projections": projections}},
        table_objects(),
    )


def write_page(page_id: str, display_name: str, visuals: list[dict]) -> None:
    page_dir = PAGES_ROOT / page_id
    write_json(
        page_dir / "page.json",
        {
            "$schema": SCHEMA_PAGE,
            "name": page_id,
            "displayName": display_name,
            "displayOption": "FitToPage",
            "height": 720,
            "width": 1280,
        },
    )
    for item in visuals:
        write_json(page_dir / "visuals" / item["name"] / "visual.json", item)


def postgres_partition(view_name: str) -> str:
    result = f'''let
			Source = PostgreSQL.Database(
				"localhost:5432",
				"retail_analytics",
				[CreateNavigationProperties=false]
			),
			Data = Source{{[Schema="public", Item="{view_name}"]}}[Data]
		in
			Data'''
    if view_name == "dashboard_user_activity_distribution":
        result = result.rsplit("Data", 1)[0] + (
            'Table.AddColumn(Data, "activity_bucket_label", '
            'each Text.From([bucket_order]) & ". " & [activity_bucket], type text)'
        )
    return result


def table_tmdl(
    table_name: str,
    view_name: str,
    columns: list[tuple[str, str, str, str | None, str | None, bool]],
    measures: list[tuple[str, str, str]],
) -> str:
    names = [column[0].casefold() for column in columns]
    names += [measure[0].casefold() for measure in measures]
    if len(names) != len(set(names)):
        raise ValueError(f"Duplicate column/measure name in {table_name}")
    lines = [f"table '{table_name}'", ""]
    for measure_name, expression, format_string in measures:
        lines.extend(
            [
                f"\tmeasure '{measure_name}' = {expression}",
                f"\t\tformatString: {format_string}",
                "",
            ]
        )
        dax_format = format_string.replace('"', '""')
        lines.extend(
            [
                f"\tmeasure '{measure_name} Display' = "
                f"IF(ISBLANK([{measure_name}]), BLANK(), "
                f'FORMAT([{measure_name}], "{dax_format}", "en-US"))',
                "\t\tisHidden",
                "",
            ]
        )
    for name, source, data_type, format_string, sort_by, hidden in columns:
        lines.extend([f"\tcolumn '{name}'", f"\t\tdataType: {data_type}"])
        if format_string:
            lines.append(f"\t\tformatString: {format_string}")
        if sort_by:
            lines.append(f"\t\tsortByColumn: '{sort_by}'")
        if hidden:
            lines.append("\t\tisHidden")
        lines.extend(["\t\tsummarizeBy: none", f"\t\tsourceColumn: {source}", ""])
    lines.extend(
        [
            f"\tpartition '{table_name}' = m",
            "\t\tmode: import",
            "\t\tsource =",
            "\t\t\t" + postgres_partition(view_name).replace("\n", "\n\t\t\t"),
        ]
    )
    return "\n".join(lines)


def write_semantic_model() -> None:
    definition = MODEL_ROOT / "definition"
    tables = definition / "tables"
    write_json(
        MODEL_ROOT / "definition.pbism",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/"
                "definitionProperties/1.0.0/schema.json"
            ),
            "version": "4.2",
            "settings": {"qnaEnabled": True},
        },
    )
    write_text(
        definition / "database.tmdl",
        f"database {uuid.uuid5(uuid.NAMESPACE_DNS, PROJECT_NAME)}\n"
        "\tcompatibilityLevel: 1702\n"
        "\tcompatibilityMode: powerBI\n"
        "\tlanguage: 1033",
    )

    table_names = [
        "Fact Events",
        "Calendar",
        "Top Items",
        "Top Categories",
        "User Activity",
        "Funnel Stages",
        "Recommendation Metrics",
        "Evaluation Protocol",
    ]
    model_lines = [
        "model Model",
        "\tculture: en-US",
        "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
        "\tsourceQueryCulture: en-US",
        "\tdiscourageImplicitMeasures",
        "\tannotation __PBI_TimeIntelligenceEnabled = 0",
        "",
    ] + [f"ref table '{name}'" for name in table_names]
    write_text(definition / "model.tmdl", "\n".join(model_lines))

    fact_measures = [
        ("Total Events", "COUNTROWS('Fact Events')", "#,0"),
        ("Total Users", "DISTINCTCOUNT('Fact Events'[Visitor ID])", "#,0"),
        ("Total Items", "DISTINCTCOUNT('Fact Events'[Item ID])", "#,0"),
        ("Views", "CALCULATE([Total Events], 'Fact Events'[Event Type] = \"view\")", "#,0"),
        (
            "Cart Adds",
            "CALCULATE([Total Events], 'Fact Events'[Event Type] = \"addtocart\")",
            "#,0",
        ),
        (
            "Transactions",
            "CALCULATE([Total Events], 'Fact Events'[Event Type] = \"transaction\")",
            "#,0",
        ),
        ("Cart / View Events", "DIVIDE([Cart Adds], [Views])", "0.00%"),
        ("Purchase / Cart Events", "DIVIDE([Transactions], [Cart Adds])", "0.00%"),
        ("Purchase / View Events", "DIVIDE([Transactions], [Views])", "0.00%"),
    ]
    write_text(
        tables / "Fact Events.tmdl",
        table_tmdl(
            "Fact Events",
            "dashboard_fact_events",
            [
                ("Event Date", "event_date", "dateTime", "yyyy-MM-dd", None, False),
                ("Event Hour", "event_hour", "int64", None, None, False),
                ("Visitor ID", "visitor_id", "int64", None, None, False),
                ("Item ID", "item_id", "int64", None, None, False),
                ("Category ID", "category_id", "int64", None, None, False),
                ("Event Type", "event_type", "string", None, None, False),
                ("Source", "source", "string", None, None, False),
            ],
            fact_measures,
        ),
    )
    write_text(
        tables / "Calendar.tmdl",
        table_tmdl(
            "Calendar",
            "dashboard_calendar",
            [
                ("Date", "calendar_date", "dateTime", "yyyy-MM-dd", None, False),
                ("Year", "calendar_year", "int64", "0", None, False),
                ("Month Number", "calendar_month_number", "int64", "0", None, True),
                ("Month", "calendar_month", "string", None, None, False),
                ("Day Number", "day_of_week_number", "int64", "0", None, True),
                ("Day of Week", "day_of_week", "string", None, None, False),
            ],
            [],
        ),
    )
    write_text(
        tables / "Top Items.tmdl",
        table_tmdl(
            "Top Items",
            "dashboard_top_items",
            [
                ("Purchase Rank", "purchase_rank", "int64", "0", None, True),
                ("Item ID", "item_id", "string", None, None, False),
                ("Category ID", "category_id", "string", None, None, False),
                ("Views", "views", "int64", "#,0", None, False),
                ("Cart Adds", "cart_adds", "int64", "#,0", None, False),
                ("Purchases", "purchases", "int64", "#,0", None, False),
                ("Unique Users", "unique_users", "int64", "#,0", None, False),
                ("Purchase / View Events", "view_to_purchase_rate", "double", "0.00%", None, False),
            ],
            [
                ("Total Item Views", "SUM('Top Items'[Views])", "#,0"),
                ("Total Item Purchases", "SUM('Top Items'[Purchases])", "#,0"),
                ("Total Item Cart Adds", "SUM('Top Items'[Cart Adds])", "#,0"),
            ],
        ),
    )
    write_text(
        tables / "Top Categories.tmdl",
        table_tmdl(
            "Top Categories",
            "dashboard_top_categories",
            [
                ("Purchase Rank", "purchase_rank", "int64", "0", None, True),
                (
                    "Category ID",
                    "category_id",
                    "string",
                    None,
                    None,
                    False,
                ),
                ("Views", "views", "int64", "#,0", None, False),
                ("Cart Adds", "cart_adds", "int64", "#,0", None, False),
                ("Purchases", "purchases", "int64", "#,0", None, False),
                ("Unique Users", "unique_users", "int64", "#,0", None, False),
                ("Distinct Items", "distinct_items", "int64", "#,0", None, False),
            ],
            [
                ("Total Category Purchases", "SUM('Top Categories'[Purchases])", "#,0"),
                ("Total Category Views", "SUM('Top Categories'[Views])", "#,0"),
            ],
        ),
    )
    write_text(
        tables / "User Activity.tmdl",
        table_tmdl(
            "User Activity",
            "dashboard_user_activity_distribution",
            [
                ("Activity Bucket", "activity_bucket_label", "string", None, None, False),
                ("Bucket Order", "bucket_order", "int64", "0", None, True),
                ("User Count", "user_count", "int64", "#,0", None, False),
            ],
            [("Users in Bucket", "SUM('User Activity'[User Count])", "#,0")],
        ),
    )
    write_text(
        tables / "Funnel Stages.tmdl",
        table_tmdl(
            "Funnel Stages",
            "dashboard_funnel_stages",
            [
                ("Stage Order", "stage_order", "int64", "0", None, True),
                ("Stage", "stage", "string", None, None, False),
                ("Users", "users", "int64", "#,0", None, False),
            ],
            [
                (
                    "Stage Users",
                    "VAR StageNumber = SELECTEDVALUE('Funnel Stages'[Stage Order]) "
                    'VAR EventName = SWITCH(StageNumber, 1, "view", 2, "addtocart", '
                    '3, "transaction") RETURN IF(NOT ISBLANK(EventName), '
                    "CALCULATE(DISTINCTCOUNT('Fact Events'[Visitor ID]), "
                    "'Fact Events'[Event Type] = EventName))",
                    "#,0",
                )
            ],
        ),
    )
    write_text(
        tables / "Recommendation Metrics.tmdl",
        table_tmdl(
            "Recommendation Metrics",
            "recommendation_evaluation_metrics",
            [
                ("Cohort", "cohort", "string", None, None, False),
                ("Model", "model_name", "string", None, None, False),
                ("Metric", "metric_name", "string", None, None, False),
                ("Metric Value", "metric_value", "double", "0.000%", None, False),
                ("Evaluated Users", "evaluated_users", "int64", "#,0", None, False),
            ],
            [
                (
                    "Selected Metric Value",
                    "IF(HASONEVALUE('Recommendation Metrics'[Cohort]) "
                    "&& COUNTROWS('Recommendation Metrics') = 1, "
                    "SELECTEDVALUE('Recommendation Metrics'[Metric Value]))",
                    "0.0000%",
                ),
                ("Metric Evaluated Users", "MAX('Recommendation Metrics'[Evaluated Users])", "#,0"),
            ],
        ),
    )
    coverage_lift = (
        "VAR TT = CALCULATE(MAX('Recommendation Metrics'[Metric Value]), "
        "FILTER(ALL('Recommendation Metrics'), 'Recommendation Metrics'[Cohort] = \"Overall\" "
        "&& 'Recommendation Metrics'[Model] = \"Two-Tower + fallback\" "
        "&& 'Recommendation Metrics'[Metric] = \"catalog_coverage@10\")) "
        "VAR Pop = CALCULATE(MAX('Recommendation Metrics'[Metric Value]), "
        "FILTER(ALL('Recommendation Metrics'), 'Recommendation Metrics'[Cohort] = \"Overall\" "
        "&& 'Recommendation Metrics'[Model] = \"Popularity\" "
        "&& 'Recommendation Metrics'[Metric] = \"catalog_coverage@10\")) RETURN DIVIDE(TT, Pop)"
    )
    write_text(
        tables / "Evaluation Protocol.tmdl",
        table_tmdl(
            "Evaluation Protocol",
            "recommendation_evaluation_protocol",
            [
                ("ID", "id", "int64", "0", None, True),
                ("Sampled Users", "sampled_test_users", "int64", "#,0", None, False),
                ("Evaluated Users", "evaluated_users", "int64", "#,0", None, False),
                ("Warm Users", "warm_evaluated_users", "int64", "#,0", None, False),
                ("Cold Users", "cold_user_fallbacks", "int64", "#,0", None, False),
                (
                    "Cold Item Interactions",
                    "cold_start_item_interactions",
                    "int64",
                    "#,0",
                    None,
                    False,
                ),
                ("K", "recommendation_k", "int64", "0", None, False),
                ("Seed", "evaluation_seed", "int64", "0", None, True),
                ("Source Artifact", "source_artifact", "string", None, None, True),
                ("Loaded At", "loaded_at", "dateTime", "yyyy-MM-dd HH:mm", None, True),
            ],
            [
                (
                    "Evaluated User Count",
                    "MAX('Evaluation Protocol'[Evaluated Users])",
                    "#,0",
                ),
                ("Warm User Count", "MAX('Evaluation Protocol'[Warm Users])", "#,0"),
                ("Cold User Count", "MAX('Evaluation Protocol'[Cold Users])", "#,0"),
                (
                    "Cold Start Share",
                    "DIVIDE(MAX('Evaluation Protocol'[Cold Users]), "
                    "MAX('Evaluation Protocol'[Evaluated Users]))",
                    "0.0%",
                ),
                ("Overall Coverage Lift", coverage_lift, '0.0"x"'),
            ],
        ),
    )
    relationship_id = uuid.uuid5(uuid.NAMESPACE_DNS, PROJECT_NAME + ":calendar")
    write_text(
        definition / "relationships.tmdl",
        f"relationship {relationship_id}\n"
        "\tfromColumn: 'Fact Events'.'Event Date'\n"
        "\ttoColumn: 'Calendar'.Date",
    )


def write_report() -> None:
    PAGES_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(
        REPORT_ROOT / "definition.pbir",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/fabric/item/report/"
                "definitionProperties/2.0.0/schema.json"
            ),
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{PROJECT_NAME}.SemanticModel"}},
        },
    )
    write_json(
        REPORT_ROOT / "definition" / "version.json",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
                "versionMetadata/1.0.0/schema.json"
            ),
            "version": "2.0.0",
        },
    )
    write_json(
        REPORT_ROOT / "definition" / "report.json",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
                "report/3.3.0/schema.json"
            ),
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU10",
                    "reportVersionAtImport": {
                        "visual": "2.9.0",
                        "page": "2.1.0",
                        "report": "3.3.0",
                    },
                    "type": "SharedResources",
                }
            },
            "settings": {
                "defaultFilterActionIsDataFilter": True,
                "useEnhancedTooltips": True,
                "pagesPosition": "Bottom",
                "locale": "en-US",
            },
            "annotations": [
                {
                    "name": "Project",
                    "value": "Retailrocket real-time recommendation analytics portfolio dashboard",
                }
            ],
        },
    )

    overview = uid("page_overview")
    funnel = uid("page_funnel")
    users_products = uid("page_users_products")
    recommendations = uid("page_recommendations")

    write_page(
        overview,
        "Executive Overview",
        [
            title("overview_title", "Retail Recommendation Analytics — Executive Overview"),
            card("overview_users", 20, 66, 225, "Fact Events", "Total Users"),
            card("overview_events", 260, 66, 225, "Fact Events", "Total Events"),
            card("overview_items", 500, 66, 225, "Fact Events", "Total Items"),
            card("overview_conversion", 740, 66, 225, "Fact Events", "Purchase / View Events"),
            slicer("overview_date", 980, 66, 280, "Calendar", "Date"),
            chart(
                "overview_trend",
                20,
                194,
                760,
                270,
                "lineChart",
                ("Calendar", "Date"),
                [
                    ("Fact Events", "Views"),
                    ("Fact Events", "Cart Adds"),
                    ("Fact Events", "Transactions"),
                ],
            ),
            chart(
                "overview_items_bar",
                800,
                194,
                460,
                270,
                "clusteredBarChart",
                ("Top Items", "Item ID"),
                [("Top Items", "Total Item Purchases")],
                labels=True,
                caption="Top 20 items by purchase events (full-period snapshot)",
            ),
            chart(
                "overview_categories_bar",
                20,
                484,
                1240,
                175,
                "clusteredBarChart",
                ("Top Categories", "Category ID"),
                [("Top Categories", "Total Category Purchases")],
                labels=True,
                caption="Top 15 categories by purchase events (full-period snapshot)",
            ),
            insight(
                "overview_scope",
                "Date filters apply to cards and daily trends. "
                "Rankings are full-period snapshots. Ratios use event counts, not users.",
                20,
                669,
                1240,
                40,
            ),
        ],
    )
    write_page(
        funnel,
        "Funnel Analysis",
        [
            title("funnel_title", "Behavior Stages — Distinct Users and Event Ratios"),
            card("funnel_v2c", 20, 66, 285, "Fact Events", "Cart / View Events"),
            card("funnel_c2p", 325, 66, 285, "Fact Events", "Purchase / Cart Events"),
            card("funnel_v2p", 630, 66, 285, "Fact Events", "Purchase / View Events"),
            slicer("funnel_date", 935, 66, 325, "Calendar", "Date"),
            chart(
                "funnel_visual",
                20,
                194,
                430,
                500,
                "clusteredBarChart",
                ("Funnel Stages", "Stage"),
                [("Funnel Stages", "Stage Users")],
                labels=True,
                caption="Distinct users per stage (selected dates; not sequential)",
            ),
            chart(
                "funnel_conversion_trend",
                470,
                194,
                790,
                300,
                "lineChart",
                ("Calendar", "Date"),
                [
                    ("Fact Events", "Cart / View Events"),
                    ("Fact Events", "Purchase / Cart Events"),
                    ("Fact Events", "Purchase / View Events"),
                ],
            ),
            insight(
                "funnel_note",
                "All charts and cards respond to the date filter. Left: users with each "
                "event type, counted separately; this does not track an ordered user journey. "
                "Cards and trend: ratios of EVENT COUNTS, not user conversion rates. "
                "For example, Purchase / Cart Events divides transactions by cart-add events.",
                470,
                514,
                790,
                180,
            ),
        ],
    )
    write_page(
        users_products,
        "User & Product Analytics",
        [
            title("users_title", "User Activity and Product Engagement — Full Period"),
            card("users_total", 20, 66, 285, "Fact Events", "Total Users"),
            card("users_items", 325, 66, 285, "Fact Events", "Total Items"),
            card("users_cart", 630, 66, 285, "Fact Events", "Cart Adds"),
            insight(
                "users_scope",
                "Full-period snapshots. Products: top 20 by purchase "
                "events. No hour/date filter applies on this page.",
                935,
                66,
                325,
                108,
            ),
            chart(
                "users_distribution",
                20,
                194,
                500,
                270,
                "clusteredColumnChart",
                ("User Activity", "Activity Bucket"),
                [("User Activity", "Users in Bucket")],
                labels=True,
                caption="Users by activity level (exact counts; full period)",
            ),
            chart(
                "users_product_engagement",
                540,
                194,
                720,
                270,
                "clusteredBarChart",
                ("Top Items", "Item ID"),
                [
                    ("Top Items", "Total Item Views"),
                    ("Top Items", "Total Item Cart Adds"),
                    ("Top Items", "Total Item Purchases"),
                ],
            ),
            detail_table(
                "users_product_table",
                20,
                484,
                1240,
                215,
                [
                    ("Top Items", "Item ID", False),
                    ("Top Items", "Category ID", False),
                    ("Top Items", "Views", False),
                    ("Top Items", "Cart Adds", False),
                    ("Top Items", "Purchases", False),
                    ("Top Items", "Unique Users", False),
                    ("Top Items", "Purchase / View Events", False),
                ],
            ),
        ],
    )
    write_page(
        recommendations,
        "Recommendation Performance",
        [
            title(
                "recommendation_title",
                "Recommendation Evaluation — Accuracy, Coverage and Cold Start",
            ),
            card(
                "recommendation_users",
                20,
                66,
                225,
                "Evaluation Protocol",
                "Evaluated User Count",
            ),
            card(
                "recommendation_warm",
                260,
                66,
                225,
                "Evaluation Protocol",
                "Warm User Count",
            ),
            card("recommendation_cold", 500, 66, 225, "Evaluation Protocol", "Cold Start Share"),
            card(
                "recommendation_lift", 740, 66, 225, "Evaluation Protocol", "Overall Coverage Lift"
            ),
            slicer("recommendation_cohort", 980, 66, 280, "Recommendation Metrics", "Cohort"),
            chart(
                "recommendation_metric_comparison",
                20,
                194,
                760,
                300,
                "clusteredColumnChart",
                ("Recommendation Metrics", "Metric"),
                [("Recommendation Metrics", "Selected Metric Value")],
                series=("Recommendation Metrics", "Model"),
                labels=True,
                caption="Recommendation metrics — select exactly one cohort",
                precision=4,
            ),
            insight(
                "recommendation_story",
                "Accuracy is nearly flat, so the defensible model result is broader "
                "discovery: catalog coverage rises from about 0.0061% to 0.505% "
                "(≈82.8×). With 93.3% cold users, popularity fallback remains essential. "
                "Top cards describe the OVERALL evaluation and do not change with Cohort. "
                "The chart stays blank if multiple cohorts are selected. Metric values "
                "must never be summed across cohorts or models.",
                800,
                194,
                460,
                300,
            ),
            detail_table(
                "recommendation_metrics_table",
                20,
                514,
                1240,
                185,
                [
                    ("Recommendation Metrics", "Cohort", False),
                    ("Recommendation Metrics", "Model", False),
                    ("Recommendation Metrics", "Metric", False),
                    ("Recommendation Metrics", "Metric Value", False),
                    ("Recommendation Metrics", "Evaluated Users", False),
                ],
            ),
        ],
    )
    write_json(
        PAGES_ROOT / "pages.json",
        {
            "$schema": SCHEMA_PAGES,
            "pageOrder": [overview, funnel, users_products, recommendations],
            "activePageName": overview,
        },
    )


def write_project_files() -> None:
    PROJECT_ROOT.mkdir(parents=True, exist_ok=True)
    write_json(
        PROJECT_ROOT / f"{PROJECT_NAME}.pbip",
        {
            "$schema": (
                "https://developer.microsoft.com/json-schemas/fabric/pbip/"
                "pbipProperties/1.0.0/schema.json"
            ),
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{PROJECT_NAME}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    write_text(
        PROJECT_ROOT / ".gitignore",
        "**/.pbi/localSettings.json\n**/.pbi/cache.abf",
    )


def main(argv: list[str] | None = None) -> int:
    global PROJECT_ROOT, REPORT_ROOT, MODEL_ROOT, PAGES_ROOT
    parser = argparse.ArgumentParser(description="Generate a separate Power BI review project.")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT)
    args = parser.parse_args(argv)
    PROJECT_ROOT = args.output.resolve()
    if PROJECT_ROOT.exists() and any(PROJECT_ROOT.iterdir()):
        parser.error("Output must be empty: existing reports and caches are never overwritten.")
    REPORT_ROOT = PROJECT_ROOT / f"{PROJECT_NAME}.Report"
    MODEL_ROOT = PROJECT_ROOT / f"{PROJECT_NAME}.SemanticModel"
    PAGES_ROOT = REPORT_ROOT / "definition" / "pages"
    write_project_files()
    write_semantic_model()
    write_report()
    print(f"Generated Power BI project: {PROJECT_ROOT / (PROJECT_NAME + '.pbip')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
