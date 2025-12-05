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
    selectedPages,
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

  // 计算显示用的总页数：如果有选择页面，使用选择的页数；否则使用总页数
  const displayTotalPages = selectedPages.length > 0 ? selectedPages.length : totalPages;

  // 用于跟踪当前页面的轮询
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  // 防止重复加载的标志
  const isLoadingRef = useRef(false);
  // 记录当前加载的页面，避免重复加载
  const currentLoadingPageRef = useRef<number | null>(null);
  // 轮询次数计数器，防止无限轮询
  const pollCountRef = useRef<number>(0);
  const MAX_POLL_COUNT = 60; // 最多轮询60次（2分钟）

  // 轮询处理进度（仅在处理中时轮询）
  useEffect(() => {
    if (!pdfId) return;
    if (processingStatus !== 'processing') return;

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
  }, [pdfId, processingStatus]);

  // 当页面切换时，加载解释
  useEffect(() => {
    if (!pdfId) return;

    // 立即清除之前的轮询
    if (pollIntervalRef.current) {
      clearInterval(pollIntervalRef.current);
      pollIntervalRef.current = null;
    }

    const loadExplanation = async () => {
      // 防止重复加载同一页面
      if (isLoadingRef.current && currentLoadingPageRef.current === currentPage) {
        return;
      }

      // 检查是否正在加载
      if (loadingPages.has(currentPage)) {
        return;
      }

      // 检查缓存 - 如果有缓存且不是临时内容，直接返回
      const cached = explanations.get(currentPage);
      if (cached && !isTemporaryContent(cached.markdown_content)) {
        // 缓存命中，直接返回
        return;
      }

      // 设置加载标志
      isLoadingRef.current = true;
      currentLoadingPageRef.current = currentPage;

      setPageLoading(currentPage, true);
      setPageError(currentPage, null);

      try {
        const explanation = await getExplanation(pdfId, currentPage);
        setExplanation(currentPage, explanation);

        // 如果返回的是临时内容，且当前页面在选中的处理列表中，启动轮询
        const isPageInSelectedList = selectedPages.length === 0 || selectedPages.includes(currentPage);

        if (isTemporaryContent(explanation.markdown_content) && isPageInSelectedList && processingStatus === 'processing') {
          // 确保之前的轮询已清除
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
          }

          // 重置轮询计数
          pollCountRef.current = 0;

          pollIntervalRef.current = setInterval(async () => {
            // 检查轮询次数限制
            pollCountRef.current += 1;
            if (pollCountRef.current > MAX_POLL_COUNT) {
              console.log('轮询次数达到上限，停止轮询');
              if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
                pollIntervalRef.current = null;
              }
              return;
            }

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
              // 轮询出错时也停止轮询
              if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
                pollIntervalRef.current = null;
              }
            }
          }, 2000); // 每 2 秒检查一次
        }
      } catch (error: any) {
        console.error('加载解释失败:', error);
        const errorMsg = error.response?.data?.detail || '加载解释失败';
        setPageError(currentPage, errorMsg);
      } finally {
        setPageLoading(currentPage, false);
        isLoadingRef.current = false;
        currentLoadingPageRef.current = null;
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
  }, [pdfId, currentPage]); // 只依赖 pdfId 和 currentPage，移除 explanations 和 loadingPages

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
      <div className="px-6 py-5 border-b border-gray-200 bg-gradient-to-r from-white to-gray-50 shadow-sm">
        {/* 进度条 */}
        <div className="mb-4">
          <div className="flex justify-between text-sm font-medium text-gray-700 mb-2">
            <span>
              处理进度: {processedPages}/{displayTotalPages} 页
              {processingStatus === 'processing' && ' (处理中...)'}
              {processingStatus === 'completed' && ' ✅'}
              {processingStatus === 'failed' && ' ❌'}
            </span>
            <span className="font-semibold">{progressPercentage}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2.5 shadow-inner">
            <div
              className={`h-2.5 rounded-full transition-all duration-300 shadow-sm ${
                processingStatus === 'completed'
                  ? 'bg-gradient-to-r from-green-500 to-green-600'
                  : processingStatus === 'failed'
                  ? 'bg-gradient-to-r from-red-500 to-red-600'
                  : 'bg-gradient-to-r from-blue-500 to-blue-600'
              }`}
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
        </div>

        {/* 下载按钮 */}
        <button
          onClick={handleDownload}
          disabled={processingStatus !== 'completed'}
          className={`w-full py-3 px-4 rounded-lg text-sm font-semibold transition-all shadow-md ${
            processingStatus === 'completed'
              ? 'bg-gradient-to-r from-gray-900 to-gray-700 text-white hover:from-gray-800 hover:to-gray-600 hover:shadow-lg transform hover:-translate-y-0.5'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed shadow-none'
          }`}
        >
          {processingStatus === 'completed' ? '📥 下载完整讲解文档' : '等待处理完成后下载...'}
        </button>
      </div>

      {/* 内容区域 - 增大padding */}
      <div className="flex-1 overflow-auto px-8 py-6">
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
          <div className="prose prose-base max-w-none">
            {/* 页码标签 */}
            <div className="mb-6">
              <span className="px-4 py-2 text-sm font-semibold border-2 border-gray-800 bg-white shadow-md rounded-md">
                第 {currentExplanation.page_number} 页
              </span>
            </div>

            {/* Markdown 内容渲染 */}
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // 自定义标题样式 - 增大字体
                h1: ({ children }) => (
                  <h1 className="text-2xl font-bold mt-8 mb-4 pb-2 border-b">{children}</h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-xl font-bold mt-6 mb-3">{children}</h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-lg font-semibold mt-5 mb-2">{children}</h3>
                ),
                // 自定义段落 - 增大字体
                p: ({ children }) => (
                  <p className="text-base text-gray-700 leading-relaxed mb-4">{children}</p>
                ),
                // 自定义列表 - 增大字体
                ul: ({ children }) => (
                  <ul className="list-disc list-inside text-base text-gray-700 mb-4 space-y-2">{children}</ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal list-inside text-base text-gray-700 mb-4 space-y-2">{children}</ol>
                ),
                // 自定义强调
                strong: ({ children }) => (
                  <strong className="font-semibold text-gray-900">{children}</strong>
                ),
                // 自定义代码块 - 增大字体
                code: ({ children, className }) => {
                  const isInline = !className;
                  return isInline ? (
                    <code className="bg-gray-100 px-1.5 py-0.5 rounded text-base">{children}</code>
                  ) : (
                    <code className="block bg-gray-100 p-4 rounded text-base overflow-x-auto">{children}</code>
                  );
                },
                // 自定义引用块 - 增大字体
                blockquote: ({ children }) => (
                  <blockquote className="border-l-4 border-gray-300 pl-4 italic text-gray-600 my-4 text-base">
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
