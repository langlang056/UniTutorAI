import { create } from 'zustand';
import { persist } from 'zustand/middleware';

// 支持的模型列表
export const AVAILABLE_MODELS = [
  { id: 'gemini-2.5-flash', name: 'Gemini 2.5 Flash', description: '快速响应，适合一般使用' },
  { id: 'gemini-2.5-pro', name: 'Gemini 2.5 Pro', description: '更强能力，适合复杂内容' },
] as const;

export type ModelId = typeof AVAILABLE_MODELS[number]['id'];

interface SettingsState {
  // API 配置
  apiKey: string;
  model: ModelId;

  // 是否使用默认配置 (apiKey 为空)
  isUsingDefault: boolean;
  
  // 是否已配置 (永远为 true,允许使用默认)
  isConfigured: boolean;

  // Actions
  setApiKey: (key: string) => void;
  setModel: (model: ModelId) => void;
  clearSettings: () => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      apiKey: '',
      model: 'gemini-2.5-flash',
      isUsingDefault: true,
      isConfigured: true,  // 默认就是已配置(使用默认配置)

      setApiKey: (key) => {
        const trimmedKey = key.trim();
        set({
          apiKey: trimmedKey,
          isUsingDefault: trimmedKey.length === 0,
          isConfigured: true,  // 无论有没有 Key 都算已配置
          // 如果清空 Key,强制使用 Flash 模型
          model: trimmedKey.length === 0 ? 'gemini-2.5-flash' : undefined as any,
        });
      },

      setModel: (model) => set({ model }),

      clearSettings: () => set({
        apiKey: '',
        model: 'gemini-2.5-flash',
        isUsingDefault: true,
        isConfigured: true,  // 清除后仍然算已配置(使用默认)
      }),
    }),
    {
      name: 'unitutor-settings',
      // 只持久化这些字段
      partialize: (state) => ({
        apiKey: state.apiKey,
        model: state.model,
        isUsingDefault: state.isUsingDefault,
        isConfigured: state.isConfigured,
      }),
    }
  )
);
