import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, type FornecedorLista } from '../api'
import { Carregando, Icone, useAtrasado } from '../componentes/ui'
import { fmtData } from '../formato'

export default function Fornecedores() {
  const navegar = useNavigate()
  const [busca, setBusca] = useState('')
  const buscaAtrasada = useAtrasado(busca)
  const [lista, setLista] = useState<FornecedorLista[] | null>(null)
  const [erro, setErro] = useState('')
  const requisicao = useRef(0)

  useEffect(() => {
    const minha = ++requisicao.current
    api<FornecedorLista[]>('/fornecedores', { params: { busca: buscaAtrasada } })
      .then((l) => minha === requisicao.current && setLista(l))
      .catch((e) => setErro(e.message))
  }, [buscaAtrasada])

  return (
    <>
      <div className="cabecalho">
        <div>
          <h1>Fornecedores</h1>
          <div className="sub">Cadastro criado automaticamente a partir de "Quem passou o valor".</div>
        </div>
        <button className="btn" onClick={() => navegar('/fornecedores/novo')}>
          {Icone.mais()} Novo fornecedor
        </button>
      </div>
      <div className="cartao">
        <div className="filtros">
          <input type="search" placeholder="Buscar por nome ou CNPJ…" value={busca} onChange={(e) => setBusca(e.target.value)} aria-label="Buscar fornecedor" />
        </div>
        {erro && <div className="alerta alerta-erro">{erro}</div>}
        {lista === null ? (
          !erro && <Carregando />
        ) : lista.length === 0 ? (
          <div className="vazio">{buscaAtrasada ? 'Nenhum fornecedor encontrado.' : 'Nenhum fornecedor ainda.'}</div>
        ) : (
          <div className="tabela-caixa">
            <table className="tabela responsiva">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>CNPJ</th>
                  <th>Contato</th>
                  <th>Telefone / e-mail</th>
                  <th className="num">Registros</th>
                  <th>Último</th>
                </tr>
              </thead>
              <tbody>
                {lista.map((f) => (
                  <tr key={f.id} className="clicavel" onClick={() => navegar(`/fornecedores/${f.id}`)}>
                    <td className="principal">{f.nome}</td>
                    <td data-rotulo="CNPJ">{f.cnpj || '—'}</td>
                    <td data-rotulo="Contato">{f.contato || '—'}</td>
                    <td data-rotulo="Telefone / e-mail">
                      {f.telefone || (!f.email && '—')}
                      {f.email && <div className="fraco">{f.email}</div>}
                    </td>
                    <td data-rotulo="Registros" className="num">
                      {f.qtd_registros}
                    </td>
                    <td data-rotulo="Último registro">{f.ultimo_registro ? fmtData(f.ultimo_registro) : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  )
}
