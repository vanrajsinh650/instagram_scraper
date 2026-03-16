import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


def save_to_excel(results, filepath):
    columns = [
        "Cafe Name", "Phone", "Email", "Address", "Username",
        "Source", "URL", "Website/Link", "Datetime", "Caption", "Bio"
    ]

    if not results:
        logger.warning("No results to save.")
        df = pd.DataFrame(columns=columns)
        with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Data", index=False)
            pd.DataFrame([{"Total Results": 0}]).to_excel(writer, sheet_name="Summary", index=False)
        return False

    try:
        df = pd.DataFrame(results)

        rename_map = {
            "cafe_name": "Cafe Name",
            "phone": "Phone",
            "email": "Email",
            "address": "Address",
            "url": "URL",
            "username": "Username",
            "timestamp": "Timestamp",
            "caption": "Caption",
            "source": "Source",
            "bio": "Bio",
            "external_link": "Website/Link",
        }
        df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

        if "Timestamp" in df.columns:
            if pd.api.types.is_numeric_dtype(df["Timestamp"]):
                df["Datetime"] = pd.to_datetime(df["Timestamp"], unit="s", errors="coerce")
            else:
                df["Datetime"] = pd.to_datetime(df["Timestamp"], errors="coerce")

        df.drop(columns=["Timestamp", "shortcode"], errors="ignore", inplace=True)

        cols = [c for c in columns if c in df.columns]
        df = df[cols]

        with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Data", index=False)
            wb = writer.book
            ws = writer.sheets["Data"]

            hdr = wb.add_format({"bold": True, "fg_color": "#4F81BD", "font_color": "white", "border": 1})
            txt = wb.add_format({"text_wrap": True, "valign": "top"})
            lnk = wb.add_format({"font_color": "blue", "underline": True, "valign": "top"})

            for i, v in enumerate(df.columns):
                ws.write(0, i, v, hdr)

            widths = {
                "Cafe Name": 28, "Phone": 16, "Email": 26, "Address": 35,
                "Username": 18, "Source": 22, "URL": 40, "Website/Link": 28,
                "Datetime": 18, "Caption": 55, "Bio": 40,
            }
            for i, c in enumerate(df.columns):
                ws.set_column(i, i, widths.get(c, 18), lnk if c in ("URL", "Website/Link") else txt)

            alt = [
                wb.add_format({"bg_color": "#FFFFFF", "valign": "top", "text_wrap": True}),
                wb.add_format({"bg_color": "#F2F2F2", "valign": "top", "text_wrap": True}),
            ]
            url_col = list(df.columns).index("URL") if "URL" in df.columns else -1
            for r in range(1, len(df) + 1):
                ws.set_row(r, 45, alt[r % 2])
                if url_col >= 0:
                    val = df.iloc[r - 1]["URL"]
                    if pd.notna(val) and str(val).startswith("http"):
                        ws.write_url(r, url_col, str(val), string=str(val))

            summary = pd.DataFrame([
                {"Metric": "Total", "Value": str(len(df))},
                {"Metric": "With Phone", "Value": str((df.get("Phone", pd.Series()).astype(str) != "").sum())},
                {"Metric": "With Email", "Value": str((df.get("Email", pd.Series()).astype(str) != "").sum())},
                {"Metric": "Exported", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            ])
            summary.to_excel(writer, sheet_name="Summary", index=False)
            writer.sheets["Summary"].set_column("A:B", 20)

        logger.info("Saved %d results to %s", len(df), filepath)
        return True

    except Exception as e:
        logger.error("Excel save failed: %s", e)
        return False
