'use client';

import { useState, useEffect } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import { usePdfStore } from '@/store/pdfStore';

// 配置 PDF.js worker
if (typeof window !== 'undefined') {
  pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
}

export default function PdfViewer() {
  const { pdfFile, currentPage, totalPages, setCurrentPage } = usePdfStore();
  const [numPages, setNumPages] = useState<number>(0);
  const [pageWidth, setPageWidth] = useState<number>(600);

  useEffect(() => {
    const updateWidth = () => {
      const container = document.getElementById('pdf-container');
      if (container) {
        setPageWidth(container.clientWidth - 40);
      }
    };

    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
  };

  const goToPrevPage = () => {
    if (currentPage > 1) {
      setCurrentPage(currentPage - 1);
    }
  };

  const goToNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage(currentPage + 1);
    }
  };

  if (!pdfFile) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-400">请先上传 PDF 文件</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* 工具栏 */}
      <div className="flex items-center justify-between p-4 border-b border-border">
        <div className="flex items-center gap-2">
          <button
            onClick={goToPrevPage}
            disabled={currentPage <= 1}
            className="px-3 py-1 border border-black disabled:border-gray-300 disabled:text-gray-300 hover:bg-gray-100 transition-colors"
          >
            上一页
          </button>
          <span className="text-sm">
            {currentPage} / {totalPages}
          </span>
          <button
            onClick={goToNextPage}
            disabled={currentPage >= totalPages}
            className="px-3 py-1 border border-black disabled:border-gray-300 disabled:text-gray-300 hover:bg-gray-100 transition-colors"
          >
            下一页
          </button>
        </div>
      </div>

      {/* PDF 显示区域 */}
      <div
        id="pdf-container"
        className="flex-1 overflow-auto p-4 bg-muted flex justify-center"
      >
        <Document
          file={pdfFile}
          onLoadSuccess={onDocumentLoadSuccess}
          loading={
            <div className="flex items-center justify-center p-8">
              <div className="animate-spin h-8 w-8 border-2 border-black border-t-transparent rounded-full"></div>
            </div>
          }
          error={
            <div className="p-8 text-center">
              <p className="text-red-600">PDF 加载失败</p>
            </div>
          }
        >
          <Page
            pageNumber={currentPage}
            width={pageWidth}
            renderTextLayer={false}
            renderAnnotationLayer={false}
          />
        </Document>
      </div>
    </div>
  );
}
