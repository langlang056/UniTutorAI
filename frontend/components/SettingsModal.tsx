'use client';

import { useState, useEffect } from 'react';
import { useSettingsStore, AVAILABLE_MODELS, ModelId } from '@/store/settingsStore';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function SettingsModal({ isOpen, onClose }: SettingsModalProps) {
  const { apiKey, model, setApiKey, setModel, clearSettings } = useSettingsStore();

  const [localApiKey, setLocalApiKey] = useState(apiKey);
  const [localModel, setLocalModel] = useState<ModelId>(model);
  const [showApiKey, setShowApiKey] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 同步 store 状态到本地状态
  useEffect(() => {
    setLocalApiKey(apiKey);
    setLocalModel(model);
  }, [apiKey, model, isOpen]);

  if (!isOpen) return null;
  
  // Pro 模型是否被禁用 (没有提供 API Key 时禁用)
  const isProDisabled = !localApiKey.trim();

  const handleSave = () => {
    const trimmedKey = localApiKey.trim();
    
    // 如果没有提供 Key,使用默认配置
    if (!trimmedKey) {
      setApiKey('');  // 存储空字符串,表示使用默认
      setModel('gemini-2.5-flash');  // 强制使用 Flash
      setError(null);
      onClose();
      return;
    }

    // 有 Key,验证格式
    if (!trimmedKey.startsWith('AI') && !trimmedKey.startsWith('sk-')) {
      setError('API Key 格式可能不正确，请检查');
      // 仍然允许保存，只是警告
    }

    setApiKey(trimmedKey);
    setModel(localModel);
    setError(null);
    onClose();
  };

  const handleClear = () => {
    clearSettings();
    setLocalApiKey('');
    setLocalModel('gemini-2.5-flash');
    setError(null);
  };

  const handleOverlayClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
      onClick={handleOverlayClick}
    >
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4 overflow-hidden">
        {/* 标题栏 */}
        <div className="px-6 py-4 border-b border-gray-200 bg-gradient-to-r from-gray-50 to-white">
          <h2 className="text-lg font-bold text-gray-800">API 设置</h2>
          <p className="text-sm text-gray-500 mt-1">配置 Google Gemini API</p>
        </div>

        {/* 内容区 */}
        <div className="px-6 py-4 space-y-4">
          {/* API Key 输入 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Google API Key (可选)
            </label>
            <div className="relative">
              <input
                type={showApiKey ? 'text' : 'password'}
                value={localApiKey}
                onChange={(e) => {
                  setLocalApiKey(e.target.value);
                  setError(null);
                }}
                placeholder="可选，留空使用默认配置"
                className="w-full px-3 py-2 pr-10 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              />
              <button
                type="button"
                onClick={() => setShowApiKey(!showApiKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
              >
                {showApiKey ? (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
            <div className="mt-2 space-y-1">
              <p className="text-xs text-gray-500">
                💡 不填写将使用默认配置体验 (仅支持 Gemini 2.5 Flash)
              </p>
              <p className="text-xs text-gray-500">
                获取 API Key: <a href="https://aistudio.google.com/apikey" target="_blank" rel="noopener noreferrer" className="text-blue-500 hover:underline">Google AI Studio</a>
              </p>
            </div>
          </div>

          {/* 模型选择 */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              选择模型
            </label>
            <div className="space-y-2">
              {AVAILABLE_MODELS.map((m) => {
                const isProModel = m.id === 'gemini-2.5-pro';
                const isDisabled = isProModel && isProDisabled;
                
                return (
                  <label
                    key={m.id}
                    className={`flex items-center p-3 border rounded-lg transition-all ${
                      isDisabled
                        ? 'opacity-50 cursor-not-allowed bg-gray-50'
                        : 'cursor-pointer hover:border-gray-300'
                    } ${
                      localModel === m.id && !isDisabled
                        ? 'border-blue-500 bg-blue-50'
                        : 'border-gray-200'
                    }`}
                  >
                    <input
                      type="radio"
                      name="model"
                      value={m.id}
                      checked={localModel === m.id}
                      onChange={(e) => setLocalModel(e.target.value as ModelId)}
                      disabled={isDisabled}
                      className="mr-3"
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 text-sm">{m.name}</span>
                        {isProModel && isProDisabled && (
                          <span className="text-xs text-gray-500">🔒 需要提供 API Key</span>
                        )}
                      </div>
                      <div className="text-xs text-gray-500">{m.description}</div>
                    </div>
                  </label>
                );
              })}
            </div>
          </div>

          {/* 错误提示 */}
          {error && (
            <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-md">
              {error}
            </div>
          )}
        </div>

        {/* 按钮区 */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-between">
          <button
            onClick={handleClear}
            className="px-4 py-2 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded-md transition-colors"
          >
            清除设置
          </button>
          <div className="flex gap-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-700 hover:bg-gray-100 rounded-md transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md transition-colors"
            >
              保存
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
