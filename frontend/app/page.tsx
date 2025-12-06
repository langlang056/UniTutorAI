'use client';

import { useState } from 'react';
import { usePdfStore } from '@/store/pdfStore';
import { useSettingsStore } from '@/store/settingsStore';
import PdfUploader from '@/components/PdfUploader';
import PdfViewer from '@/components/PdfViewer';
import ExplanationPanel from '@/components/ExplanationPanel';
import PageSelector from '@/components/PageSelector';
import SettingsModal from '@/components/SettingsModal';

export default function Home() {
  const { error, filename, pdfId } = usePdfStore();
  const { isConfigured, model } = useSettingsStore();
  const [showSettings, setShowSettings] = useState(false);

  return (
    <div className="flex flex-col h-screen">
      {/* 设置弹窗 */}
      <SettingsModal isOpen={showSettings} onClose={() => setShowSettings(false)} />

      {/* 顶部导航栏 */}
      <header className="border-b border-gray-200 bg-gradient-to-r from-white via-gray-50 to-white shadow-sm">
        <div className="flex items-center justify-between px-6 py-4">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold bg-gradient-to-r from-gray-900 to-gray-600 bg-clip-text text-transparent">UniTutor AI</h1>
            {filename && (
              <span className="text-sm text-gray-600 font-medium">· {filename}</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            {/* API 状态指示器 */}
            <button
              onClick={() => setShowSettings(true)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium transition-all ${
                isConfigured
                  ? 'bg-green-100 text-green-700 hover:bg-green-200'
                  : 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
              }`}
            >
              <span className={`w-2 h-2 rounded-full ${isConfigured ? 'bg-green-500' : 'bg-yellow-500'}`} />
              {isConfigured ? model : '未配置 API'}
            </button>
            <PdfUploader />
          </div>
        </div>

        {/* 错误提示 */}
        {error && (
          <div className="px-6 py-3 bg-red-50 border-t border-red-200">
            <p className="text-sm text-red-600">❌ {error}</p>
          </div>
        )}
      </header>

      {/* 主内容区 - 左右分屏 */}
      <main className="flex-1 flex overflow-hidden bg-gradient-to-br from-gray-50 to-gray-100">
        {/* 左侧: PDF 查看器 - 占 55% */}
        <div className="w-[55%] border-r border-gray-200 bg-white shadow-lg flex flex-col overflow-hidden">
          {/* 页码选择器 */}
          {pdfId && <PageSelector />}
          {/* PDF 查看器 - 直接占据剩余空间 */}
          <PdfViewer />
        </div>

        {/* 右侧: 解释面板 - 占 45% */}
        <div className="w-[45%] bg-gradient-to-b from-white to-gray-50">
          <ExplanationPanel />
        </div>
      </main>

      {/* 底部状态栏 */}
      <footer className="border-t border-gray-200 bg-gradient-to-r from-gray-50 to-white px-6 py-2 shadow-inner">
        <div className="flex items-center justify-between text-xs text-gray-600">
          <span className="font-medium">智能课件讲解助手</span>
          <span className="text-gray-500">后端: https://localhost:8000</span>
        </div>
      </footer>
    </div>
  );
}
