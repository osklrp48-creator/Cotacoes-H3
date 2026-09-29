import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api, STATUS_ROTULO, type RegistroResumo, type Status, type Unidade } from '../api'
import { Carregando, Icone, StatusSelo, useAtrasado } from '../componentes/ui'
import { fmtData, fmtInteiro } from '../formato'

const POR_PAGINA = 50

export default function Registros() {
  const navegar = useNavigate()
  const [params, setParams] = useSearchParams()
  const [busca, setBusca] = useState(params.get('busca') ?? '')
  const buscaAtrasada = useAtrasado(busca)
  const status = params.get('status') ?? ''
  const unidade = params.get('unidade') ?? ''

  const [unidades, setUnidades] = useState<Unidade[]>([])
  const [registros, setRegistros] = useState<RegistroResumo[]>([])
  const [total, setTotal] = useState(0)
  const [carregando, setCarregando] = useState(true)
  const [erro, setErro] = useState('')
  const requisicao = useRef(0)

  useEffect(() => {
    api<Unidade[]>('/unidades').then(setUnidades).catch(() => {})
  }, [])

  function mudarParam(nome: string, valor: string) {
    const novo = new URLSearchParams(params)
    if (valor) novo.set(nome, valor)
    else novo.delete(nome)
    setParams(novo, { replace: true })
  }

  useEffect(() => {
    if ((params.get('busca') ?? '') !== buscaAtrasada) mudarParam('busca', buscaAtrasada)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscaAtrasada])

  async function carregar(deslocamento = 0) {
    const minha = ++requisicao.current
    setCarregando(true)
    setErro('')
    try {
      const r = await api<{ total: number; registros: RegistroResumo[] }>('/registros', {
        params: { busca: buscaAtrasada, status, unidade_id: unidade, limite: POR_PAGINA, deslocamento },
      })
      if (minha !== requisicao.current) return // resposta de uma busca antiga
      setTotal(r.total)
      setRegistros((atual) => (deslocamento ? [...atual, ...r.registros] : r.registros))
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setCarregando(false)
    }
  }

  useEffect(() => {
    carregar()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscaAtrasada, status, unidade])

  return (
    <>
      <div className="cabecalho">
        <div>
          <h1>Registros</h1>
          <div className="sub">Histórico de valores passados por fornecedores, de todas as unidades.</div>
        </div>
        <Link to="/registros/novo" className="btn btn-primario">
          {Icone.mais()} Registrar valores
        </Link>
      </div>

      <div className="cartao">
        <div className="filtros">
          <input type="search" placeholder="Buscar por produto, fornecedor ou marca…" value={busca} onChange={(e) => setBusca(e.target.value)} aria-label="Buscar" />
          <select value={status} onChange={(e) => mudarParam('status', e.target.value)} aria-label="Status">
            <option value="">Todos os status</option>
            {(Object.keys(STATUS_ROTULO) as Status[]).map((s) => (
              <option key={s} value={s}>
                {STATUS_ROTULO[s]}
              </option>
            ))}
          </select>
          <select value={unidade} onChange={(e) => mudarParam('unidade', e.target.value)} aria-label="Unidade">
            <option value="">Todas as unidades</option>
            {unidades.map((u) => (
              <option key={u.id} value={u.id}>
                {u.nome}
              </option>
            ))}
          </select>
        </div>

        {erro && <div className="alerta alerta-erro">{erro}</div>}
        {!carregando || registros.length ? (
          <>
            <div className="fraco" style={{ marginBottom: 6 }}>
              {fmtInteiro(total)} {total === 1 ? 'registro' : 'registros'}
            </div>
            {registros.length === 0 ? (
              <div className="vazio">
                {buscaAtrasada || status || unidade ? 'Nenhum registro encontrado com esses filtros.' : 'Nenhum registro ainda. Clique em "Registrar valores" para começar.'}
              </div>
            ) : (
              <div className="tabela-caixa">
                <table className="tabela responsiva">
                  <thead>
                    <tr>
                      <th>Data</th>
                      <th>Quem passou</th>
                      <th>Unidade</th>
                      <th>Nº</th>
                      <th>Itens</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {registros.map((r) => (
                      <tr key={r.id} className="clicavel" onClick={() => navegar(`/registros/${r.id}`)}>
                        <td data-rotulo="Data" className="num" style={{ textAlign: 'left' }}>
                          {fmtData(r.data_recebimento)}
                        </td>
                        <td data-rotulo="Quem passou" className="principal">
                          <Link to={`/registros/${r.id}`} onClick={(e) => e.stopPropagation()} style={{ color: 'inherit', textDecoration: 'none' }}>
                            <span className={r.fornecedor === 'Não informado' ? 'nao-informado' : ''}>{r.fornecedor}</span>
                          </Link>
                        </td>
                        <td data-rotulo="Unidade">
                          {r.unidade}
                          <div className="fraco">por {r.usuario}</div>
                        </td>
                        <td data-rotulo="Nº">{r.numero || '—'}</td>
                        <td data-rotulo="Itens">
                          <span className="etiqueta">{r.qtd_itens}</span> {r.itens_resumo}
                        </td>
                        <td data-rotulo="Status">
                          <StatusSelo status={r.status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {registros.length < total && (
              <div style={{ textAlign: 'center', marginTop: 12 }}>
                <button className="btn" disabled={carregando} onClick={() => carregar(registros.length)}>
                  {carregando ? 'Carregando…' : 'Carregar mais'}
                </button>
              </div>
            )}
          </>
        ) : (
          <Carregando />
        )}
      </div>
    </>
  )
}
