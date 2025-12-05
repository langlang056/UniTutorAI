import { create } from 'zustand';

// 新的 Markdown 格式解释
export interface PageExplanationMarkdown {
  page_number: number;
  markdown_content: string;
  summary: string;
}

// 保留旧接口以保持兼容
export interface PageExplanation {
  page_number: number;
  page_type: string;
  content: {
    summary: string;
    key_points: Array<{
      concept: string;
      explanation: string;
      is_important: boolean;
    }>;
    analogy: string;
    example: string;
  };
  original_language: string;
}

// 处理进度
export interface ProcessingProgress {
  pdf_id: string;
  total_pages: number;
  processed_pages: number;
  status: string;
  progress_percentage: number;
}

interface PdfState {
  // PDF 信息
  pdfId: string | null;
  pdfFile: File | null;
  totalPages: number;
  filename: string;

  // 当前页面
  currentPage: number;

  // 选中的页码（用于分析）
  selectedPages: number[];

  // 解释缓存（改用 Markdown 格式）
  explanations: Map<number, PageExplanationMarkdown>;

  // 处理进度
  processingStatus: string;
  processedPages: number;
  progressPercentage: number;

  // 加载状态（按页面跟踪）
  isUploading: boolean;
  loadingPages: Set<number>;

  // 错误状态（按页面跟踪）
  pageErrors: Map<number, string>;
  error: string | null;

  // Actions
  setPdfFile: (file: File) => void;
  setPdfInfo: (pdfId: string, totalPages: number, filename: string) => void;
  setCurrentPage: (page: number) => void;
  setSelectedPages: (pages: number[]) => void;
  setExplanation: (page: number, explanation: PageExplanationMarkdown) => void;
  setProgress: (status: string, processedPages: number, progressPercentage: number) => void;
  setIsUploading: (isUploading: boolean) => void;
  setPageLoading: (page: number, isLoading: boolean) => void;
  setPageError: (page: number, error: string | null) => void;
  setError: (error: string | null) => void;
  reset: () => void;
}

export const usePdfStore = create<PdfState>((set) => ({
  // 初始状态
  pdfId: null,
  pdfFile: null,
  totalPages: 0,
  filename: '',
  currentPage: 1,
  selectedPages: [],
  explanations: new Map(),
  processingStatus: 'pending',
  processedPages: 0,
  progressPercentage: 0,
  isUploading: false,
  loadingPages: new Set(),
  pageErrors: new Map(),
  error: null,

  // Actions
  setPdfFile: (file) => set({ pdfFile: file }),

  setPdfInfo: (pdfId, totalPages, filename) =>
    set({ pdfId, totalPages, filename, currentPage: 1 }),

  setCurrentPage: (page) => set({ currentPage: page }),

  setSelectedPages: (pages) => set({ selectedPages: pages }),

  setExplanation: (page, explanation) =>
    set((state) => {
      const newExplanations = new Map(state.explanations);
      newExplanations.set(page, explanation);
      return { explanations: newExplanations };
    }),

  setProgress: (status, processedPages, progressPercentage) =>
    set({ processingStatus: status, processedPages, progressPercentage }),

  setIsUploading: (isUploading) => set({ isUploading }),

  setPageLoading: (page, isLoading) =>
    set((state) => {
      const newLoadingPages = new Set(state.loadingPages);
      if (isLoading) {
        newLoadingPages.add(page);
      } else {
        newLoadingPages.delete(page);
      }
      return { loadingPages: newLoadingPages };
    }),

  setPageError: (page, error) =>
    set((state) => {
      const newPageErrors = new Map(state.pageErrors);
      if (error) {
        newPageErrors.set(page, error);
      } else {
        newPageErrors.delete(page);
      }
      return { pageErrors: newPageErrors };
    }),

  setError: (error) => set({ error }),

  reset: () =>
    set({
      pdfId: null,
      pdfFile: null,
      totalPages: 0,
      filename: '',
      currentPage: 1,
      selectedPages: [],
      explanations: new Map(),
      processingStatus: 'pending',
      processedPages: 0,
      progressPercentage: 0,
      isUploading: false,
      loadingPages: new Set(),
      pageErrors: new Map(),
      error: null,
    }),
}));
