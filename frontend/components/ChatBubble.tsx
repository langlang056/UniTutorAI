'use client';

import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatStore, ChatMessage } from '@/store/chatStore';
import { usePdfStore } from '@/store/pdfStore';
import { useSettingsStore } from '@/store/settingsStore';

export default function ChatBubble() {
  const {
    messages,
    isOpen,
    isLoading,
    currentPageContext,
    addMessage,
    updateMessage,
    setIsOpen,
    setIsLoading,
    clearMessages,
    setCurrentPageContext,
  } = useChatStore();

  const { pdfId, currentPage, explanations } = usePdfStore();
  const { apiKey, model, isConfigured } = useSettingsStore();

  const [inputValue, setInputValue] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // 当页面切换时，更新上下文并清空聊天
  useEffect(() => {
    if (currentPage !== currentPageContext) {
      setCurrentPageContext(currentPage);
    }
  }, [currentPage, currentPageContext, setCurrentPageContext]);

  // 自动滚动到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // 聊天框打开时聚焦输入框
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // 获取当前页面的解释内容作为上下文
  const getCurrentContext = () => {
    const explanation = explanations.get(currentPage);
    return explanation?.markdown_content || '';
  };

  // 发送消息
  const handleSend = async () => {
    if (!inputValue.trim() || isLoading || !pdfId) return;

    if (!isConfigured) {
      addMessage({
        role: 'assistant',
        content: '请先配置 API Key（点击右上角设置按钮）',
      });
      return;
    }

    // 验证 pdfId 是否有效
    if (!pdfId || pdfId === 'undefined' || pdfId === 'null') {
      addMessage({
        role: 'assistant',
        content: '请先上传 PDF 文件',
      });
      return;
    }

    const userMessage = inputValue.trim();
    setInputValue('');

    // 添加用户消息
    addMessage({ role: 'user', content: userMessage });

    // 添加 AI 消息占位符
    const assistantMsgId = addMessage({
      role: 'assistant',
      content: '',
      isStreaming: true,
    });

    setIsLoading(true);

    try {
      const context = getCurrentContext();
      const history = messages.map((msg) => ({
        role: msg.role,
        content: msg.content,
      }));

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      // 确保 API URL 不为空字符串
      const baseUrl = apiUrl && apiUrl.trim() !== '' ? apiUrl : 'http://localhost:8000';
      const fullUrl = `${baseUrl}/api/chat/${pdfId}`;
      
      console.log('🔍 聊天请求详情:', {
        envApiUrl: process.env.NEXT_PUBLIC_API_URL,
        apiUrl,
        baseUrl,
        fullUrl,
        pdfId,
        currentPage,
        hasContext: !!context,
        model,
      });

      // 使用流式 API
      const response = await fetch(fullUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            question: userMessage,
            page_number: currentPage,
            context: context,
            history: history,
            llm_config: {
              api_key: apiKey,
              model: model,
            },
          }),
        }
      );

      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}`;
        try {
          const error = await response.json();
          errorMessage = error.detail || errorMessage;
        } catch {
          // 如果无法解析 JSON，使用状态文本
          errorMessage = response.statusText || errorMessage;
        }
        console.error('❌ 聊天请求失败:', {
          status: response.status,
          statusText: response.statusText,
          url: fullUrl,
          errorMessage,
        });
        throw new Error(errorMessage);
      }

      // 处理流式响应
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let fullContent = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split('\n');

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              if (data === '[DONE]') {
                updateMessage(assistantMsgId, fullContent, false);
              } else {
                try {
                  const parsed = JSON.parse(data);
                  if (parsed.content) {
                    fullContent += parsed.content;
                    updateMessage(assistantMsgId, fullContent, true);
                  }
                } catch {
                  // 忽略解析错误
                }
              }
            }
          }
        }
      }

      updateMessage(assistantMsgId, fullContent, false);
    } catch (error: any) {
      console.error('聊天请求失败:', error);
      updateMessage(
        assistantMsgId,
        `抱歉，发生错误：${error.message || '请稍后重试'}`,
        false
      );
    } finally {
      setIsLoading(false);
    }
  };

  // 处理键盘事件
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  if (!pdfId) return null;

  return (
    <>
      {/* 悬浮球 */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={`fixed bottom-6 right-6 w-14 h-14 rounded-full shadow-lg transition-all duration-300 z-50 flex items-center justify-center ${
          isOpen
            ? 'bg-gray-700 hover:bg-gray-800'
            : 'bg-gradient-to-r from-blue-600 to-blue-700 hover:from-blue-700 hover:to-blue-800'
        }`}
      >
        {isOpen ? (
          <svg
            className="w-6 h-6 text-white"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        ) : (
          <svg
            className="w-6 h-6 text-white"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
            />
          </svg>
        )}
      </button>

      {/* 聊天面板 */}
      <div
        className={`fixed bottom-24 right-6 w-[480px] bg-white rounded-xl shadow-2xl transition-all duration-300 z-40 flex flex-col overflow-hidden ${
          isOpen
            ? 'opacity-100 translate-y-0 pointer-events-auto'
            : 'opacity-0 translate-y-4 pointer-events-none'
        }`}
        style={{ height: '600px' }}
      >
        {/* 头部 */}
        <div className="px-4 py-3 bg-gradient-to-r from-blue-600 to-blue-700 text-white flex-shrink-0">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold">AI 助手</h3>
              <p className="text-xs text-blue-100">
                正在针对第 {currentPage} 页提问
              </p>
            </div>
            <button
              onClick={clearMessages}
              className="text-xs px-2 py-1 bg-blue-500 hover:bg-blue-400 rounded transition-colors"
              title="清空对话"
            >
              清空
            </button>
          </div>
        </div>

        {/* 消息列表 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
          {messages.length === 0 ? (
            <div className="text-center text-gray-400 text-sm mt-8">
              <p>👋 有什么不懂的可以问我</p>
              <p className="mt-2 text-xs">
                我会基于当前页面的内容来回答你
              </p>
            </div>
          ) : (
            messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* 输入区域 */}
        <div className="p-3 border-t border-gray-200 bg-white flex-shrink-0">
          <div className="flex gap-2">
            <textarea
              ref={inputRef}
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的问题..."
              disabled={isLoading}
              className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none text-sm disabled:bg-gray-100"
              rows={2}
            />
            <button
              onClick={handleSend}
              disabled={!inputValue.trim() || isLoading}
              className={`px-4 rounded-lg font-medium transition-all ${
                !inputValue.trim() || isLoading
                  ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                  : 'bg-blue-600 text-white hover:bg-blue-700'
              }`}
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

// 消息气泡组件
function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === 'user';

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[85%] rounded-xl px-4 py-2 ${
          isUser
            ? 'bg-blue-600 text-white'
            : 'bg-white border border-gray-200 shadow-sm'
        }`}
      >
        {isUser ? (
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="max-w-none text-[13px]">
            {message.content ? (
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                components={{
                  p: ({ children }) => (
                    <p className="text-gray-800 mb-2 last:mb-0 leading-relaxed">
                      {children}
                    </p>
                  ),
                  ul: ({ children }) => (
                    <ul className="list-disc list-inside text-gray-800 mb-2 space-y-1">
                      {children}
                    </ul>
                  ),
                  ol: ({ children }) => (
                    <ol className="list-decimal list-inside text-gray-800 mb-2 space-y-1">
                      {children}
                    </ol>
                  ),
                  li: ({ children }) => (
                    <li className="text-gray-800">
                      {children}
                    </li>
                  ),
                  strong: ({ children }) => (
                    <strong className="font-semibold text-gray-900">
                      {children}
                    </strong>
                  ),
                  em: ({ children }) => (
                    <em className="italic">
                      {children}
                    </em>
                  ),
                  h1: ({ children }) => (
                    <h1 className="text-base font-bold text-gray-900 mb-2 mt-3">
                      {children}
                    </h1>
                  ),
                  h2: ({ children }) => (
                    <h2 className="text-[14px] font-bold text-gray-900 mb-2 mt-2">
                      {children}
                    </h2>
                  ),
                  h3: ({ children }) => (
                    <h3 className="text-[13px] font-semibold text-gray-900 mb-1 mt-2">
                      {children}
                    </h3>
                  ),
                  code: ({ children, className }) => {
                    const isInline = !className;
                    return isInline ? (
                      <code className="bg-blue-50 text-blue-800 px-1.5 py-0.5 rounded font-mono text-[12px]">
                        {children}
                      </code>
                    ) : (
                      <code className="block bg-gray-50 text-gray-800 p-3 rounded overflow-x-auto font-mono text-[12px] border border-gray-200">
                        {children}
                      </code>
                    );
                  },
                }}
              >
                {message.content}
              </ReactMarkdown>
            ) : (
              <div className="flex items-center gap-2 text-gray-400">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <div
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: '0.1s' }}
                />
                <div
                  className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                  style={{ animationDelay: '0.2s' }}
                />
              </div>
            )}
            {message.isStreaming && message.content && (
              <span className="inline-block w-2 h-4 bg-gray-400 animate-pulse ml-1" />
            )}
          </div>
        )}
      </div>
    </div>
  );
}
