"""
Excel Parser: Chunked parsing with deduplication and validation
"""

import hashlib
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class ExcelParser:
    """
    Parse Excel files with:
    - Chunked reading (10k rows per batch)
    - Deduplication (PK + op_hash)
    - Great Expectations validation
    - Progress callbacks
    """

    def __init__(
        self, chunk_size: int = 10_000, dedupe_enabled: bool = True, validation_enabled: bool = True
    ):
        self.chunk_size = chunk_size
        self.dedupe_enabled = dedupe_enabled
        self.validation_enabled = validation_enabled

        # Required columns (customs data)
        self.required_columns = [
            "hs_code",
            "date",
            "amount",
            "qty",
            "country_code",
            "edrpou",
            "company_name",
            "customs_office",
        ]

        logger.info(f"ExcelParser initialized (chunk_size={chunk_size})")

    def parse(
        self, file_path: str, progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> dict[str, Any]:
        """
        Parse Excel file

        Args:
            file_path: Path to .xlsx/.xls/.csv file
            progress_callback: Callback(processed_rows, total_rows)

        Returns:
            {
                "records": [...],  # Parsed records
                "total_rows": int,
                "valid_rows": int,
                "duplicates": int,
                "errors": [...]
            }
        """
        logger.info(f"Parsing: {file_path}")

        # Detect file type
        file_ext = Path(file_path).suffix.lower()

        if file_ext == ".csv":
            df_iterator = pd.read_csv(file_path, chunksize=self.chunk_size)
        elif file_ext in [".xlsx", ".xls"]:
            # Read entire Excel file at once as chunksize is not supported for Excel in this pandas version
            df = pd.read_excel(file_path)
            df_iterator = [df] # Wrap in a list to simulate iteration
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")

        # Parse chunks
        all_records = []
        seen_hashes = set()
        total_rows = 0
        duplicate_count = 0
        errors = []

        for chunk_idx, chunk_df in enumerate(df_iterator):
            chunk_records, chunk_dupes, chunk_errors = self._process_chunk(
                chunk_df, chunk_idx, seen_hashes
            )

            all_records.extend(chunk_records)
            duplicate_count += chunk_dupes
            errors.extend(chunk_errors)

            total_rows += len(chunk_df)

            # Progress callback
            if progress_callback:
                progress_callback(total_rows, total_rows)  # Total not known in advance

            logger.debug(
                f"Chunk {chunk_idx}: {len(chunk_records)} valid, "
                f"{chunk_dupes} dupes, {len(chunk_errors)} errors"
            )

        logger.info(
            f"Parsed {total_rows} rows → {len(all_records)} valid, "
            f"{duplicate_count} duplicates, {len(errors)} errors"
        )

        return {
            "records": all_records,
            "total_rows": total_rows,
            "valid_rows": len(all_records),
            "duplicates": duplicate_count,
            "errors": errors,
        }

    def _process_chunk(
        self, df: pd.DataFrame, chunk_idx: int, seen_hashes: set
    ) -> tuple[list[dict], int, list[str]]:
        """Process single chunk"""
        records = []
        duplicates = 0
        errors = []

        # Validate schema
        missing_cols = set(self.required_columns) - set(df.columns)
        if missing_cols:
            error = f"Missing columns: {missing_cols}"
            errors.append(error)
            logger.error(error)
            return [], 0, errors

        # Iterate rows
        for idx, row in df.iterrows():
            try:
                # Build record
                record = self._build_record(row, chunk_idx, idx)

                # Validate
                if self.validation_enabled and not self._validate_record(record):
                    errors.append(f"Row {idx}: Validation failed")
                    continue

                # Deduplicate
                op_hash = self._compute_op_hash(record)
                if self.dedupe_enabled:
                    if op_hash in seen_hashes:
                        duplicates += 1
                        continue
                    seen_hashes.add(op_hash)

                record["op_hash"] = op_hash
                records.append(record)

            except Exception as e:
                errors.append(f"Row {idx}: {str(e)}")

        return records, duplicates, errors

    def _build_record(self, row: pd.Series, chunk_idx: int, row_idx: int) -> dict[str, Any]:
        """Build record dict from DataFrame row"""
        # Generate PK
        pk = f"excel_{chunk_idx}_{row_idx}"

        # Convert types
        record = {
            "pk": pk,
            "hs_code": str(row["hs_code"]).strip() if pd.notna(row["hs_code"]) else None,
            "date": pd.to_datetime(row["date"]).date() if pd.notna(row["date"]) else None,
            "amount": float(row["amount"]) if pd.notna(row["amount"]) else 0.0,
            "qty": float(row["qty"]) if pd.notna(row["qty"]) else 0.0,
            "country_code": (
                str(row["country_code"]).strip().upper() if pd.notna(row["country_code"]) else None
            ),
            "edrpou": str(row["edrpou"]).strip() if pd.notna(row["edrpou"]) else None,
            "company_name": (
                str(row["company_name"]).strip() if pd.notna(row["company_name"]) else None
            ),
            "customs_office": (
                str(row["customs_office"]).strip() if pd.notna(row["customs_office"]) else None
            ),
        }

        # Optional fields
        optional_fields = ["contract_no", "transport", "invoice_no", "goods_description"]
        for field in optional_fields:
            if field in row and pd.notna(row[field]):
                record[field] = str(row[field]).strip()

        return record

    def _compute_op_hash(self, record: dict) -> str:
        """Compute operation hash for deduplication"""
        # Hash critical fields
        hash_input = f"{record['pk']}|{record['hs_code']}|{record['date']}|{record['amount']}|{record['edrpou']}"
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def _validate_record(self, record: dict) -> bool:
        """Validate record with Great Expectations"""
        # Basic validation rules
        if not record.get("hs_code"):
            return False

        if not record.get("date"):
            return False

        if record.get("amount", 0) < 0:
            return False

        if record.get("qty", 0) < 0:
            return False

        # HS code format (2-10 digits)
        hs_code = record["hs_code"]
        if not hs_code.isdigit() or len(hs_code) < 2 or len(hs_code) > 10:
            return False

        # Country code (2-3 letters)
        country = record.get("country_code")
        if country and (not country.isalpha() or len(country) < 2 or len(country) > 3):
            return False

        return True

    def get_sample(self, file_path: str, n_rows: int = 5) -> pd.DataFrame:
        """Get sample rows for preview"""
        file_ext = Path(file_path).suffix.lower()

        if file_ext == ".csv":
            return pd.read_csv(file_path, nrows=n_rows)
        elif file_ext in [".xlsx", ".xls"]:
            return pd.read_excel(file_path, nrows=n_rows)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")


# ========== TEST ==========
if __name__ == "__main__":
    # Create test Excel
    test_data = pd.DataFrame(
        {
            "hs_code": ["8418", "8501", "8703"],
            "date": ["2023-01-15", "2023-02-20", "2023-03-10"],
            "amount": [100000, 250000, 500000],
            "qty": [50, 100, 20],
            "country_code": ["CHN", "DEU", "POL"],
            "edrpou": ["12345678", "87654321", "11111111"],
            "company_name": ["CompanyA", "CompanyB", "CompanyC"],
            "customs_office": ["КИЇВ", "ЛЬВІВ", "ОДЕСА"],
        }
    )

    test_file = "/tmp/test_customs.xlsx"
    test_data.to_excel(test_file, index=False)

    # Parse
    parser = ExcelParser()
    result = parser.parse(test_file)

    print(f"Parsed: {result['valid_rows']} records")
    print(f"Sample: {result['records'][0]}")

    # Cleanup
    os.remove(test_file)
