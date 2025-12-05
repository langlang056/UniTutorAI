'use client';

import { useEffect, useCallback, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { usePdfStore } from '@/store/pdfStore';
import { getExplanation, getProgress, downloadMarkdown } from '@/lib/api';

// 判断内容是否是临时的"正在生成中"内容
const isTemporaryContent = (content: string) => {
  return content.includes('正在生成中') || 
         content.includes('正在后台处理') ||
         content.includes('⏳');
};

export default function ExplanationPanel() {
  const {
    pdfId,
    filename,
    currentPage,
    totalPages,
    explanations,
    processingStatus,
    processedPages,
    progressPercentage,
    loadingPages,
    pageErrors,
    setExplanation,
    setProgress,
    setPageLoading,
    setPageError,
  } = usePdfStore();

  // 用于跟踪当前页面的轮询
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // 轮询处理进度
  useEffect(() => {
    if (!pdfId) return;
    if (processingStatus === 'completed') return;

    const pollProgress = async () => {
      try {
        const progress = await getProgress(pdfId);
        setProgress(progress.status, progress.processed_pages, progress.progress_percentage);
      } catch (error) {
        console.error('获取进度失败:', error);
      }
    };

    // 立即获取一次
    pollProgress();

    // 每 3 秒轮询一次
    const interval = setInterval(pollProgress, 3000);

    return () => clearInterval(interval);
  }, [pdfId, processingStatus, setProgress]);

  // 当页面切换时，加载解释
  useEffect(() => {
    if (!pdfId) return;

    // 清除之前的轮询
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    const loadExplanation = async () => {
      // 检查是否正在加载
      if (loadingPages.has(currentPage)) {
        return;
      }

      // 检查缓存 - 如果有缓存且不是临时内容，直接返回
      const cached = explanations.get(currentPage);
      if (cached && !isTemporaryContent(cached.markdown_content)) {
        return;
      }

      setPageLoading(currentPage, true);
      setPageError(currentPage, null);

      try {
        const explanation = await getExplanation(pdfId, currentPage);
        setExplanation(currentPage, explanation);
        
        // 如果返回的是临时内容，启动轮询
        if (isTemporaryContent(explanation.markdown_content)) {
          pollIntervalRef.current = setInterval(async () => {
            try {
              const newExplanation = await getExplanation(pdfId, currentPage);
              setExplanation(currentPage, newExplanation);
              
              // 如果不再是临时内容，停止轮询
              if (!isTemporaryContent(newExplanation.markdown_content)) {
                if (pollIntervalRef.current) {
                  clearInterval(pollIntervalRef.current);
                  pollIntervalRef.current = null;
                }
              }
            } catch (error) {
              console.error('轮询解释失败:', error);
            }
          }, 2000); // 每 2 秒检查一次
        }
      } catch (error: any) {
        console.error('加载解释失败:', error);
        const errorMsg = error.response?.data?.detail || '加载解释失败';
        setPageError(currentPage, errorMsg);
      } finally {
        setPageLoading(currentPage, false);
      }
    };

    loadExplanation();

    // 清理函数
    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
      }
    };
  }, [pdfId, currentPage]);

  // 下载处理
  const handleDownload = useCallback(async () => {
    if (!pdfId || !filename) return;
    
    try {
      await downloadMarkdown(pdfId, filename.replace('.pdf', ''));
    } catch (error: any) {
      console.error('下载失败:', error);
      alert(error.response?.data?.detail || '下载失败');
    }
  }, [pdfId, filename]);

  const currentExplanation = explanations.get(currentPage);
  const isLoadingCurrentPage = loadingPages.has(currentPage);
  const currentPageError = pageErrors.get(currentPage);

  if (!pdfId) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-400 text-center px-4">
          上传 PDF 后,这里将显示 AI 生成的解释
        </p>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      {/* 顶部工具栏：进度和下载 */}
      <div className="p-4 border-b border-gray-200 bg-gray-50">
        {/* 进度条 */}
        <div className="mb-3">
          <div className="flex justify-between text-sm text-gray-600 mb-1">
            <span>
              处理进度: {processedPages}/{totalPages} 页
              {processingStatus === 'processing' && ' (处理中...)'}
              {processingStatus === 'completed' && ' ✅'}
              {processingStatus === 'failed' && ' ❌'}
            </span>
            <span>{progressPercentage}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${
                processingStatus === 'completed'
                  ? 'bg-green-500'
                  : processingStatus === 'failed'
                  ? 'bg-red-500'
                  : 'bg-blue-500'
              }`}
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
        </div>

        {/* 下载按钮 */}
        <button
          onClick={handleDownload}
          disabled={processingStatus !== 'completed'}
          className={`w-full py-2 px-4 rounded text-sm font-medium transition-colors ${
            processingStatus === 'completed'
              ? 'bg-black text-white hover:bg-gray-800'
              : 'bg-gray-300 text-gray-500 cursor-not-allowed'
          }`}
        >
          {processingStatus === 'completed' ? '📥 下载完整讲解文档' : '等待处理完成后下载...'}
        </button>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 overflow-auto p-6">
        {isLoadingCurrentPage ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center">
              <div className="animate-spin h-8 w-8 border-2 border-black border-t-transparent rounded-full mx-auto mb-4"></div>
              <p className="text-gray-500">正在加载解释...</p>
            </div>
          </div>
        ) : currentPageError ? (
          <div className="flex items-center justify-center h-full">
            <div className="text-center px-4">
              <p className="text-red-500 mb-2">加载失败</p>
              <p className="text-gray-600 text-sm">{currentPageError}</p>
            </div>
          </div>
        ) : currentExplanation ? (
          <div className="prose prose-sm max-w-none">
            {/* 页码标签 */}
            <div className="mb-4">
              <span className="px-3 py-1 text-xs border border-black bg-white">
                第 {currentExplanation.page_number} 页
              </span>
            </div>

            {/* Markdown 内容渲染 */}
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // 自定义标题样式
                h1: ({ children }) => (
                  <h1 className="text-xl font-bold mt-6 mb-3 pb-2 border-b">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-lg font-bold mt-5 mb-2">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-base font-semibold mt-4 mb-2">{children}</h3>
                ),
                // 自定义段落
                p: ({ children }) => (
                  <p className="text-sm text-gray-700 leading-relaxed mb-3">{children}</p>
                ),
                // 自定义列表
                ul: ({ children }) => (
                  <ul className="list-disc list-inside text-sm text-gray-700 mb-3 space-y-1">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-inside text-sm text-gray-700 mb-3 space-y-1">{children}</ol>
                ),
                // 自定义强调
                strong: ({ children }) => (
                  <strong className="font-semibold text-gray-900">{children}</strong>
                ),
                // 自定义代码块
                code: ({ children, className }) => {
                  const isInline = !className;
                  return isInline ? (
                    <code className="bg-gray-100 px-1 py-0.5 rounded text-sm">{children}</code>
                  ) : (
                    <code className="block bg-gray-100 p-3 rounded text-sm overflow-x-auto">{children}</code>
                  );
                },
                // 自定义引用块
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-gray-300 pl-4 italic text-gray-600 my-3">
                    {children}
                  </blockquote>
                ),
              }}
            >
              {currentExplanation.markdown_content}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full">
            <p className="text-gray-400">暂无解释</p>
          </div>
        )}
      </div>
    </div>
  );
}
