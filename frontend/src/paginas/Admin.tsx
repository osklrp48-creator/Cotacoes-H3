import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api, type Perfil, type Unidade, type Usuario } from '../api'
import { useSessao } from '../auth'
import { Carregando, Icone, Modal, useAvisar, useConfirmar } from '../componentes/ui'
import { fmtData, fmtInteiro, hoje } from '../formato'

/* ---------------- Unidades ---------------- */
function Unidades() {
  const avisar = useAvisar()
  const confirmar = useConfirmar()
  const [lista, setLista] = useState<Unidade[] | null>(null)
  const [nova, setNova] = useState('')
  const [editando, setEditando] = useState<Unidade | null>(null)
  const [erro, setErro] = useState('')

  const carregar = useCallback(() => api<Unidade[]>('/unidades').then(setLista).catch((e) => setErro(e.message)), [])
  useEffect(() => {
    carregar()
  }, [carregar])

  async function criar(e: FormEvent) {
    e.preventDefault()
    if (!nova.trim()) return
    try {
      await api('/unidades', { metodo: 'POST', corpo: { nome: nova.trim() } })
      setNova('')
      avisar('Unidade criada.')
      carregar()
    } catch (e) {
      avisar((e as Error).message, 'erro')
    }
  }

  async function salvar(u: Unidade) {
    try {
      await api(`/unidades/${u.id}`, { metodo: 'PUT', corpo: { nome: u.nome, ativo: u.ativo } })
      setEditando(null)
      avisar('Unidade salva.')
      carregar()
    } catch (e) {
      avisar((e as Error).message, 'erro')
    }
  }

  async function excluir(u: Unidade) {
    if (!(await confirmar({ titulo: `Excluir a unidade "${u.nome}"?`, sim: 'Excluir', nao: 'Cancelar', perigo: true }))) return
    try {
      await api(`/unidades/${u.id}`, { metodo: 'DELETE' })
      avisar('Unidade excluída.')
      carregar()
    } catch (e) {
      avisar((e as Error).message, 'erro')
    }
  }

  if (!lista) return erro ? <div className="alerta alerta-erro">{erro}</div> : <Carregando />
  return (
    <div className="cartao">
      <form className="filtros" onSubmit={criar}>
        <input placeholder="Nome da nova unidade" value={nova} onChange={(e) => setNova(e.target.value)} maxLength={120} aria-label="Nome da nova unidade" />
        <button className="btn btn-primario" disabled={!nova.trim()}>
          {Icone.mais()} Adicionar
        </button>
      </form>
      <table className="tabela responsiva">
        <thead>
          <tr>
            <th>Unidade</th>
            <th>Situação</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {lista.map((u) =>
            editando?.id === u.id ? (
              <tr key={u.id}>
                <td className="principal">
                  <input value={editando.nome} onChange={(e) => setEditando({ ...editando, nome: e.target.value })} autoFocus aria-label="Nome" />
                </td>
                <td data-rotulo="Ativa">
                  <label>
                    <input type="checkbox" style={{ width: 'auto', minHeight: 0 }} checked={editando.ativo} onChange={(e) => setEditando({ ...editando, ativo: e.target.checked })} /> Ativa
                  </label>
                </td>
                <td>
                  <div className="acoes">
                    <button className="btn" onClick={() => setEditando(null)}>
                      Cancelar
                    </button>
                    <button className="btn btn-primario" onClick={() => salvar(editando)}>
                      Salvar
                    </button>
                  </div>
                </td>
              </tr>
            ) : (
              <tr key={u.id}>
                <td className="principal">{u.nome}</td>
                <td data-rotulo="Situação">{u.ativo ? 'Ativa' : <span className="fraco">Inativa</span>}</td>
                <td>
                  <div className="acoes">
                    <button className="btn" onClick={() => setEditando(u)}>
                      {Icone.lapis(16)} Editar
                    </button>
                    <button className="btn btn-icone" title="Excluir" aria-label={`Excluir ${u.nome}`} onClick={() => excluir(u)}>
                      {Icone.lixeira()}
                    </button>
                  </div>
                </td>
              </tr>
            ),
          )}
        </tbody>
      </table>
    </div>
  )
}

/* ---------------- Usuários ---------------- */
interface FormUsuario {
  id?: number
  nome: string
  email: string
  senha: string
  perfil: Perfil
  unidade_id: string
  ativo: boolean
}

function Usuarios() {
  const avisar = useAvisar()
  const { usuario: eu } = useSessao()
  const [lista, setLista] = useState<Usuario[] | null>(null)
  const [unidades, setUnidades] = useState<Unidade[]>([])
  const [form, setForm] = useState<FormUsuario | null>(null)
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)

  const carregar = useCallback(() => api<Usuario[]>('/usuarios').then(setLista).catch((e) => avisar(e.message, 'erro')), [avisar])
  useEffect(() => {
    carregar()
    api<Unidade[]>('/unidades').then(setUnidades).catch(() => {})
  }, [carregar])

  function abrir(u?: Usuario) {
    setErro('')
    setForm(
      u
        ? { id: u.id, nome: u.nome, email: u.email, senha: '', perfil: u.perfil, unidade_id: String(u.unidade.id), ativo: u.ativo }
        : { nome: '', email: '', senha: '', perfil: 'usuario', unidade_id: String(unidades.find((x) => x.ativo)?.id ?? ''), ativo: true },
    )
  }

  async function salvar(e: FormEvent) {
    e.preventDefault()
    if (!form) return
    if (!form.nome.trim() || !form.email.trim() || !form.unidade_id) return setErro('Preencha nome, e-mail e unidade.')
    if (!form.id && form.senha.length < 8) return setErro('A senha precisa ter pelo menos 8 caracteres.')
    if (form.id && form.senha && form.senha.length < 8) return setErro('A nova senha precisa ter pelo menos 8 caracteres.')
    const corpo = {
      nome: form.nome.trim(),
      email: form.email.trim(),
      perfil: form.perfil,
      unidade_id: Number(form.unidade_id),
      ativo: form.ativo,
      ...(form.senha ? { senha: form.senha } : {}),
    }
    setSalvando(true)
    try {
      await api(form.id ? `/usuarios/${form.id}` : '/usuarios', { metodo: form.id ? 'PUT' : 'POST', corpo })
      avisar(form.id ? 'Usuário salvo.' : 'Usuário criado.')
      setForm(null)
      carregar()
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setSalvando(false)
    }
  }

  if (!lista) return <Carregando />
  return (
    <div className="cartao">
      <div className="filtros" style={{ justifyContent: 'flex-end' }}>
        <button className="btn btn-primario" onClick={() => abrir()}>
          {Icone.mais()} Novo usuário
        </button>
      </div>
      <div className="tabela-caixa">
        <table className="tabela responsiva">
          <thead>
            <tr>
              <th>Nome</th>
              <th>E-mail</th>
              <th>Unidade</th>
              <th>Perfil</th>
              <th>Situação</th>
            </tr>
          </thead>
          <tbody>
            {lista.map((u) => (
              <tr key={u.id} className="clicavel" onClick={() => abrir(u)}>
                <td className="principal">{u.nome}</td>
                <td data-rotulo="E-mail">{u.email}</td>
                <td data-rotulo="Unidade">{u.unidade.nome}</td>
                <td data-rotulo="Perfil">{u.perfil === 'admin' ? 'Admin' : 'Usuário'}</td>
                <td data-rotulo="Situação">{u.ativo ? 'Ativo' : <span className="fraco">Desativado</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {form && (
        <Modal largo aoFechar={() => setForm(null)}>
          <h2>{form.id ? 'Editar usuário' : 'Novo usuário'}</h2>
          <form onSubmit={salvar} noValidate>
            <div className="grade">
              <label className="campo">
                <span>Nome *</span>
                <input value={form.nome} onChange={(e) => setForm({ ...form, nome: e.target.value })} maxLength={120} autoFocus />
              </label>
              <label className="campo">
                <span>E-mail *</span>
                <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} autoComplete="off" />
              </label>
              <label className="campo">
                <span>{form.id ? 'Nova senha (deixe vazio para manter)' : 'Senha * (mín. 8)'}</span>
                <input type="password" value={form.senha} onChange={(e) => setForm({ ...form, senha: e.target.value })} autoComplete="new-password" />
              </label>
              <label className="campo">
                <span>Unidade *</span>
                <select value={form.unidade_id} onChange={(e) => setForm({ ...form, unidade_id: e.target.value })}>
                  <option value="">Selecione…</option>
                  {unidades.map((u) => (
                    <option key={u.id} value={u.id} disabled={!u.ativo && String(u.id) !== form.unidade_id}>
                      {u.nome}
                      {u.ativo ? '' : ' (inativa)'}
                    </option>
                  ))}
                </select>
              </label>
              <label className="campo">
                <span>Perfil</span>
                <select value={form.perfil} onChange={(e) => setForm({ ...form, perfil: e.target.value as Perfil })} disabled={form.id === eu?.id}>
                  <option value="usuario">Usuário (registra e edita valores)</option>
                  <option value="admin">Admin (gerencia unidades e usuários)</option>
                </select>
              </label>
              <label className="campo">
                <span>Situação</span>
                <select value={form.ativo ? '1' : '0'} onChange={(e) => setForm({ ...form, ativo: e.target.value === '1' })} disabled={form.id === eu?.id}>
                  <option value="1">Ativo</option>
                  <option value="0">Desativado (não consegue entrar)</option>
                </select>
              </label>
            </div>
            {erro && <div className="alerta alerta-erro">{erro}</div>}
            <div className="acoes" style={{ marginTop: 16 }}>
              <button type="button" className="btn" onClick={() => setForm(null)}>
                Cancelar
              </button>
              <button className="btn btn-primario" disabled={salvando}>
                {salvando ? 'Salvando…' : 'Salvar'}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}

/* ---------------- Uso da IA ---------------- */
interface LinhaUso {
  nome: string
  leituras: number
  falhas: number
  tokens_entrada: number
  tokens_saida: number
  custo_estimado_usd: number
}
interface ResumoUso {
  de: string
  ate: string
  provedor: 'gemini' | 'anthropic'
  modelo: string
  preco_entrada_mtok: number
  preco_saida_mtok: number
  total: LinhaUso
  por_usuario: LinhaUso[]
  por_unidade: LinhaUso[]
}

const usd = (v: number) => v.toLocaleString('pt-BR', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 4 })

function TabelaUso({ titulo, linhas }: { titulo: string; linhas: LinhaUso[] }) {
  return (
    <div className="cartao">
      <h2>{titulo}</h2>
      {linhas.length === 0 ? (
        <div className="vazio">Nenhuma leitura no período.</div>
      ) : (
        <table className="tabela responsiva">
          <thead>
            <tr>
              <th>Nome</th>
              <th className="num">Leituras</th>
              <th className="num">Falhas</th>
              <th className="num">Tokens entrada</th>
              <th className="num">Tokens saída</th>
              <th className="num">Custo estimado</th>
            </tr>
          </thead>
          <tbody>
            {linhas.map((l) => (
              <tr key={l.nome}>
                <td className="principal">{l.nome}</td>
                <td data-rotulo="Leituras" className="num">{fmtInteiro(l.leituras)}</td>
                <td data-rotulo="Falhas" className="num">{fmtInteiro(l.falhas)}</td>
                <td data-rotulo="Tokens entrada" className="num">{fmtInteiro(l.tokens_entrada)}</td>
                <td data-rotulo="Tokens saída" className="num">{fmtInteiro(l.tokens_saida)}</td>
                <td data-rotulo="Custo estimado" className="num">{usd(l.custo_estimado_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}

function UsoIA() {
  const [de, setDe] = useState(hoje().slice(0, 8) + '01')
  const [ate, setAte] = useState(hoje())
  const [dados, setDados] = useState<ResumoUso | null>(null)
  const [erro, setErro] = useState('')

  useEffect(() => {
    setErro('')
    api<ResumoUso>('/admin/uso-ia', { params: { de, ate } }).then(setDados).catch((e) => setErro(e.message))
  }, [de, ate])

  return (
    <>
      <div className="cartao">
        <div className="filtros" style={{ marginBottom: 0 }}>
          <label className="campo">
            <span>De</span>
            <input type="date" value={de} onChange={(e) => e.target.value && setDe(e.target.value)} />
          </label>
          <label className="campo">
            <span>Até</span>
            <input type="date" value={ate} onChange={(e) => e.target.value && setAte(e.target.value)} />
          </label>
        </div>
      </div>
      {erro && <div className="alerta alerta-erro">{erro}</div>}
      {!dados ? (
        !erro && <Carregando />
      ) : (
        <>
          <div className="numeros">
            <div className="cartao-valor">
              <div className="rotulo">Leituras</div>
              <div className="valor">{fmtInteiro(dados.total.leituras)}</div>
              <div className="quem">{dados.total.falhas} com falha</div>
            </div>
            <div className="cartao-valor">
              <div className="rotulo">Tokens de entrada</div>
              <div className="valor">{fmtInteiro(dados.total.tokens_entrada)}</div>
            </div>
            <div className="cartao-valor">
              <div className="rotulo">Tokens de saída</div>
              <div className="valor">{fmtInteiro(dados.total.tokens_saida)}</div>
            </div>
            <div className="cartao-valor">
              <div className="rotulo">Custo estimado</div>
              <div className="valor">{usd(dados.total.custo_estimado_usd)}</div>
              <div className="quem">
                {fmtData(dados.de)} a {fmtData(dados.ate)}
              </div>
            </div>
          </div>
          <TabelaUso titulo="Por unidade" linhas={dados.por_unidade} />
          <TabelaUso titulo="Por usuário" linhas={dados.por_usuario} />
          <p className="fraco">
            IA: {dados.provedor === 'gemini' ? 'Google Gemini' : 'Anthropic (Claude)'} · modelo {dados.modelo}. Estimativa com US$ {dados.preco_entrada_mtok} por milhão de
            tokens de entrada e US$ {dados.preco_saida_mtok} por milhão de saída (ajuste em IA_PRECO_ENTRADA_MTOK e IA_PRECO_SAIDA_MTOK).{' '}
            {dados.provedor === 'gemini'
              ? 'Na camada gratuita do Gemini o custo é zero, mas há limite de leituras por minuto e por dia.'
              : 'Confira o valor real no painel da Anthropic.'}
          </p>
        </>
      )}
    </>
  )
}

/* ---------------- Importar dados antigos ---------------- */
interface ResumoImportacao {
  simulado: boolean
  importados: number
  ja_existentes: number
  ignorados: number
  itens: number
  fornecedores: number
  avisos: string[]
}

function Importar() {
  const avisar = useAvisar()
  const confirmar = useConfirmar()
  const [unidades, setUnidades] = useState<Unidade[]>([])
  const [unidadeId, setUnidadeId] = useState('')
  const [arquivo, setArquivo] = useState<File | null>(null)
  const [resumo, setResumo] = useState<ResumoImportacao | null>(null)
  const [enviando, setEnviando] = useState(false)
  const [erro, setErro] = useState('')

  useEffect(() => {
    api<Unidade[]>('/unidades').then(setUnidades).catch(() => {})
  }, [])

  async function enviar(simular: boolean) {
    if (!arquivo || !unidadeId) return
    if (!simular) {
      const unidade = unidades.find((u) => String(u.id) === unidadeId)?.nome
      const ok = await confirmar({
        titulo: 'Importar de verdade?',
        mensagem: `Os registros serão gravados na unidade "${unidade}". Registros já importados antes são pulados.`,
        sim: 'Importar',
        nao: 'Cancelar',
      })
      if (!ok) return
    }
    const corpo = new FormData()
    corpo.append('arquivo', arquivo)
    corpo.append('unidade_id', unidadeId)
    corpo.append('simular', simular ? 'true' : 'false')
    setErro('')
    setEnviando(true)
    try {
      const r = await api<ResumoImportacao>('/admin/importar', { metodo: 'POST', corpo })
      setResumo(r)
      if (!simular) avisar(`Importação concluída: ${r.importados} registro(s).`)
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="cartao">
      <h2>Importar dados antigos (cotacoes-export.json)</h2>
      <p className="fraco" style={{ marginTop: 0 }}>
        Primeiro clique em <strong>Simular</strong> para ver o resultado sem gravar nada. Se estiver certo, clique em <strong>Importar de verdade</strong>.
        Pode repetir sem medo: registros já importados são pulados.
      </p>
      <div className="grade">
        <label className="campo">
          <span>Arquivo .json</span>
          <input
            type="file"
            accept=".json,application/json"
            onChange={(e) => {
              setArquivo(e.target.files?.[0] ?? null)
              setResumo(null)
            }}
          />
        </label>
        <label className="campo">
          <span>Unidade dos registros</span>
          <select
            value={unidadeId}
            onChange={(e) => {
              setUnidadeId(e.target.value)
              setResumo(null)
            }}
          >
            <option value="">Selecione…</option>
            {unidades.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nome}
              </option>
            ))}
          </select>
        </label>
      </div>
      {erro && <div className="alerta alerta-erro">{erro}</div>}
      <div className="acoes" style={{ justifyContent: 'flex-start', marginTop: 12 }}>
        <button className="btn" disabled={!arquivo || !unidadeId || enviando} onClick={() => enviar(true)}>
          {enviando ? 'Enviando…' : 'Simular'}
        </button>
        <button className="btn btn-primario" disabled={!arquivo || !unidadeId || enviando || !resumo?.simulado} onClick={() => enviar(false)}>
          Importar de verdade
        </button>
      </div>
      {resumo && (
        <div className={`alerta ${resumo.simulado ? 'alerta-ia' : 'alerta-ok'}`} style={{ marginTop: 14 }}>
          <strong>{resumo.simulado ? 'Simulação (nada foi gravado)' : 'Importação concluída'}</strong>
          <div>Registros {resumo.simulado ? 'que serão importados' : 'importados'}: {resumo.importados}</div>
          <div>Itens: {resumo.itens}</div>
          <div>Já importados antes (pulados): {resumo.ja_existentes}</div>
          <div>Ignorados por erro: {resumo.ignorados}</div>
          <div>Fornecedores do cadastro: {resumo.fornecedores}</div>
          {resumo.avisos.length > 0 && (
            <details style={{ marginTop: 6 }}>
              <summary>{resumo.avisos.length} aviso(s)</summary>
              <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
                {resumo.avisos.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  )
}

export default function Admin() {
  const [aba, setAba] = useState<'unidades' | 'usuarios' | 'ia' | 'importar'>('unidades')
  return (
    <>
      <div className="cabecalho">
        <h1>Administração</h1>
      </div>
      <div className="sub-abas" role="tablist">
        <button role="tab" aria-selected={aba === 'unidades'} className={aba === 'unidades' ? 'ativo' : ''} onClick={() => setAba('unidades')}>
          Unidades
        </button>
        <button role="tab" aria-selected={aba === 'usuarios'} className={aba === 'usuarios' ? 'ativo' : ''} onClick={() => setAba('usuarios')}>
          Usuários
        </button>
        <button role="tab" aria-selected={aba === 'ia'} className={aba === 'ia' ? 'ativo' : ''} onClick={() => setAba('ia')}>
          Uso da IA
        </button>
        <button role="tab" aria-selected={aba === 'importar'} className={aba === 'importar' ? 'ativo' : ''} onClick={() => setAba('importar')}>
          Importar dados
        </button>
      </div>
      {aba === 'unidades' && <Unidades />}
      {aba === 'usuarios' && <Usuarios />}
      {aba === 'ia' && <UsoIA />}
      {aba === 'importar' && <Importar />}
    </>
  )
}
