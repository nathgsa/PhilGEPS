#!/usr/bin/env python3
"""
Data Cleaner for PhilGEPS CSV Data

BUGS FIXED:
  BUG-DC-1  date_patterns[0] == date_patterns[4] — the MM/DD/YYYY entry was an
            exact duplicate of DD/MM/YYYY so it never matched.  Fixed with smart
            disambiguation: if day > 12 it MUST be DD/MM; if month > 12 it MUST
            be MM/DD; otherwise default to Philippine DD/MM/YYYY.
  BUG-DC-2  clean_currency() had no ₱ prefix handler — amounts written as
            '₱55,200.00' always fell through and returned None.  Fixed by
            matching both PHP and ₱ in the same regex.
"""

import pandas as pd
import re
from datetime import datetime
import logging
from typing import Optional, Tuple

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class PhilGEPSDataCleaner:
    """Data cleaner for PhilGEPS procurement data."""

    def __init__(self, input_file: str, output_file: str = None):
        self.input_file  = input_file
        self.output_file = output_file or input_file.replace('.csv', '_cleaned.csv')
        self.df          = None

    def load_data(self) -> pd.DataFrame:
        try:
            logger.info(f"Loading data from {self.input_file}")
            self.df = pd.read_csv(self.input_file)
            logger.info(f"Loaded {len(self.df)} rows and {len(self.df.columns)} columns")
            return self.df
        except Exception as e:
            logger.error(f"Error loading data: {e}")
            raise

    # ── BUG-DC-2 FIX: recognise both PHP and ₱ ───────────────────────────────
    def clean_currency(self, amount_str: str) -> Optional[float]:
        """
        Clean and standardise currency values.

        Accepts:
          • 'PHP 55,200.00'   — original format
          • '₱55,200.00'      — BUG-DC-2 FIX: ₱ prefix now handled
          • '55200'           — plain numeric fallback
        """
        if pd.isna(amount_str) or amount_str == '':
            return None

        # BUG-DC-2 FIX: match either PHP or ₱ as the currency prefix
        match = re.search(r'(?:PHP|₱)\s*([\d,]+\.?\d*)', str(amount_str))
        if match:
            try:
                return float(match.group(1).replace(',', ''))
            except ValueError:
                logger.warning(f"Could not convert currency value: {amount_str}")
                return None

        # Fallback: plain numeric string with no prefix
        numeric_match = re.search(r'([\d,]+\.?\d*)', str(amount_str))
        if numeric_match:
            try:
                return float(numeric_match.group(1).replace(',', ''))
            except ValueError:
                pass

        logger.warning(f"Could not parse currency: {amount_str}")
        return None

    # ── BUG-DC-1 FIX: smart DD/MM vs MM/DD disambiguation ───────────────────
    def clean_date(self, date_str: str) -> Optional[str]:
        """
        Standardise date values to YYYY-MM-DD.

        BUG-DC-1 FIX: the original code had patterns[0] == patterns[4], both
        matching DD/MM/YYYY but the second one formatting as MM/DD/YYYY — it was
        unreachable because patterns[0] always consumed the match first.

        Replaced with a single pattern that disambiguates:
          • If day part > 12  → definitely DD/MM/YYYY (months stop at 12)
          • If month part > 12 → definitely MM/DD/YYYY
          • Ambiguous (both ≤ 12) → Philippine default DD/MM/YYYY,
            retry as MM/DD/YYYY if that produces an invalid date
        """
        if pd.isna(date_str) or date_str == '':
            return None

        date_str = str(date_str).strip()
        # Strip trailing time component
        date_str = re.sub(
            r'\s+\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM)?', '',
            date_str, flags=re.IGNORECASE,
        ).strip()

        date_patterns = [
            # ── Unambiguous formats ─────────────────────────────────────────
            # YYYY-MM-DD (already correct)
            (r'^(\d{4})-(\d{1,2})-(\d{1,2})$',
             lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
            # DD-MM-YYYY
            (r'^(\d{1,2})-(\d{1,2})-(\d{4})$',
             lambda m: f"{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"),
            # DD/MM/YY  (20XX if yy < 50, else 19XX)
            (r'^(\d{1,2})/(\d{1,2})/(\d{2})$',
             lambda m: (
                 f"20{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
                 if int(m.group(3)) < 50
                 else f"19{m.group(3)}-{m.group(2).zfill(2)}-{m.group(1).zfill(2)}"
             )),
        ]

        for pattern, formatter in date_patterns:
            m = re.match(pattern, date_str)
            if m:
                try:
                    result = formatter(m)
                    datetime.strptime(result, '%Y-%m-%d')
                    return result
                except ValueError:
                    continue

        # ── BUG-DC-1 FIX: smart ambiguous-slash pattern ──────────────────────
        slash_m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{4})$', date_str)
        if slash_m:
            a, b, yyyy = int(slash_m.group(1)), int(slash_m.group(2)), slash_m.group(3)

            def _try(year, month, day):
                """Return YYYY-MM-DD string if valid, else None."""
                try:
                    s = f"{year}-{month:02d}-{day:02d}"
                    datetime.strptime(s, '%Y-%m-%d')
                    return s
                except ValueError:
                    return None

            if a > 12:
                # a must be the day (DD/MM/YYYY)
                result = _try(yyyy, b, a)
            elif b > 12:
                # b must be the day (MM/DD/YYYY)
                result = _try(yyyy, a, b)
            else:
                # Ambiguous: Philippine convention is DD/MM/YYYY
                result = _try(yyyy, b, a) or _try(yyyy, a, b)

            if result:
                return result

        logger.warning(f"Could not parse date: {date_str}")
        return None

    def clean_data(self) -> pd.DataFrame:
        if self.df is None:
            self.load_data()
        logger.info("Starting data cleaning process...")
        cleaned_df = self.df.copy()

        if 'abc_php' in cleaned_df.columns:
            logger.info("Cleaning currency values...")
            cleaned_df['abc_php'] = cleaned_df['abc_php'].apply(self.clean_currency)

        date_columns = ['date_published', 'closing_datetime', 'last_updated']
        for col in date_columns:
            if col in cleaned_df.columns:
                logger.info(f"Cleaning date column: {col}")
                cleaned_df[col] = cleaned_df[col].apply(self.clean_date)

        for col in cleaned_df.columns:
            if 'date' in col.lower() and col not in date_columns:
                logger.info(f"Cleaning additional date column: {col}")
                cleaned_df[col] = cleaned_df[col].apply(self.clean_date)

        logger.info("Data cleaning completed!")
        return cleaned_df

    def save_cleaned_data(self, df: pd.DataFrame = None) -> str:
        if df is None:
            df = self.df
        try:
            logger.info(f"Saving cleaned data to {self.output_file}")
            df.to_csv(self.output_file, index=False)
            logger.info(f"Successfully saved {len(df)} rows to {self.output_file}")
            return self.output_file
        except Exception as e:
            logger.error(f"Error saving data: {e}")
            raise

    def generate_cleaning_report(self, original_df: pd.DataFrame,
                                  cleaned_df: pd.DataFrame) -> dict:
        report = {
            'total_rows':       len(cleaned_df),
            'total_columns':    len(cleaned_df.columns),
            'currency_cleaning': {},
            'date_cleaning':    {},
        }
        if 'abc_php' in original_df.columns:
            orig = original_df['abc_php'].notna().sum()
            cln  = cleaned_df['abc_php'].notna().sum()
            report['currency_cleaning'] = {
                'original_valid': orig,
                'cleaned_valid':  cln,
                'lost_values':    orig - cln,
            }
        for col in ['date_published', 'closing_datetime', 'last_updated']:
            if col in original_df.columns:
                orig = original_df[col].notna().sum()
                cln  = cleaned_df[col].notna().sum()
                report['date_cleaning'][col] = {
                    'original_valid': orig,
                    'cleaned_valid':  cln,
                    'lost_values':    orig - cln,
                }
        return report

    def run_full_cleaning(self) -> Tuple[pd.DataFrame, dict]:
        original_df = self.load_data()
        cleaned_df  = self.clean_data()
        report      = self.generate_cleaning_report(original_df, cleaned_df)
        self.save_cleaned_data(cleaned_df)
        return cleaned_df, report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Clean PhilGEPS CSV data")
    parser.add_argument("--input",  default="philgeps_all_148.csv")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    if not args.output:
        args.output = args.input.replace('.csv', '_cleaned.csv')

    cleaner = PhilGEPSDataCleaner(args.input, args.output)
    cleaned_df, report = cleaner.run_full_cleaning()

    print("\n" + "=" * 60)
    print("DATA CLEANING SUMMARY")
    print("=" * 60)
    print(f"Total rows processed : {report['total_rows']}")
    print(f"Total columns        : {report['total_columns']}")
    if report['currency_cleaning']:
        s = report['currency_cleaning']
        print(f"\nCurrency  — original valid: {s['original_valid']}, "
              f"cleaned valid: {s['cleaned_valid']}, lost: {s['lost_values']}")
    for col, s in report['date_cleaning'].items():
        print(f"\n{col}  — original valid: {s['original_valid']}, "
              f"cleaned valid: {s['cleaned_valid']}, lost: {s['lost_values']}")
    print(f"\nCleaned data saved to: {args.output}")
    print("=" * 60)


if __name__ == "__main__":
    main()
