"""PDF 解析服务 - PyMuPDF 图像提取"""
import hashlib
import fitz  # PyMuPDF
from PIL import Image
import io


class PDFParserService:
    """PDF 解析器 - 将页面渲染为图像"""

    def __init__(self, dpi: int = 150):
        self.dpi = dpi
        print(f"✅ PDF 解析器已初始化 (PyMuPDF, DPI={dpi})")

    async def extract_page_as_image(self, file_path: str, page_number: int) -> Image.Image:
        """提取页面为 PIL 图像"""
        doc = fitz.open(file_path)
        try:
            if not (1 <= page_number <= len(doc)):
                raise ValueError(f"页码超出范围: {page_number} (总页数: {len(doc)})")

            page = doc[page_number - 1]  # 0-based 索引
            zoom = self.dpi / 72  # 72 DPI 默认值
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            img_data = pix.tobytes("png")
            return Image.open(io.BytesIO(img_data))
        finally:
            doc.close()

    async def parse_single_page(self, file_path: str, page_number: int) -> Image.Image:
        """解析单个页面（返回图像）"""
        return await self.extract_page_as_image(file_path, page_number)

    def _generate_pdf_id(self, file_path: str) -> str:
        """生成 PDF 唯一 ID (SHA256)"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        return sha256.hexdigest()[:16]

    def get_page_count(self, file_path: str) -> int:
        """获取总页数"""
        doc = fitz.open(file_path)
        count = len(doc)
        doc.close()
        return count


# 全局单例
pdf_parser = PDFParserService()
