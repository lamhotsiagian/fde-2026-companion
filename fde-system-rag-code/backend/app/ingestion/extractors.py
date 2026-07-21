import abc
import csv
from pathlib import Path
from loguru import logger
import pypdf
import docx2txt
import markdown
from bs4 import BeautifulSoup
import openpyxl

class BaseExtractor(abc.ABC):
    @abc.abstractmethod
    async def extract(self, file_path: Path) -> str:
        """Extract text from the given file path."""
        pass

class PDFExtractor(BaseExtractor):
    async def extract(self, file_path: Path) -> str:
        logger.info(f"Extracting PDF: {file_path}")
        text = ""
        try:
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.error(f"Error extracting PDF {file_path}: {e}")
        return text

class DOCXExtractor(BaseExtractor):
    async def extract(self, file_path: Path) -> str:
        logger.info(f"Extracting DOCX: {file_path}")
        try:
            text = docx2txt.process(str(file_path))
            return text if text else ""
        except Exception as e:
            logger.error(f"Error extracting DOCX {file_path}: {e}")
            return ""

class TXTExtractor(BaseExtractor):
    async def extract(self, file_path: Path) -> str:
        logger.info(f"Extracting TXT: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error extracting TXT {file_path}: {e}")
            return ""

class MarkdownExtractor(BaseExtractor):
    async def extract(self, file_path: Path) -> str:
        logger.info(f"Extracting Markdown: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                md_text = f.read()
            html = markdown.markdown(md_text)
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text()
        except Exception as e:
            logger.error(f"Error extracting Markdown {file_path}: {e}")
            return ""

class HTMLExtractor(BaseExtractor):
    async def extract(self, file_path: Path) -> str:
        logger.info(f"Extracting HTML: {file_path}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                soup = BeautifulSoup(f, "html.parser")
                return soup.get_text()
        except Exception as e:
            logger.error(f"Error extracting HTML {file_path}: {e}")
            return ""

class CSVExtractor(BaseExtractor):
    async def extract(self, file_path: Path) -> str:
        logger.info(f"Extracting CSV: {file_path}")
        text = ""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                reader = csv.reader(f)
                for row in reader:
                    text += " ".join(row) + "\n"
        except Exception as e:
            logger.error(f"Error extracting CSV {file_path}: {e}")
        return text

class ExcelExtractor(BaseExtractor):
    async def extract(self, file_path: Path) -> str:
        logger.info(f"Extracting Excel: {file_path}")
        text = ""
        try:
            wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
            for sheet in wb:
                for row in sheet.iter_rows(values_only=True):
                    row_text = [str(cell) for cell in row if cell is not None]
                    text += " ".join(row_text) + "\n"
            wb.close()
        except Exception as e:
            logger.error(f"Error extracting Excel {file_path}: {e}")
        return text

def get_extractor(file_path: Path) -> BaseExtractor:
    """Factory function to get the appropriate extractor based on file extension."""
    ext = file_path.suffix.lower()
    if ext == ".pdf":
        return PDFExtractor()
    elif ext == ".docx":
        return DOCXExtractor()
    elif ext == ".txt":
        return TXTExtractor()
    elif ext == ".md":
        return MarkdownExtractor()
    elif ext in [".html", ".htm"]:
        return HTMLExtractor()
    elif ext == ".csv":
        return CSVExtractor()
    elif ext in [".xlsx", ".xls"]:
        return ExcelExtractor()
    else:
        raise ValueError(f"Unsupported file extension: {ext}")
