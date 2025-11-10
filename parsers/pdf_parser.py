"""
PDF Parser: Extract tables and text from PDF files
"""
import os
import logging
from typing import Dict, Any, List, Callable, Optional
from pathlib import Path
import hashlib

import pdfplumber
import pandas as pd
import numpy as np
from PIL import Image
import pytesseract

logger = logging.getLogger(__name__)


class PDFParser:
    """
    Parse PDF files with:
    - Table extraction (pdfplumber)
    - OCR fallback (Tesseract)
    - Text extraction
    - Image detection
    """
    
    def __init__(
        self,
        ocr_enabled: bool = True,
        table_detection: bool = True,
        text_extraction: bool = True
    ):
        self.ocr_enabled = ocr_enabled
        self.table_detection = table_detection
        self.text_extraction = text_extraction
        
        # Configure Tesseract for Ukrainian
        if self.ocr_enabled:
            try:
                import pytesseract
                pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"  # Adjust path as needed
            except ImportError:
                logger.warning("Tesseract not available, OCR disabled")
                self.ocr_enabled = False
        
        logger.info(f"PDFParser initialized (OCR: {self.ocr_enabled})")
    
    def parse(
        self,
        file_path: str,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Parse PDF file
        
        Returns:
            {
                "tables": [...],  # Extracted tables as DataFrames
                "text": str,      # Full text content
                "images": [...],  # Image metadata
                "metadata": {...} # PDF metadata
            }
        """
        logger.info(f"Parsing PDF: {file_path}")
        
        try:
            with pdfplumber.open(file_path) as pdf:
                total_pages = len(pdf.pages)
                
                # Extract metadata
                metadata = {
                    "total_pages": total_pages,
                    "file_size": os.path.getsize(file_path),
                    "title": pdf.metadata.get("Title", ""),
                    "author": pdf.metadata.get("Author", ""),
                    "subject": pdf.metadata.get("Subject", ""),
                    "creator": pdf.metadata.get("Creator", "")
                }
                
                # Extract tables
                tables = []
                if self.table_detection:
                    tables = self._extract_tables(pdf, progress_callback)
                
                # Extract text
                text = ""
                if self.text_extraction:
                    text = self._extract_text(pdf)
                
                # Extract images
                images = []
                if self.ocr_enabled:
                    images = self._extract_images(pdf)
                
                logger.info(
                    f"PDF parsed: {total_pages} pages, "
                    f"{len(tables)} tables, {len(images)} images, "
                    f"{len(text)} chars"
                )
                
                return {
                    "tables": tables,
                    "text": text,
                    "images": images,
                    "metadata": metadata
                }
                
        except Exception as e:
            logger.error(f"PDF parsing failed: {e}")
            return {
                "tables": [],
                "text": "",
                "images": [],
                "metadata": {"error": str(e)}
            }
    
    def _extract_tables(self, pdf, progress_callback) -> List[Dict[str, Any]]:
        """Extract tables from all pages"""
        tables = []
        
        for page_num, page in enumerate(pdf.pages):
            try:
                page_tables = page.extract_tables()
                
                for table_idx, table in enumerate(page_tables):
                    if table and len(table) > 1:  # Skip empty tables
                        # Convert to DataFrame
                        df = pd.DataFrame(table[1:], columns=table[0] if table[0] else None)
                        
                        # Clean data
                        df = df.dropna(how='all').dropna(axis=1, how='all')
                        
                        if not df.empty:
                            tables.append({
                                "page": page_num + 1,
                                "table_index": table_idx,
                                "dataframe": df,
                                "shape": df.shape,
                                "columns": list(df.columns) if df.columns.any() else []
                            })
                
                # Progress callback
                if progress_callback:
                    progress_callback(page_num + 1, len(pdf.pages))
                    
            except Exception as e:
                logger.warning(f"Table extraction failed on page {page_num + 1}: {e}")
        
        logger.info(f"Extracted {len(tables)} tables")
        return tables
    
    def _extract_text(self, pdf) -> str:
        """Extract full text from PDF"""
        text_parts = []
        
        for page in pdf.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            except Exception as e:
                logger.warning(f"Text extraction failed on page: {e}")
        
        full_text = "\n\n".join(text_parts)
        logger.info(f"Extracted {len(full_text)} characters of text")
        return full_text
    
    def _extract_images(self, pdf) -> List[Dict[str, Any]]:
        """Extract images and perform OCR"""
        images = []
        
        for page_num, page in enumerate(pdf.pages):
            try:
                page_images = page.images
                
                for img_idx, img in enumerate(page_images):
                    try:
                        # Extract image data
                        img_data = pdf.stream.get_object(img.stream)
                        
                        # OCR if enabled
                        ocr_text = ""
                        if self.ocr_enabled:
                            # Convert to PIL Image
                            pil_image = Image.open(img_data.stream)
                            
                            # OCR with Ukrainian language
                            ocr_text = pytesseract.image_to_string(
                                pil_image,
                                lang='ukr+eng'
                            )
                        
                        images.append({
                            "page": page_num + 1,
                            "image_index": img_idx,
                            "bbox": img.bbox,
                            "size": (img.width, img.height),
                            "ocr_text": ocr_text.strip(),
                            "has_text": bool(ocr_text.strip())
                        })
                        
                    except Exception as e:
                        logger.warning(f"Image processing failed: {e}")
                        
            except Exception as e:
                logger.warning(f"Image extraction failed on page {page_num + 1}: {e}")
        
        logger.info(f"Extracted {len(images)} images with OCR")
        return images
    
    def convert_to_records(
        self,
        parse_result: Dict[str, Any],
        source_file: str
    ) -> List[Dict[str, Any]]:
        """
        Convert PDF content to standardized records format
        
        This is a helper to convert PDF tables to the same format as Excel parser
        """
        records = []
        seen_hashes = set()
        
        # Process tables
        for table_info in parse_result.get("tables", []):
            df = table_info["dataframe"]
            
            # Try to map columns to customs format
            column_mapping = self._guess_column_mapping(df.columns.tolist())
            
            for idx, row in df.iterrows():
                try:
                    # Map columns
                    record = {}
                    for pdf_col, std_col in column_mapping.items():
                        if pdf_col in row and pd.notna(row[pdf_col]):
                            record[std_col] = str(row[pdf_col]).strip()
                    
                    # Add metadata
                    record["source_file"] = source_file
                    record["source_type"] = "pdf_table"
                    record["page"] = table_info["page"]
                    record["table_index"] = table_info["table_index"]
                    
                    # Generate PK and dedupe
                    pk = f"pdf_{Path(source_file).stem}_{table_info['page']}_{table_info['table_index']}_{idx}"
                    record["pk"] = pk
                    
                    op_hash = hashlib.sha256(pk.encode()).hexdigest()[:16]
                    if op_hash not in seen_hashes:
                        record["op_hash"] = op_hash
                        records.append(record)
                        seen_hashes.add(op_hash)
                        
                except Exception as e:
                    logger.warning(f"Record conversion failed: {e}")
        
        logger.info(f"Converted {len(records)} PDF records")
        return records
    
    def _guess_column_mapping(self, pdf_columns: List[str]) -> Dict[str, str]:
        """Guess mapping from PDF columns to standard customs columns"""
        mapping = {}
        
        # Common patterns
        patterns = {
            "hs_code": ["hs", "код товару", "товар", "код"],
            "date": ["дата", "date", "дата оформлення"],
            "amount": ["сума", "вартість", "amount", "ціна"],
            "qty": ["кількість", "quantity", "к-ть", "обсяг"],
            "country_code": ["країна", "country", "країна походження"],
            "edrpou": ["едрпоу", "код", "ідентифікатор"],
            "company_name": ["назва", "компанія", "імпортер", "експортер"],
            "customs_office": ["митниця", "office", "місце"]
        }
        
        pdf_cols_lower = [col.lower() for col in pdf_columns]
        
        for std_col, patterns_list in patterns.items():
            for pattern in patterns_list:
                for i, pdf_col in enumerate(pdf_cols_lower):
                    if pattern in pdf_col:
                        mapping[pdf_columns[i]] = std_col
                        break
        
        return mapping


# ========== TEST ==========
if __name__ == "__main__":
    # Create test PDF (would need pdfkit or similar in real usage)
    parser = PDFParser()
    
    # Mock result for testing
    mock_result = {
        "tables": [
            {
                "page": 1,
                "table_index": 0,
                "dataframe": pd.DataFrame({
                    "Код товару": ["8418", "8501"],
                    "Дата": ["2023-01-15", "2023-02-20"],
                    "Сума": [100000, 250000],
                    "Кількість": [50, 100],
                    "Країна": ["CHN", "DEU"],
                    "Назва компанії": ["CompanyA", "CompanyB"]
                }),
                "shape": (2, 6),
                "columns": ["Код товару", "Дата", "Сума", "Кількість", "Країна", "Назва компанії"]
            }
        ],
        "text": "Sample PDF text content...",
        "images": [],
        "metadata": {"total_pages": 1}
    }
    
    records = parser.convert_to_records(mock_result, "test.pdf")
    print(f"Converted {len(records)} records")
    print(f"Sample: {records[0] if records else 'None'}")
