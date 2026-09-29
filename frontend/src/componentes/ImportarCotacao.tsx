import { useRef, useState, type DragEvent } from 'react'
import { api, type LeituraIA } from '../api'
import { Icone } from './ui'

const LIMITE_MB = 20
const ACEITOS = ['.pdf', '.jpg', '.jpeg', '.png', '.webp', '.docx', '.xlsx', '.xls', '.csv']

function validar(arquivo: File): string | null {
  const nome = arquivo.name.toLowerCase()
  const ext = nome.includes('.') ? nome.slice(nome.lastIndexOf('.')) : ''
  if (ext === '.doc') return 'Arquivos .doc (Word antigo) não são aceitos. Abra no Word e salve como .docx ou PDF.'
  if (!ACEITOS.includes(ext)) return 'Tipo de arquivo não aceito. Envie PDF, imagem (JPG, PNG, WebP), Word (.docx) ou planilha (.xlsx, .xls, .csv).'
  if (arquivo.size > LIMITE_MB * 1024 * 1024) return `O arquivo passa do limite de ${LIMITE_MB} MB.`
  if (arquivo.size === 0) return 'O arquivo está vazio.'
  return null
}

export default function ImportarCotacao({ aoLer }: { aoLer: (dados: LeituraIA) => void }) {
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [texto, setTexto] = useState('')
  const [mostrarTexto, setMostrarTexto] = useState(false)
  const [arrastando, setArrastando] = useState(false)
  const [lendo, setLendo] = useState(false)
  const [erro, setErro] = useState('')
  const entrada = useRef<HTMLInputElement>(null)

  function escolher(f: File | undefined | null) {
    setErro('')
    if (!f) return
    const problema = validar(f)
    if (problema) {
      setErro(problema)
      setArquivo(null)
      return
    }
    setArquivo(f)
  }

  function soltar(e: DragEvent) {
    e.preventDefault()
    setArrastando(false)
    escolher(e.dataTransfer.files?.[0])
  }

  async function ler() {
    setErro('')
    if (!arquivo && !texto.trim()) {
      setErro('Escolha um arquivo ou cole o texto da cotação.')
      return
    }
    const corpo = new FormData()
    if (arquivo) corpo.append('arquivo', arquivo)
    else corpo.append('texto', texto)
    setLendo(true)
    try {
      const dados = await api<LeituraIA>('/ia/ler-cotacao', { metodo: 'POST', corpo, limiteMs: 150_000 })
      aoLer(dados)
      setArquivo(null)
      setTexto('')
      if (entrada.current) entrada.current.value = ''
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setLendo(false)
    }
  }

  return (
    <section className="importar" aria-label="Importar cotação">
      <h2>
        {Icone.brilho()} Importar cotação
      </h2>
      <p className="fraco">A IA lê o arquivo e preenche o formulário. Nada é salvo até você conferir e clicar em Salvar.</p>

      <div
        className={`soltar${arrastando ? ' ativo' : ''}`}
        onDragOver={(e) => {
          e.preventDefault()
          setArrastando(true)
        }}
        onDragLeave={() => setArrastando(false)}
        onDrop={soltar}
      >
        {arquivo ? (
          <div>
            {Icone.arquivo()} <span className="arquivo-nome">{arquivo.name}</span>{' '}
            <span className="fraco">({(arquivo.size / 1024 / 1024).toFixed(1).replace('.', ',')} MB)</span>{' '}
            <button type="button" className="btn-link" onClick={() => setArquivo(null)} disabled={lendo}>
              remover
            </button>
          </div>
        ) : (
          <div>
            Arraste o arquivo aqui ou{' '}
            <button type="button" className="btn-link" onClick={() => entrada.current?.click()}>
              escolha um arquivo
            </button>
            <div className="fraco">PDF, JPG, PNG, WebP, Word (.docx), Excel (.xlsx, .xls) ou CSV — até {LIMITE_MB} MB</div>
          </div>
        )}
        <input ref={entrada} type="file" hidden accept={ACEITOS.join(',')} onChange={(e) => escolher(e.target.files?.[0])} />
      </div>

      {mostrarTexto && !arquivo && (
        <textarea
          rows={5}
          placeholder="Cole aqui o texto da cotação (ex.: mensagem de WhatsApp ou e-mail)…"
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          disabled={lendo}
          aria-label="Texto da cotação"
        />
      )}

      {erro && <div className="alerta alerta-erro">{erro}</div>}

      <div className="importar-acoes">
        <button type="button" className="btn" onClick={() => entrada.current?.click()} disabled={lendo}>
          {Icone.arquivo()} Escolher arquivo
        </button>
        {!arquivo && (
          <button type="button" className="btn" onClick={() => setMostrarTexto((v) => !v)} disabled={lendo}>
            {mostrarTexto ? 'Esconder texto' : 'Colar texto'}
          </button>
        )}
        <button type="button" className="btn btn-primario" onClick={ler} disabled={lendo || (!arquivo && !texto.trim())}>
          {lendo ? (
            <>
              <span className="girando" /> Lendo cotação…
            </>
          ) : (
            'Ler cotação'
          )}
        </button>
        {lendo && <span className="fraco">Isso costuma levar menos de um minuto (no máximo dois).</span>}
      </div>
    </section>
  )
}
