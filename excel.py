import logging
import pandas as pd
from datetime import datetime

logger = logging.getLogger(__name__)

def save_to_excel(results, filepath):
    if not results:
        logger.warning("No results to save.")
        df = pd.DataFrame(columns=["URL", "Timestamp", "Caption", "Source"])
        with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
            df.to_excel(writer, sheet_name="Data", index=False)
            
            summary_df = pd.DataFrame([{"Total Results": 0}])
            summary_df.to_excel(writer, sheet_name="Summary", index=False)
        return False

    try:
        df = pd.DataFrame(results)
        
        # Standardize column names
        df.rename(columns={
            "url": "URL",
            "timestamp": "Timestamp",
            "caption": "Caption",
            "source": "Source",
        }, inplace=True)
        
        # Convert timestamp to human-readable datetime if it's numeric
        if pd.api.types.is_numeric_dtype(df['Timestamp']):
            df['Datetime'] = pd.to_datetime(df['Timestamp'], unit='s')
        else:
            df['Datetime'] = df['Timestamp']

        # Reorder columns
        cols = ["URL", "Datetime", "Source", "Caption"]
        df = df[[c for c in cols if c in df.columns]]

        # Generate summary statistics
        source_counts = df["Source"].value_counts().reset_index()
        source_counts.columns = ["Source", "Count"]
        
        total_items = len(df)
        summary_general = pd.DataFrame([
            {"Metric": "Total Results", "Value": total_items},
            {"Metric": "Export Time", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
        ])

        with pd.ExcelWriter(filepath, engine="xlsxwriter") as writer:
            # 1. Write Main Data Sheet
            df.to_excel(writer, sheet_name="Data", index=False)
            workbook = writer.book
            worksheet = writer.sheets["Data"]
            
            # Formats
            header_format = workbook.add_format({
                "bold": True,
                "fg_color": "#4F81BD",
                "font_color": "white",
                "border": 1
            })
            text_format = workbook.add_format({"text_wrap": True, "valign": "top"})
            link_format = workbook.add_format({
                "font_color": "blue",
                "underline": True,
                "valign": "top"
            })
            
            # Apply format to header row
            for col_num, value in enumerate(df.columns.values):
                worksheet.write(0, col_num, value, header_format)

            # Set column widths
            worksheet.set_column("A:A", 45, link_format)  # URL
            worksheet.set_column("B:B", 20, text_format)  # Datetime
            worksheet.set_column("C:C", 25, text_format)  # Source
            worksheet.set_column("D:D", 80, text_format)  # Caption

            # Apply alternating row colors
            row_formats = [
                workbook.add_format({"bg_color": "#FFFFFF", "valign": "top", "text_wrap": True}),
                workbook.add_format({"bg_color": "#F2F2F2", "valign": "top", "text_wrap": True})
            ]
            
            for row_num in range(1, len(df) + 1):
                fmt = row_formats[row_num % 2]
                worksheet.set_row(row_num, 60, fmt) # Set a fixed height for text wrapping
                
                url_val = df.iloc[row_num-1]["URL"]
                if pd.notna(url_val):
                    worksheet.write_url(row_num, 0, url_val, string=url_val)

            summary_general.to_excel(writer, sheet_name="Summary", index=False, startrow=0)
            source_counts.to_excel(writer, sheet_name="Summary", index=False, startrow=4)
            
            summary_worksheet = writer.sheets["Summary"]
            summary_worksheet.set_column("A:B", 25)

        logger.info("Successfully saved %d results to %s", total_items, filepath)
        return True

    except Exception as e:
        logger.error("Failed to save Excel file: %s", e)
        return False
