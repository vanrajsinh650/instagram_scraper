import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)


def save_to_excel(results, filepath):
    if not results:
        logger.warning("No results to save.")
        df = pd.DataFrame(columns=[
            "Cafe Name", "Phone", "Email", "URL", "Username", "Source", "Datetime", "Caption"
        ])
        with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Data", index=False)
            summary_df = pd.DataFrame([{"Total Results": 0}])
            summary_df.to_excel(writer, sheet_name="Summary", index=False)
        return False

    try:
        df = pd.DataFrame(results)

        rename_map = {
            "cafe_name": "Cafe Name",
            "phone": "Phone",
            "email": "Email",
            "url": "URL",
            "username": "Username",
            "timestamp": "Timestamp",
            "caption": "Caption",
            "source": "Source",
            "bio": "Bio",
        }
        df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns}, inplace=True)

        if "Timestamp" in df.columns:
            if pd.api.types.is_numeric_dtype(df["Timestamp"]):
                df["Datetime"] = pd.to_datetime(df["Timestamp"], unit="s")
            else:
                df["Datetime"] = df["Timestamp"]

        # Drop internal columns
        df.drop(columns=["Timestamp", "shortcode"], errors="ignore", inplace=True)

        # Reorder — name and contact first, then source info
        desired_order = [
            "Cafe Name", "Phone", "Email", "Username", "Source",
            "URL", "Datetime", "Caption", "Bio"
        ]
        cols = [c for c in desired_order if c in df.columns]
        df = df[cols]

        # Summaries
        source_counts = df["Source"].value_counts().reset_index()
        source_counts.columns = ["Source", "Count"]

        posts_with_phone = df["Phone"].notna() & (df["Phone"] != "")
        posts_with_email = df["Email"].notna() & (df["Email"] != "")

        summary_general = pd.DataFrame([
            {"Metric": "Total Results", "Value": str(len(df))},
            {"Metric": "Posts with Phone", "Value": str(posts_with_phone.sum())},
            {"Metric": "Posts with Email", "Value": str(posts_with_email.sum())},
            {"Metric": "Export Time", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        ])

        with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Data", index=False)
            workbook = writer.book
            worksheet = writer.sheets["Data"]

            header_fmt = workbook.add_format({
                "bold": True,
                "fg_color": "#4F81BD",
                "font_color": "white",
                "border": 1,
            })
            text_fmt = workbook.add_format({"text_wrap": True, "valign": "top"})
            link_fmt = workbook.add_format({
                "font_color": "blue",
                "underline": True,
                "valign": "top",
            })

            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_fmt)

            # Column widths — keyed by column name
            col_widths = {
                "Cafe Name": 30,
                "Phone": 18,
                "Email": 30,
                "Username": 20,
                "Source": 25,
                "URL": 45,
                "Datetime": 20,
                "Caption": 70,
                "Bio": 50,
            }

            for col_num, col_name in enumerate(df.columns):
                width = col_widths.get(col_name, 20)
                fmt = link_fmt if col_name == "URL" else text_fmt
                worksheet.set_column(col_num, col_num, width, fmt)

            # Alternating row colors
            row_fmts = [
                workbook.add_format({"bg_color": "#FFFFFF", "valign": "top", "text_wrap": True}),
                workbook.add_format({"bg_color": "#F2F2F2", "valign": "top", "text_wrap": True}),
            ]

            for row_num in range(1, len(df) + 1):
                fmt = row_fmts[row_num % 2]
                worksheet.set_row(row_num, 50, fmt)

                # Make URL column clickable
                url_col_idx = list(df.columns).index("URL") if "URL" in df.columns else -1
                if url_col_idx >= 0:
                    url_val = df.iloc[row_num - 1]["URL"]
                    if pd.notna(url_val):
                        worksheet.write_url(row_num, url_col_idx, url_val, string=url_val)

            # Summary sheet
            summary_general.to_excel(writer, sheet_name="Summary", index=False, startrow=0)
            source_counts.to_excel(writer, sheet_name="Summary", index=False, startrow=6)

            summary_ws = writer.sheets["Summary"]
            summary_ws.set_column("A:B", 25)

        logger.info("Saved %d results to %s", len(df), filepath)
        return True

    except Exception as e:
        logger.error("Failed to save Excel file: %s", e)
        return False
