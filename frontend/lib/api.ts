import axios from 'axios';

// 支持生产环境通过 Nginx 代理访问 API
// 开发环境: NEXT_PUBLIC_API_URL 未设置，使用 http://localhost:8000
// 生产环境: NEXT_PUBLIC_API_URL 设置为 http://your-ip/api 或使用默认 /api
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export interface UploadResponse {
  pdf_id: string;
  total_pages: number;
  filename: string;
  message?: string;
}

export interface PdfInfo {
  pdf_id: string;
  filename: string;
  total_pages: number;
  uploaded_at: string;
  processing_status: string;
  processed_pages: number;
}

// 新增：Markdown 格式的解释
export interface PageExplanationMarkdown {
  page_number: number;
  markdown_content: string;
  summary: string;
}

// 新增：处理进度
export interface ProcessingProgress {
  pdf_id: string;
  total_pages: number;
  processed_pages: number;
  status: string;
  progress_percentage: number;
}

// 保留旧的接口以保持兼容
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

/**
 * 上传 PDF 文件
 */
export async function uploadPdf(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post<UploadResponse>('/api/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
}

/**
 * 获取页面解释（Markdown 格式）
 */
export async function getExplanation(
  pdfId: string,
  pageNumber: number
): Promise<PageExplanationMarkdown> {
  const response = await api.get<PageExplanationMarkdown>(
    `/api/explain/${pdfId}/${pageNumber}`
  );

  return response.data;
}

/**
 * 获取处理进度
 */
export async function getProgress(pdfId: string): Promise<ProcessingProgress> {
  const response = await api.get<ProcessingProgress>(`/api/progress/${pdfId}`);
  return response.data;
}

/**
 * 启动处理指定页码
 */
export async function startProcessing(pdfId: string, pageNumbers: number[]): Promise<void> {
  await api.post(`/api/process/${pdfId}`, { page_numbers: pageNumbers });
}

/**
 * 获取 PDF 信息
 */
export async function getPdfInfo(pdfId: string): Promise<PdfInfo> {
  const response = await api.get<PdfInfo>(`/api/pdf/${pdfId}/info`);
  return response.data;
}

/**
 * 下载 Markdown 文件
 */
export async function downloadMarkdown(pdfId: string, filename: string): Promise<void> {
  const response = await api.get(`/api/download/${pdfId}`, {
    responseType: 'blob',
  });

  // 创建下载链接
  const url = window.URL.createObjectURL(new Blob([response.data]));
  const link = document.createElement('a');
  link.href = url;
  link.setAttribute('download', `${filename}_explained.md`);
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
}

/**
 * 健康检查
 */
export async function healthCheck(): Promise<boolean> {
  try {
    const response = await api.get('/');
    return response.status === 200;
  } catch {
    return false;
  }
}
