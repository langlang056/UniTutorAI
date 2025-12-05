'use client';

import { useEffect } from 'react';
import { usePdfStore } from '@/store/pdfStore';
import { getExplanation } from '@/lib/api';

export default function ExplanationPanel() {
  const {
    pdfId,
    currentPage,
    explanations,
    isLoadingExplanation,
    setExplanation,
    setIsLoadingExplanation,
    setError,
  } = usePdfStore();

  // 当页面切换时,加载解释
  useEffect(() => {
    if (!pdfId) return;

    // 检查缓存
    if (explanations.has(currentPage)) {
      return;
    }

    // 加载解释
    const loadExplanation = async () => {
      setIsLoadingExplanation(true);
      setError(null);

      try {
        const explanation = await getExplanation(pdfId, currentPage);
        setExplanation(currentPage, explanation);
      } catch (error: any) {
        console.error('加载解释失败:', error);
        setError(error.response?.data?.detail || '加载解释失败');
      } finally {
        setIsLoadingExplanation(false);
      }
    };

    loadExplanation();
  }, [pdfId, currentPage]);

  const currentExplanation = explanations.get(currentPage);

  if (!pdfId) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-400 text-center px-4">
          上传 PDF 后,这里将显示 AI 生成的解释
        </p>
      </div>
    );
  }

  if (isLoadingExplanation) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin h-8 w-8 border-2 border-black border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-500">正在生成解释...</p>
        </div>
      </div>
    );
  }

  if (!currentExplanation) {
    return (
      <div className="flex items-center justify-center h-full">
        <p className="text-gray-400">暂无解释</p>
      </div>
    );
  }

  // 检查内容是否与摘要重复
  const isContentDuplicate =
    currentExplanation.content.key_points.length === 1 &&
    currentExplanation.content.key_points[0].explanation ===
      currentExplanation.content.summary;

  return (
    <div className="h-full overflow-auto p-6">
      {/* 页面类型标签 */}
      <div className="mb-4">
        <span className="px-3 py-1 text-xs border border-black bg-white">
          页面 {currentExplanation.page_number} · {currentExplanation.page_type}
        </span>
      </div>

      {/* 摘要 */}
      {currentExplanation.content.summary &&
       currentExplanation.content.summary.trim() && (
        <div className="mb-6">
          <h3 className="text-base font-bold mb-3 pb-2 border-b border-gray-200">
            📝 摘要
          </h3>
          <div className="p-4 bg-gray-50 border-l-4 border-black">
            <p className="text-sm text-gray-800 leading-relaxed whitespace-pre-wrap">
              {currentExplanation.content.summary}
            </p>
          </div>
        </div>
      )}

      {/* 关键点 - 过滤重复内容 */}
      {!isContentDuplicate && currentExplanation.content.key_points.length > 0 && (
        <div className="mb-6">
          <h3 className="text-base font-bold mb-3 pb-2 border-b border-gray-200">
            🔑 关键概念
          </h3>
          <div className="space-y-3">
            {currentExplanation.content.key_points
              .filter(
                (point) =>
                  point.concept !== '原始文本' &&
                  point.concept !== 'AI 生成的解释'
              )
              .map((point, index) => (
                <div
                  key={index}
                  className={`p-4 border rounded-lg ${
                    point.is_important
                      ? 'border-black bg-white shadow-sm'
                      : 'border-gray-200 bg-gray-50'
                  }`}
                >
                  <h4 className="font-semibold mb-2 text-sm text-gray-900">
                    {point.concept}
                  </h4>
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
                    {point.explanation}
                  </p>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* 类比 */}
      {currentExplanation.content.analogy &&
       currentExplanation.content.analogy.trim() &&
       !currentExplanation.content.analogy.includes('[将在 Phase') && (
        <div className="mb-6">
          <h3 className="text-base font-bold mb-3 pb-2 border-b border-gray-200">
            💡 类比说明
          </h3>
          <div className="p-4 bg-blue-50 border-l-4 border-blue-500 rounded-r">
            <p className="text-sm text-gray-800 italic leading-relaxed whitespace-pre-wrap">
              {currentExplanation.content.analogy}
            </p>
          </div>
        </div>
      )}

      {/* 示例 */}
      {currentExplanation.content.example &&
       currentExplanation.content.example.trim() && (
        <div className="mb-6">
          <h3 className="text-base font-bold mb-3 pb-2 border-b border-gray-200">
            📚 示例
          </h3>
          <div className="p-4 border border-gray-200 bg-white rounded-lg">
            <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-wrap">
              {currentExplanation.content.example}
            </p>
          </div>
        </div>
      )}

      {/* 元信息 */}
      <div className="mt-8 pt-4 border-t border-gray-200 text-xs text-gray-400 space-y-1">
        <p>原始语言: {currentExplanation.original_language}</p>
      </div>
    </div>
  );
}
