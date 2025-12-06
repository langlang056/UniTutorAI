'use client';

import { useState } from 'react';
import { usePdfStore } from '@/store/pdfStore';
import { useSettingsStore } from '@/store/settingsStore';
import { startProcessing } from '@/lib/api';

export default function PageSelector() {
  const { pdfId, totalPages, selectedPages, setSelectedPages, processingStatus, setProgress } = usePdfStore();
  const { apiKey, model, isConfigured } = useSettingsStore();
  const [pageInput, setPageInput] = useState<string>('');
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!pdfId) return null;

  // 解析页码输入（支持: 1,2,3 或 1-5 或混合 1,3-5,7）
  const parsePageInput = (input: string): number[] => {
    const pages = new Set<number>();
    const parts = input.split(',').map(p => p.trim());

    for (const part of parts) {
      if (part.includes('-')) {
        // 范围: 1-5
        const [start, end] = part.split('-').map(p => parseInt(p.trim()));
        if (isNaN(start) || isNaN(end)) continue;
        for (let i = Math.min(start, end); i <= Math.max(start, end); i++) {
          if (i >= 1 && i <= totalPages) {
            pages.add(i);
          }
        }
      } else {
        // 单个页码
        const page = parseInt(part);
        if (!isNaN(page) && page >= 1 && page <= totalPages) {
          pages.add(page);
        }
      }
    }

    return Array.from(pages).sort((a, b) => a - b);
  };

  const handleApplyPages = () => {
    setError(null);
    
    if (!pageInput.trim()) {
      // 如果输入为空，选择所有页
      const allPages = Array.from({ length: totalPages }, (_, i) => i + 1);
      setSelectedPages(allPages);
      return;
    }

    const pages = parsePageInput(pageInput);
    
    if (pages.length === 0) {
      setError('请输入有效的页码');
      return;
    }

    setSelectedPages(pages);
  };

  const handleSelectAll = () => {
    const allPages = Array.from({ length: totalPages }, (_, i) => i + 1);
    setSelectedPages(allPages);
    setPageInput(`1-${totalPages}`);
  };

  const handleClear = () => {
    setSelectedPages([]);
    setPageInput('');
  };

  const handleStartProcessing = async () => {
    if (selectedPages.length === 0) {
      setError('请先选择要分析的页码');
      return;
    }

    // 检查是否配置了 API Key
    if (!isConfigured) {
      setError('请先配置 API Key（点击右上角设置按钮）');
      return;
    }

    setIsStarting(true);
    setError(null);

    try {
      // 立即更新状态为 processing，防止重复点击
      setProgress('processing', 0, 0);
      // 传递 LLM 配置
      await startProcessing(pdfId, selectedPages, {
        api_key: apiKey,
        model: model,
      });
      console.log('✅ 开始处理选定页码:', selectedPages, '使用模型:', model);
    } catch (error: any) {
      console.error('❌ 启动处理失败:', error);
      const errorMessage = error.response?.data?.detail || '启动处理失败';

      // 如果是"正在处理中"的错误，不显示（因为用户可以从进度条看到状态）
      // 只需保持当前的 processing 状态即可
      if (errorMessage.includes('正在处理中')) {
        console.log('ℹ️ PDF 正在处理中，保持当前状态');
        // 不重置状态，不显示错误
      } else {
        // 其他错误才重置状态并显示
        setProgress('pending', 0, 0);
        setError(errorMessage);
      }
    } finally {
      setIsStarting(false);
    }
  };

  const isProcessing = processingStatus === 'processing';
  const isCompleted = processingStatus === 'completed';

  return (
    <div className="border-b border-gray-200 bg-gradient-to-r from-white to-gray-50 p-4 shadow-sm">
      <div className="flex flex-col gap-3">
        {/* 页码输入和操作按钮 */}
        <div className="flex gap-2 items-center">
          <div className="flex-1">
            <input
              type="text"
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              placeholder={`输入页码 (例: 1,3,5-10)，留空表示全部 ${totalPages} 页`}
              disabled={isProcessing}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-gray-400 disabled:bg-gray-100 disabled:text-gray-500 text-sm"
            />
          </div>
          <button
            onClick={handleApplyPages}
            disabled={isProcessing}
            className="px-4 py-2 bg-gray-600 text-white rounded-md hover:bg-gray-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors text-sm font-medium"
          >
            应用
          </button>
          <button
            onClick={handleSelectAll}
            disabled={isProcessing}
            className="px-4 py-2 bg-gray-500 text-white rounded-md hover:bg-gray-600 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors text-sm font-medium"
          >
            全选
          </button>
          <button
            onClick={handleClear}
            disabled={isProcessing}
            className="px-4 py-2 bg-gray-400 text-white rounded-md hover:bg-gray-500 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors text-sm font-medium"
          >
            清空
          </button>
          <button
            onClick={handleStartProcessing}
            disabled={selectedPages.length === 0 || isStarting || isProcessing}
            className={`px-5 py-2 rounded-md text-sm font-semibold transition-all shadow-sm ${
              selectedPages.length === 0 || isStarting || isProcessing
                ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-blue-600 to-blue-700 text-white hover:from-blue-700 hover:to-blue-800 hover:shadow-md'
            }`}
          >
            {isStarting
              ? '启动中...'
              : isProcessing
              ? '分析中...'
              : isCompleted
              ? '继续分析'
              : '开始分析'}
          </button>
        </div>

        {/* 已选页码显示 */}
        {selectedPages.length > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <span className="text-gray-700 font-medium">已选择:</span>
            <span className="text-gray-600">
              共 {selectedPages.length} 页
              {selectedPages.length <= 20 && (
                <span className="ml-2 text-gray-500">
                  ({selectedPages.join(', ')})
                </span>
              )}
            </span>
          </div>
        )}

        {/* 错误提示 */}
        {error && (
          <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-md">
            ❌ {error}
          </div>
        )}
      </div>
    </div>
  );
}
