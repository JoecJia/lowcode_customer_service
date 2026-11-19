import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { AttachmentPayload, PendingAttachment } from '../api/chat'

const ALLOWED_IMAGE_MIME = ['image/png', 'image/jpeg', 'image/webp']
const MAX_IMAGE_SIZE = 10 * 1024 * 1024
const MAX_PDF_SIZE = 20 * 1024 * 1024
const MAX_TOTAL_SIZE = 20 * 1024 * 1024
const MAX_COUNT = 6

function makeId(): string {
  const uuid = globalThis.crypto?.randomUUID?.()
  return `att_${(uuid || `${Date.now()}${Math.random()}`).replace(/-/g, '').slice(0, 8)}`
}

function readAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

async function toPayload(item: PendingAttachment): Promise<AttachmentPayload | null> {
  if (item.status !== 'ready') return null
  if (item.kind === 'image') {
    if (!item.dataUrl) return null
    return {
      id: item.id,
      kind: 'image',
      name: item.name,
      mime: item.mime,
      size: item.size,
      data_url: item.dataUrl,
    }
  }
  const base64 = item.base64 || (item.dataUrl ? item.dataUrl.split(',')[1] : '')
  if (!base64) return null
  return {
    id: item.id,
    kind: 'pdf',
    name: item.name,
    mime: 'application/pdf',
    size: item.size,
    base64,
  }
}

export function useAttachments() {
  const attachments = ref<PendingAttachment[]>([])

  function remove(id: string) {
    const target = attachments.value.find(a => a.id === id)
    if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl)
    attachments.value = attachments.value.filter(a => a.id !== id)
  }

  function reset() {
    attachments.value.forEach(a => {
      if (a.previewUrl) URL.revokeObjectURL(a.previewUrl)
    })
    attachments.value = []
  }

  async function addFiles(files: File[]) {
    for (const file of files) {
      if (attachments.value.length >= MAX_COUNT) {
        ElMessage.warning(`最多上传 ${MAX_COUNT} 个附件`)
        break
      }

      const isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')
      const isImage = ALLOWED_IMAGE_MIME.includes(file.type)

      if (!isImage && !isPdf) {
        ElMessage.warning('仅支持 PNG/JPEG/WebP 图片或 PDF 文档')
        continue
      }
      if (isPdf && attachments.value.some(a => a.kind === 'pdf')) {
        ElMessage.warning('每次最多上传 1 个 PDF')
        continue
      }
      if (file.size > (isPdf ? MAX_PDF_SIZE : MAX_IMAGE_SIZE)) {
        ElMessage.warning(isPdf ? 'PDF 不能超过 20MB' : '图片不能超过 10MB')
        continue
      }
      if (attachments.value.reduce((sum, a) => sum + a.size, 0) + file.size > MAX_TOTAL_SIZE) {
        ElMessage.warning('附件总大小不能超过 20MB')
        continue
      }
      if (!file.name || /[\\/]|\.\./.test(file.name)) {
        ElMessage.warning('文件名包含非法字符')
        continue
      }

      const item: PendingAttachment = {
        id: makeId(),
        kind: isPdf ? 'pdf' : 'image',
        name: file.name,
        mime: isPdf ? 'application/pdf' : file.type,
        size: file.size,
        status: 'ready',
      }

      try {
        const dataUrl = await readAsDataURL(file)
        if (isImage) {
          item.previewUrl = URL.createObjectURL(file)
          item.dataUrl = dataUrl
        } else {
          item.base64 = dataUrl.split(',')[1] || ''
        }
      } catch {
        item.status = 'error'
        ElMessage.warning(`读取 ${file.name} 失败`)
      }

      attachments.value.push(item)
    }
  }

  async function getPayloads(): Promise<AttachmentPayload[]> {
    const payloads = await Promise.all(attachments.value.map(toPayload))
    return payloads.filter((p): p is AttachmentPayload => p !== null)
  }

  return { attachments, addFiles, remove, reset, getPayloads }
}
