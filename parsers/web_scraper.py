"""
Web Scraper: Extract data from websites using Playwright and Scrapy
"""
import os
import logging
from typing import Dict, Any, List, Callable, Optional
from pathlib import Path
import hashlib
import asyncio
import re
from urllib.parse import urlparse, urljoin

import scrapy
from scrapy.crawler import CrawlerProcess
from playwright.async_api import async_playwright
import pandas as pd

logger = logging.getLogger(__name__)


class WebScraper:
    """
    Scrape websites for customs/OSINT data:
    - Playwright for JS-rendered pages
    - Scrapy for structured crawling
    - Anti-bot measures
    - Rate limiting
    """
    
    def __init__(
        self,
        headless: bool = True,
        max_pages: int = 100,
        delay: float = 1.0,
        respect_robots: bool = True
    ):
        self.headless = headless
        self.max_pages = max_pages
        self.delay = delay
        self.respect_robots = respect_robots
        
        # User agents for rotation
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        ]
        
        logger.info(f"WebScraper initialized (headless: {headless})")
    
    async def scrape_page(
        self,
        url: str,
        wait_for_selector: Optional[str] = None,
        extract_tables: bool = True,
        extract_text: bool = True
    ) -> Dict[str, Any]:
        """
        Scrape single page with Playwright
        
        Args:
            url: Target URL
            wait_for_selector: CSS selector to wait for
            extract_tables: Extract HTML tables
            extract_text: Extract page text
        
        Returns:
            {
                "url": str,
                "title": str,
                "tables": [...],
                "text": str,
                "links": [...],
                "metadata": {...}
            }
        """
        logger.info(f"Scraping page: {url}")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            
            try:
                context = await browser.new_context(
                    user_agent=self.user_agents[0],
                    viewport={"width": 1920, "height": 1080}
                )
                
                page = await context.new_page()
                
                # Set extra HTTP headers
                await page.set_extra_http_headers({
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
                    "Accept-Encoding": "gzip, deflate, br",
                    "DNT": "1",
                    "Connection": "keep-alive",
                    "Upgrade-Insecure-Requests": "1",
                })
                
                # Navigate with timeout
                await page.goto(url, wait_until="networkidle", timeout=30000)
                
                # Wait for specific selector if provided
                if wait_for_selector:
                    await page.wait_for_selector(wait_for_selector, timeout=10000)
                
                # Add delay to be respectful
                await asyncio.sleep(self.delay)
                
                # Extract data
                title = await page.title()
                
                tables = []
                if extract_tables:
                    tables = await self._extract_tables_playwright(page)
                
                text = ""
                if extract_text:
                    text = await page.inner_text("body")
                
                links = await self._extract_links(page, url)
                
                metadata = {
                    "url": url,
                    "domain": urlparse(url).netloc,
                    "status": 200,  # Assume success if we get here
                    "response_time": None,  # Would need to measure
                    "content_type": "text/html"
                }
                
                logger.info(f"Scraped: {title[:50]}... ({len(text)} chars, {len(tables)} tables)")
                
                return {
                    "url": url,
                    "title": title,
                    "tables": tables,
                    "text": text,
                    "links": links,
                    "metadata": metadata
                }
                
            except Exception as e:
                logger.error(f"Page scraping failed: {e}")
                return {
                    "url": url,
                    "error": str(e),
                    "tables": [],
                    "text": "",
                    "links": [],
                    "metadata": {"status": "error"}
                }
            
            finally:
                await browser.close()
    
    async def _extract_tables_playwright(self, page) -> List[Dict[str, Any]]:
        """Extract tables using Playwright"""
        tables_data = await page.evaluate("""
            () => {
                const tables = [];
                const tableElements = document.querySelectorAll('table');
                
                tableElements.forEach((table, index) => {
                    const rows = [];
                    const trs = table.querySelectorAll('tr');
                    
                    trs.forEach(tr => {
                        const cells = [];
                        const tds = tr.querySelectorAll('td, th');
                        tds.forEach(td => {
                            cells.push(td.textContent.trim());
                        });
                        if (cells.length > 0) {
                            rows.push(cells);
                        }
                    });
                    
                    if (rows.length > 1) {  // Has header + data
                        tables.push({
                            table_index: index,
                            rows: rows,
                            shape: [rows.length, rows[0] ? rows[0].length : 0]
                        });
                    }
                });
                
                return tables;
            }
        """)
        
        # Convert to DataFrames
        tables = []
        for table_data in tables_data:
            try:
                rows = table_data["rows"]
                if rows:
                    df = pd.DataFrame(rows[1:], columns=rows[0] if len(rows[0]) > 0 else None)
                    tables.append({
                        "table_index": table_data["table_index"],
                        "dataframe": df,
                        "shape": table_data["shape"],
                        "columns": list(df.columns) if df.columns.any() else []
                    })
            except Exception as e:
                logger.warning(f"Table conversion failed: {e}")
        
        return tables
    
    async def _extract_links(self, page, base_url: str) -> List[Dict[str, Any]]:
        """Extract all links from page"""
        links_data = await page.evaluate("""
            () => {
                const links = [];
                const anchors = document.querySelectorAll('a[href]');
                
                anchors.forEach(a => {
                    links.push({
                        text: a.textContent.trim(),
                        href: a.href,
                        title: a.title || '',
                        rel: a.rel || ''
                    });
                });
                
                return links;
            }
        """)
        
        # Process links
        processed_links = []
        for link in links_data:
            try:
                href = link["href"]
                
                # Resolve relative URLs
                if href.startswith('/'):
                    href = urljoin(base_url, href)
                
                # Skip external links or anchors
                parsed_href = urlparse(href)
                parsed_base = urlparse(base_url)
                
                if parsed_href.netloc == parsed_base.netloc and not href.startswith('#'):
                    processed_links.append({
                        "text": link["text"][:100],  # Truncate long text
                        "url": href,
                        "title": link["title"],
                        "internal": True
                    })
                    
            except Exception as e:
                logger.debug(f"Link processing failed: {e}")
        
        return processed_links[:100]  # Limit to 100 links
    
    def crawl_site(
        self,
        start_url: str,
        allowed_domains: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> Dict[str, Any]:
        """
        Crawl website using Scrapy
        
        Returns:
            {
                "pages": [...],
                "statistics": {...}
            }
        """
        logger.info(f"Crawling site: {start_url}")
        
        # Scrapy spider class
        class CustomsSpider(scrapy.Spider):
            name = 'customs_spider'
            
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.start_urls = [start_url]
                self.allowed_domains = allowed_domains or [urlparse(start_url).netloc]
                self.pages_data = []
                self.max_pages = self.settings.get('MAX_PAGES', 100)
            
            def parse(self, response):
                # Extract page data
                page_data = {
                    "url": response.url,
                    "title": response.css('title::text').get(),
                    "text": ' '.join(response.css('p::text').getall()),
                    "status": response.status,
                    "size": len(response.body)
                }
                
                self.pages_data.append(page_data)
                
                # Follow links
                if len(self.pages_data) < self.max_pages:
                    for link in response.css('a::attr(href)').getall():
                        if link.startswith('/'):
                            link = response.urljoin(link)
                        yield response.follow(link, self.parse)
            
            def closed(self, reason):
                # Save results
                self.crawler.stats.set_value('pages_crawled', len(self.pages_data))
        
        # Run crawler
        process = CrawlerProcess({
            'USER_AGENT': self.user_agents[0],
            'ROBOTSTXT_OBEY': self.respect_robots,
            'DOWNLOAD_DELAY': self.delay,
            'MAX_PAGES': self.max_pages,
            'FEEDS': {
                'items.json': {'format': 'json'},
            },
        })
        
        # Custom spider instance
        spider = CustomsSpider()
        spider.max_pages = self.max_pages
        
        process.crawl(spider)
        process.start()
        
        # Get results
        pages = getattr(spider, 'pages_data', [])
        
        statistics = {
            "total_pages": len(pages),
            "start_url": start_url,
            "allowed_domains": allowed_domains,
            "respect_robots": self.respect_robots
        }
        
        logger.info(f"Crawled {len(pages)} pages from {start_url}")
        
        return {
            "pages": pages,
            "statistics": statistics
        }
    
    def convert_to_records(
        self,
        scrape_result: Dict[str, Any],
        source_url: str
    ) -> List[Dict[str, Any]]:
        """
        Convert scraped data to standardized records format
        """
        records = []
        seen_hashes = set()
        
        # Process tables from single page scrape
        for table_info in scrape_result.get("tables", []):
            df = table_info["dataframe"]
            
            # Try to map columns (similar to PDF parser)
            column_mapping = self._guess_column_mapping(df.columns.tolist())
            
            for idx, row in df.iterrows():
                try:
                    record = {}
                    for pdf_col, std_col in column_mapping.items():
                        if pdf_col in row and pd.notna(row[pdf_col]):
                            record[std_col] = str(row[pdf_col]).strip()
                    
                    # Add metadata
                    record["source_url"] = source_url
                    record["source_type"] = "web_table"
                    record["table_index"] = table_info["table_index"]
                    
                    # Generate PK and dedupe
                    pk = f"web_{Path(urlparse(source_url).path).name}_{table_info['table_index']}_{idx}"
                    record["pk"] = pk
                    
                    op_hash = hashlib.sha256(pk.encode()).hexdigest()[:16]
                    if op_hash not in seen_hashes:
                        record["op_hash"] = op_hash
                        records.append(record)
                        seen_hashes.add(op_hash)
                        
                except Exception as e:
                    logger.warning(f"Record conversion failed: {e}")
        
        # Process crawled pages (text extraction)
        for page in scrape_result.get("pages", []):
            try:
                # Extract entities from text
                entities = self._extract_entities_from_text(page.get("text", ""))
                
                for entity in entities:
                    record = {
                        "source_url": page["url"],
                        "source_type": "web_crawl",
                        "entity_type": entity["type"],
                        "entity_text": entity["text"],
                        "confidence": entity["confidence"],
                        "page_title": page.get("title", ""),
                        "date": datetime.now().isoformat()
                    }
                    
                    # Map to standard fields
                    if entity["type"] == "edrpou":
                        record["edrpou"] = entity["text"]
                    elif entity["type"] == "company_name":
                        record["company_name"] = entity["text"]
                    elif entity["type"] == "hs_code":
                        record["hs_code"] = entity["text"]
                    
                    # Generate PK and dedupe
                    pk = f"web_crawl_{hashlib.md5(page['url'].encode()).hexdigest()[:8]}_{entity['type']}_{entity['text']}"
                    record["pk"] = pk
                    
                    op_hash = hashlib.sha256(pk.encode()).hexdigest()[:16]
                    if op_hash not in seen_hashes:
                        record["op_hash"] = op_hash
                        records.append(record)
                        seen_hashes.add(op_hash)
                        
            except Exception as e:
                logger.warning(f"Page processing failed: {e}")
        
        logger.info(f"Converted {len(records)} web records")
        return records
    
    def _guess_column_mapping(self, columns: List[str]) -> Dict[str, str]:
        """Guess column mapping (same as PDF parser)"""
        # Reuse logic from PDF parser
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
        
        mapping = {}
        cols_lower = [col.lower() for col in columns]
        
        for std_col, patterns_list in patterns.items():
            for pattern in patterns_list:
                for i, col in enumerate(cols_lower):
                    if pattern in col:
                        mapping[columns[i]] = std_col
                        break
        
        return mapping
    
    def _extract_entities_from_text(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities from text (similar to Telegram parser)"""
        entities = []
        
        # EDRPOU codes
        edrpou_matches = re.findall(r'\b\d{8,10}\b', text)
        for match in edrpou_matches:
            entities.append({
                "type": "edrpou",
                "text": match,
                "confidence": 0.9
            })
        
        # Company names
        words = re.findall(r'\b[A-ZА-Я][a-zа-я]{2,}\b', text)
        for word in words:
            if len(word) > 3:
                entities.append({
                    "type": "company_name",
                    "text": word,
                    "confidence": 0.6
                })
        
        # HS codes
        hs_matches = re.findall(r'\b\d{4,10}\b', text)
        for match in hs_matches:
            if 4 <= len(match) <= 10:
                entities.append({
                    "type": "hs_code",
                    "text": match,
                    "confidence": 0.8
                })
        
        return entities


# ========== TEST ==========
if __name__ == "__main__":
    # Mock test
    scraper = WebScraper()
    
    # Mock scrape result
    mock_result = {
        "tables": [
            {
                "table_index": 0,
                "dataframe": pd.DataFrame({
                    "Код товару": ["8418", "8501"],
                    "Дата": ["2023-01-15", "2023-02-20"],
                    "Сума": [100000, 250000]
                }),
                "columns": ["Код товару", "Дата", "Сума"]
            }
        ],
        "pages": [
            {
                "url": "https://example.com/page1",
                "title": "Test Page",
                "text": "Компанія ТОВ 'Тест' з кодом 12345678"
            }
        ]
    }
    
    records = scraper.convert_to_records(mock_result, "https://example.com")
    print(f"Converted {len(records)} records")
    print(f"Sample: {records[0] if records else 'None'}")
