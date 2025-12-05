'use client';

import { useRef } from 'react';
import { usePdfStore } from '@/store/pdfStore';
import { uploadPdf } from '@/lib/api';

export default function PdfUploader() {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const {
    isUploading,
    setPdfFile,
    setPdfInfo,
    setIsUploading,
    setError,
    pdfId,
    reset,
  } = usePdfStore();

  const handleFileSelect = async (
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    const file = event.target.files?.[0];
    if (!file) return;

    // 验证文件类型
    if (file.type !== 'application/pdf') {
      setError('请选择 PDF 文件');
      return;
    }

    // 验证文件大小 (50MB)
    const maxSize = 50 * 1024 * 1024;
    if (file.size > maxSize) {
      setError('文件大小不能超过 50MB');
      return;
    }

    // 重新上传时，先重置所有状态（清除旧的解释缓存等）
    reset();
    
    setPdfFile(file);
    setError(null);
    setIsUploading(true);

    try {
      const response = await uploadPdf(file);
      setPdfInfo(response.pdf_id, response.total_pages, response.filename);
      console.log('✅ PDF 上传成功:', response);
    } catch (error: any) {
      console.error('❌ 上传失败:', error);
      setError(
        error.response?.data?.detail || '上传失败,请检查网络连接和后端服务'
      );
    } finally {
      setIsUploading(false);
    }
  };

  const handleButtonClick = () => {
    // 清除 input 的值，确保选择相同文件也能触发 onChange
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
    fileInputRef.current?.click();
  };

  // 如果已上传,显示状态
  if (pdfId) {
    return (
      <div className="flex items-center gap-3 text-sm">
        <div className="flex items-center gap-2">
          <span className="text-gray-500">已加载</span>
          <button
            onClick={handleButtonClick}
            className="text-black underline hover:no-underline"
          >
            重新上传
          </button>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          onChange={handleFileSelect}
          className="hidden"
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <button
        onClick={handleButtonClick}
        disabled={isUploading}
        className="px-6 py-3 bg-black text-white font-medium hover:bg-gray-800 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors border border-black"
      >
        {isUploading ? '上传中...' : '选择 PDF 文件'}
      </button>
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf"
        onChange={handleFileSelect}
        className="hidden"
      />
    </div>
  );
}
