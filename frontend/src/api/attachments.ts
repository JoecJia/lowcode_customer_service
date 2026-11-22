import { authFetch } from './auth'

/** 读取带鉴权的附件内容，用于历史消息附件卡片预览/下载。 */
export async function getAttachmentContent(
  messageId: number,
  attachmentId: string,
): Promise<Blob> {
  const resp = await authFetch(
    `/api/messages/${messageId}/attachments/${encodeURIComponent(attachmentId)}/content`,
  )
  if (!resp.ok) {
    let detail = '附件读取失败'
    try {
      const data = await resp.json()
      detail = data.detail || detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
  return await resp.blob()
}
