import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { api, type ProdutoResumo } from '../api'
import { Carregando, useAtrasado } from '../componentes/ui'
import { fmtData, fmtMoeda } from '../formato'

export const linkProduto = (p: { chave: string; unidade_medida: string }) =>
  `/produtos/ver?${new URLSearchParams({ nome: p.chave, un: p.unidade_medida })}`

export default function Produtos() {
  const navegar = useNavigate()
  const [params, setParams] = useSearchParams()
  const [busca, setBusca] = useState(params.get('busca') ?? '')
  const buscaAtrasada = useAtrasado(busca)
  const ordem = params.get('ordem') ?? 'alfa'
  const [produtos, setProdutos] = useState<ProdutoResumo[] | null>(null)
  const [erro, setErro] = useState('')
  const requisicao = useRef(0)

  useEffect(() => {
    const novo = new URLSearchParams(params)
    if (buscaAtrasada) novo.set('busca', buscaAtrasada)
    else novo.delete('busca')
    if (novo.toString() !== params.toString()) setParams(novo, { replace: true })
    const minha = ++requisicao.current
    setErro('')
    api<ProdutoResumo[]>('/produtos', { params: { busca: buscaAtrasada, ordem } })
      .then((p) => minha === requisicao.current && setProdutos(p))
      .catch((e) => setErro(e.message))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [buscaAtrasada, ordem])

  function mudarOrdem(valor: string) {
    const novo = new URLSearchParams(params)
    novo.set('ordem', valor)
    setParams(novo, { replace: true })
  }

  return (
    <>
      <div className="cabecalho">
        <div>
          <h1>Produtos</h1>
          <div className="sub">Um produto por linha, agrupado pelo nome e pela unidade de medida.</div>
        </div>
      </div>
      <div className="cartao">
        <div className="filtros">
          <input type="search" placeholder="Buscar produto ou marca…" value={busca} onChange={(e) => setBusca(e.target.value)} aria-label="Buscar produto" />
          <select value={ordem} onChange={(e) => mudarOrdem(e.target.value)} aria-label="Ordenar">
            <option value="alfa">Ordem alfabética</option>
            <option value="recente">Mais recentes</option>
            <option value="mais">Mais registrados</option>
          </select>
        </div>
        {erro && <div className="alerta alerta-erro">{erro}</div>}
        {produtos === null ? (
          !erro && <Carregando />
        ) : produtos.length === 0 ? (
          <div className="vazio">{buscaAtrasada ? 'Nenhum produto encontrado.' : 'Nenhum produto registrado ainda.'}</div>
        ) : (
          <>
            <div className="fraco" style={{ marginBottom: 6 }}>
              {produtos.length} {produtos.length === 1 ? 'produto' : 'produtos'}
            </div>
            <div className="tabela-caixa">
              <table className="tabela responsiva">
                <thead>
                  <tr>
                    <th>Produto</th>
                    <th>Unid.</th>
                    <th>Marcas</th>
                    <th className="num">Valores</th>
                    <th className="num">Menor valor</th>
                    <th className="num">Último</th>
                    <th className="num">Maior</th>
                  </tr>
                </thead>
                <tbody>
                  {produtos.map((p) => (
                    <tr key={p.chave + '|' + p.unidade_medida} className="clicavel" onClick={() => navegar(linkProduto(p))}>
                      <td className="principal">{p.nome}</td>
                      <td data-rotulo="Unidade">{p.unidade_medida || '—'}</td>
                      <td data-rotulo="Marcas">
                        {p.marcas.length ? p.marcas.map((m) => <span key={m} className="etiqueta">{m}</span>) : <span className="fraco">—</span>}
                      </td>
                      <td data-rotulo="Nº de valores" className="num">
                        {p.qtd_valores}
                      </td>
                      <td data-rotulo="Menor valor" className="num">
                        <strong>{fmtMoeda(p.menor.valor)}</strong>
                        <div className="fraco">{p.menor.fornecedor}</div>
                      </td>
                      <td data-rotulo="Último valor" className="num">
                        {fmtMoeda(p.ultimo.valor)}
                        <div className="fraco">{fmtData(p.ultimo.data)}</div>
                      </td>
                      <td data-rotulo="Maior valor" className="num">
                        {fmtMoeda(p.maior.valor)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </>
  )
}
