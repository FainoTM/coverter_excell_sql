import { useRef, useState } from 'react'
import axios from 'axios'

function UploadForm() {
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [previewText, setPreviewText] = useState('-- O preview do arquivo aparecerá aqui.')
  const [fileMeta, setFileMeta] = useState(null)

  const buildLocalPreview = async (selectedFile) => {
    if (!selectedFile) {
      setPreviewText('-- O preview do arquivo aparecerá aqui.')
      setFileMeta(null)
      return
    }

    const extension = selectedFile.name.split('.').pop()?.toLowerCase() || ''

    setFileMeta({
      name: selectedFile.name,
      size: `${(selectedFile.size / 1024).toFixed(1)} KB`,
      type: extension.toUpperCase(),
    })

    if (extension === 'csv') {
      try {
        const text = await selectedFile.text()
        const lines = text.split(/\r?\n/).slice(0, 8).join('\n')
        setPreviewText(lines || '-- CSV vazio.')
      } catch {
        setPreviewText('-- Não foi possível ler o CSV localmente.')
      }
      return
    }

    if (extension === 'xlsx' || extension === 'xls') {
      setPreviewText(
`-- Arquivo Excel selecionado
-- Nome: ${selectedFile.name}
-- Tipo: ${extension.toUpperCase()}
-- Tamanho: ${(selectedFile.size / 1024).toFixed(1)} KB

-- O arquivo será enviado ao backend para conversão em SQL.`
      )
      return
    }

    if (extension === 'zip') {
      setPreviewText(
`-- Arquivo ZIP selecionado
-- Nome: ${selectedFile.name}

-- Preview local não disponível para ZIP.
-- O conteúdo será processado pelo backend.`
      )
      return
    }

    setPreviewText('-- Formato não suportado para preview.')
  }

  const handleSelectedFile = async (selectedFile) => {
    setFile(selectedFile || null)
    setError('')
    setSuccess('')
    await buildLocalPreview(selectedFile)
  }

  const handleChange = async (e) => {
    const selectedFile = e.target.files?.[0]
    await handleSelectedFile(selectedFile)
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    setDragActive(true)
  }

  const handleDragLeave = (e) => {
    e.preventDefault()
    setDragActive(false)
  }

  const handleDrop = async (e) => {
    e.preventDefault()
    setDragActive(false)

    const droppedFile = e.dataTransfer.files?.[0]
    await handleSelectedFile(droppedFile)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    if (!file) {
      setError('Selecione ou arraste um arquivo antes de enviar.')
      return
    }

    const formData = new FormData()
    formData.append('file', file)

    try {
      setLoading(true)
      setError('')
      setSuccess('')

      const response = await axios.post(
        'http://127.0.0.1:8000/api/upload-file/',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
          responseType: 'blob',
        }
      )

      const blob = new Blob([response.data], { type: 'application/zip' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'sql_gerado.zip'
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)

      setSuccess('Arquivo processado com sucesso. O download foi iniciado.')
    } catch (err) {
      let message = 'Erro ao enviar o arquivo.'

      if (err.response?.data) {
        try {
          const text = await err.response.data.text()
          const json = JSON.parse(text)
          message = json.error || message
        } catch {
          message = 'Falha ao processar o retorno do servidor.'
        }
      }

      setError(message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="converter-page">
      <div className="converter-shell">
        <header className="topbar">
          <div>
            <p className="topbar-kicker">Converter Dashboard</p>
            <h1>Excel to SQL Converter</h1>
            <p className="topbar-subtitle">
              Envie arquivos CSV, XLSX, XLS ou ZIP para gerar scripts SQL.
            </p>
          </div>

          <div className="topbar-badge">SQL EXPORT</div>
        </header>

        <form className="content-grid" onSubmit={handleSubmit}>
          <section
            className={`upload-card ${dragActive ? 'drag-active' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <div className="upload-icon">↑</div>
            <h2>Arraste e solte seu arquivo</h2>
            <p>Formatos aceitos: .zip, .csv, .xlsx, .xls</p>

            <input
              ref={inputRef}
              type="file"
              accept=".zip,.csv,.xlsx,.xls"
              onChange={handleChange}
              hidden
            />

            <div className="upload-actions">
              <button
                type="button"
                className="secondary-btn"
                onClick={() => inputRef.current?.click()}
              >
                Escolher arquivo
              </button>

              <button
                type="submit"
                className="primary-btn"
                disabled={loading}
              >
                {loading ? 'Processando...' : 'Converter para SQL'}
              </button>
            </div>

            {file && (
              <div className="selected-file">
                <strong>Arquivo:</strong> {file.name}
              </div>
            )}

            {success && <p className="message success">{success}</p>}
            {error && <p className="message error">{error}</p>}
          </section>

          <section className="preview-card">
            <div className="preview-header">
              <h3>Preview</h3>
              {fileMeta && (
                <div className="file-meta">
                  <span>{fileMeta.type}</span>
                  <span>{fileMeta.size}</span>
                </div>
              )}
            </div>

            <div className="preview-window">
              <div className="preview-dots">
                <span />
                <span />
                <span />
              </div>

              <pre>{previewText}</pre>
            </div>
          </section>
        </form>
      </div>
    </div>
  )
}

export default UploadForm