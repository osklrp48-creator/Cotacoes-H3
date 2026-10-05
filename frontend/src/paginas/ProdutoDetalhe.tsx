import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, type ProdutoDetalhe as Detalhe, type ValorProduto } from '../api'
import { Carregando, Icone, useAvisar, useConfirmar } from '../componentes/ui'
import { fmtData, fmtMoeda, fmtNumero, fmtPct } from '../formato'

const paraTempo = (iso: string) => {
  const [a, m, d] = iso.split('-').map(Number)
  return Date.UTC(a, m - 1, d)
}
const tempoParaData = (t: number) => fmtData(new Date(t).toISOString().slice(0, 10))

interface PontoGrafico {
  t: number
  valor: number
  fornecedor: string
  menor: boolean
}

function DicaGrafico({ active, payload }: { active?: boolean; payload?: { payload: PontoGrafico }[] }) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload
  return (
    <div className="grafico-tooltip">
      <div className="fraco">{tempoParaData(p.t)}</div>
      <strong>{fmtMoeda(p.valor)}</strong>
      <div>{p.fornecedor}</div>
      {p.menor && <div style={{ color: 'var(--verde)', fontWeight: 700 }}>Menor valor</div>}
    </div>
  )
}

function Grafico({ valores, menor }: { valores: ValorProduto[]; menor: number }) {
  const pontos: PontoGrafico[] = [...valores]
    .sort((a, b) => a.data.localeCompare(b.data) || a.item_id - b.item_id)
    .map((v) => ({ t: paraTempo(v.data), valor: v.valor, fornecedor: v.fornecedor, menor: v.valor === menor }))

  return (
    <div className="grafico" style={{ width: '100%', height: 300, color: 'var(--grafico-linha)' }}>
      <ResponsiveContainer height={270}>
        <LineChart data={pontos} margin={{ top: 16, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid vertical={false} />
          <XAxis dataKey="t" type="number" scale="time" domain={['dataMin', 'dataMax']} tickFormatter={tempoParaData} minTickGap={24} tickLine={false} axisLine={false} />
          <YAxis tickFormatter={(v: number) => fmtMoeda(v)} width={84} tickLine={false} axisLine={false} domain={['auto', 'auto']} />
          <Tooltip content={<DicaGrafico />} cursor={{ strokeDasharray: '3 3' }} />
          <ReferenceLine y={menor} strokeDasharray="4 4" className="linha-menor" />
          <Line
            type="linear"
            dataKey="valor"
            stroke="currentColor"
            strokeWidth={2}
            isAnimationActive={false}
            dot={(props: { cx?: number; cy?: number; payload?: PontoGrafico; index?: number }) => {
              const { cx, cy, payload, index } = props
              if (cx === undefined || cy === undefined) return <g key={index} />
              return payload?.menor ? (
                <g key={index}>
                  <circle cx={cx} cy={cy} r={9} fill="currentColor" opacity={0.2} />
                  <circle cx={cx} cy={cy} r={6} fill="currentColor" stroke="var(--superficie)" strokeWidth={2} />
                </g>
              ) : (
                <circle key={index} cx={cx} cy={cy} r={4} fill="var(--superficie)" stroke="currentColor" strokeWidth={2} />
              )
            }}
            activeDot={{ r: 6, stroke: 'var(--superficie)', strokeWidth: 2, fill: 'currentColor' }}
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="grafico-legenda">
        <span className="ponto-menor" /> Menor valor ({fmtMoeda(menor)}) — linha tracejada
      </div>
    </div>
  )
}

export default function ProdutoDetalhe() {
  const [params] = useSearchParams()
  const nome = params.get('nome') ?? ''
  const un = params.get('un') ?? ''
  const navegar = useNavigate()
  const confirmar = useConfirmar()
  const avisar = useAvisar()
  const [d, setD] = useState<Detalhe | null>(null)
  const [erro, setErro] = useState('')

  const carregar = useCallback(async () => {
    try {
      setD(await api<Detalhe>('/produtos/detalhe', { params: { nome, un } }))
    } catch (e) {
      setErro((e as Error).message)
    }
  }, [nome, un])

  useEffect(() => {
    carregar()
  }, [carregar])

  async function apagarProduto() {
    if (!d) return
    const ok = await confirmar({
      titulo: 'Apagar este produto?',
      mensagem: `"${d.nome}"${d.unidade_medida ? ` (${d.unidade_medida})` : ''} será removido de todos os registros (${d.qtd_valores} ${d.qtd_valores === 1 ? 'valor' : 'valores'}). Registros que ficarem sem itens também serão apagados.`,
      sim: 'Apagar',
      nao: 'Cancelar',
      perigo: true,
    })
    if (!ok) return
    try {
      const r = await api<{ itens_apagados: number; registros_apagados: number }>('/produtos', { metodo: 'DELETE', params: { nome, un } })
      avisar(`Produto apagado (${r.itens_apagados} valores${r.registros_apagados ? `, ${r.registros_apagados} registro(s) vazio(s) removido(s)` : ''}).`)
      navegar('/produtos')
    } catch (e) {
      avisar((e as Error).message, 'erro')
    }
  }

  async function apagarValor(v: ValorProduto) {
    const ok = await confirmar({
      titulo: 'Apagar este valor?',
      mensagem: `${fmtMoeda(v.valor)} de ${v.fornecedor} em ${fmtData(v.data)}. Se o registro ficar sem itens, ele também será apagado.`,
      sim: 'Apagar',
      nao: 'Cancelar',
      perigo: true,
    })
    if (!ok) return
    try {
      const r = await api<{ registros_apagados: number }>(`/itens/${v.item_id}`, { metodo: 'DELETE' })
      avisar(r.registros_apagados ? 'Valor apagado. O registro ficou vazio e também foi apagado.' : 'Valor apagado.')
      if (d && d.valores.length === 1) navegar('/produtos')
      else carregar()
    } catch (e) {
      avisar((e as Error).message, 'erro')
    }
  }

  if (erro)
    return (
      <>
        <Link to="/produtos" className="voltar">
          {Icone.voltar(16)} Produtos
        </Link>
        <div className="alerta alerta-erro">{erro}</div>
      </>
    )
  if (!d) return <Carregando />

  const datas = new Set(d.valores.map((v) => v.data))
  const menor = d.menor.valor

  return (
    <>
      <Link to="/produtos" className="voltar">
        {Icone.voltar(16)} Produtos
      </Link>
      <div className="cabecalho">
        <div>
          <h1>{d.nome}</h1>
          <div className="sub">
            {d.unidade_medida ? `Unidade: ${d.unidade_medida} · ` : ''}
            {d.qtd_valores} {d.qtd_valores === 1 ? 'valor registrado' : 'valores registrados'}
            {d.marcas.length > 0 && ` · Marcas: ${d.marcas.join(', ')}`}
          </div>
        </div>
        <button className="btn btn-perigo" onClick={apagarProduto}>
          {Icone.lixeira()} Apagar produto
        </button>
      </div>

      <div className="cartoes-valor">
        <div className="cartao-valor menor">
          <div className="rotulo">Menor valor</div>
          <div className="valor">{fmtMoeda(d.menor.valor)}</div>
          <div className="quem">
            {d.menor.fornecedor} · {fmtData(d.menor.data)}
          </div>
        </div>
        <div className="cartao-valor">
          <div className="rotulo">Último valor</div>
          <div className="valor">{fmtMoeda(d.ultimo.valor)}</div>
          <div className="quem">
            {d.ultimo.fornecedor} · {fmtData(d.ultimo.data)}
          </div>
        </div>
        <div className="cartao-valor">
          <div className="rotulo">Maior valor</div>
          <div className="valor">{fmtMoeda(d.maior.valor)}</div>
          <div className="quem">
            {d.maior.fornecedor} · {fmtData(d.maior.data)}
          </div>
        </div>
      </div>

      {datas.size >= 2 && (
        <div className="cartao">
          <h2>Valor unitário ao longo do tempo</h2>
          <Grafico valores={d.valores} menor={menor} />
        </div>
      )}

      <div className="cartao">
        <h2>Todos os valores (do menor ao maior)</h2>
        <div className="tabela-caixa">
          <table className="tabela responsiva">
            <thead>
              <tr>
                <th className="num">Valor unit.</th>
                <th className="num">Dif.</th>
                <th>Quem passou</th>
                <th>Data</th>
                <th>Marca / descrição</th>
                <th className="num">Qtd.</th>
                <th>Unidade H3</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {d.valores.map((v) => (
                <tr key={v.item_id} className={`clicavel${v.valor === menor ? ' destaque' : ''}`} onClick={() => navegar(`/registros/${v.registro_id}`)}>
                  <td className="principal num" style={{ textAlign: 'left' }}>
                    {fmtMoeda(v.valor)}
                  </td>
                  <td data-rotulo="Diferença" className="num">
                    <span className={`dif${v.diferenca_pct === 0 ? ' zero' : ''}`}>{fmtPct(v.diferenca_pct)}</span>
                  </td>
                  <td data-rotulo="Quem passou">
                    <span className={v.fornecedor === 'Não informado' ? 'nao-informado' : ''}>{v.fornecedor}</span>
                  </td>
                  <td data-rotulo="Data">{fmtData(v.data)}</td>
                  <td data-rotulo="Marca / descrição">
                    {v.marca || (!v.descricao && '—')}
                    {v.descricao && <div className="fraco">{v.descricao}</div>}
                  </td>
                  <td data-rotulo="Qtd." className="num">
                    {fmtNumero(v.quantidade) || '—'}
                  </td>
                  <td data-rotulo="Unidade H3">{v.unidade}</td>
                  <td className="acao-linha">
                    <button
                      className="btn btn-icone"
                      title="Apagar este valor"
                      aria-label="Apagar este valor"
                      onClick={(e) => {
                        e.stopPropagation()
                        apagarValor(v)
                      }}
                    >
                      {Icone.lixeira()}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  )
}
