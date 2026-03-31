import { useRef, useState } from 'react'
import axios from 'axios'

function UploadForm() {
  const inputRef = useRef(null)
  const [file, setFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [previewLoading, setPreviewLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [previewText, setPreviewText] = useState('-- O preview do SQL aparecerá aqui.')

  const fetchPreview = async (selectedFile) => {
    if (!selectedFile) {
      setPreviewText('-- O preview do SQL aparecerá aqui.')
      return
    }

    const formData = new FormData()
    formData.append('file', selectedFile)

    try {
      setPreviewLoading(true)
      setError('')

      const response = await axios.post(
        'http://127.0.0.1:8000/api/preview-file/',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
          },
        }
      )

      const preview = response.data.preview || '-- Nenhum preview disponível.'
      setPreviewText(preview)
    } catch (err) {
      let message = '-- Não foi possível gerar preview.'

      if (err.response?.data?.error) {
        message = `-- ${err.response.data.error}`
      }

      setPreviewText(message)
    } finally {
      setPreviewLoading(false)
    }
  }

  const handleSelectedFile = async (selectedFile) => {
    setFile(selectedFile || null)
    setError('')
    setSuccess('')
    await fetchPreview(selectedFile)
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
              <h3>Preview do SQL</h3>
              {previewLoading && <span className="preview-loading">Gerando preview...</span>}
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