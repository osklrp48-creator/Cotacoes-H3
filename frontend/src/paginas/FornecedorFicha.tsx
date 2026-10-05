import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, type Fornecedor, type FornecedorFicha as Ficha } from '../api'
import { Carregando, Icone, StatusSelo, useAvisar, useConfirmar } from '../componentes/ui'
import { fmtData, fmtMoeda, fmtNumero } from '../formato'

type Campos = Omit<Fornecedor, 'id'>
const VAZIO: Campos = { nome: '', cnpj: '', contato: '', telefone: '', email: '', observacoes: '' }

const doFornecedor = (f: Fornecedor): Campos => ({
  nome: f.nome,
  cnpj: f.cnpj ?? '',
  contato: f.contato ?? '',
  telefone: f.telefone ?? '',
  email: f.email ?? '',
  observacoes: f.observacoes ?? '',
})

export default function FornecedorFicha() {
  const { id } = useParams()
  const novo = id === 'novo'
  const navegar = useNavigate()
  const confirmar = useConfirmar()
  const avisar = useAvisar()
  const [ficha, setFicha] = useState<Ficha | null>(null)
  const [campos, setCampos] = useState<Campos>(VAZIO)
  const [modo, setModo] = useState<'ver' | 'editar'>(novo ? 'editar' : 'ver')
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)
  const travado = modo === 'ver'

  useEffect(() => {
    if (novo) return
    setFicha(null)
    setErro('')
    api<Ficha>(`/fornecedores/${id}`)
      .then((f) => {
        setFicha(f)
        setCampos(doFornecedor(f))
        setModo('ver')
      })
      .catch((e) => setErro(e.message))
  }, [id, novo])

  async function editar() {
    if (await confirmar({ titulo: 'Editar este fornecedor?', mensagem: 'Os campos serão liberados para alteração.' })) setModo('editar')
  }

  function cancelar() {
    if (novo) navegar('/fornecedores')
    else {
      setCampos(doFornecedor(ficha!))
      setErro('')
      setModo('ver')
    }
  }

  async function salvar(e: FormEvent) {
    e.preventDefault()
    const nome = campos.nome.trim()
    if (!nome) {
      setErro('Informe o nome do fornecedor.')
      return
    }
    setErro('')
    const corpo = Object.fromEntries(Object.entries(campos).map(([k, v]) => [k, (v ?? '').trim() || null]))
    try {
      setSalvando(true)
      if (novo) {
        const f = await api<Fornecedor>('/fornecedores', { metodo: 'POST', corpo })
        avisar('Fornecedor cadastrado.')
        navegar(`/fornecedores/${f.id}`, { replace: true })
        return
      }
      if (nome !== ficha!.nome) {
        const previa = await api<{ registros_alterados: number; juntar_com: { id: number; nome: string } | null }>(
          `/fornecedores/${id}/previa`,
          { params: { nome } },
        )
        const n = previa.registros_alterados
        const regs = `${n} ${n === 1 ? 'registro' : 'registros'}`
        const ok = await confirmar(
          previa.juntar_com
            ? {
                titulo: 'Juntar fornecedores?',
                mensagem: `Já existe o fornecedor "${previa.juntar_com.nome}". Os dois cadastros serão juntados em "${nome}" e ${regs} deste fornecedor passarão para ele.`,
                sim: 'Juntar',
                nao: 'Cancelar',
              }
            : {
                titulo: 'Renomear fornecedor?',
                mensagem: `O nome será alterado de "${ficha!.nome}" para "${nome}" em ${regs}.`,
                sim: 'Renomear',
                nao: 'Cancelar',
              },
        )
        if (!ok) return
      }
      const r = await api<{ fornecedor: Fornecedor; registros_alterados: number; juntou: boolean }>(`/fornecedores/${id}`, {
        metodo: 'PUT',
        corpo,
      })
      avisar(
        r.juntou
          ? `Fornecedores juntados (${r.registros_alterados} registro(s) movido(s)).`
          : r.registros_alterados
            ? `Fornecedor salvo. Nome atualizado em ${r.registros_alterados} registro(s).`
            : 'Fornecedor salvo.',
      )
      if (r.fornecedor.id !== Number(id)) {
        navegar(`/fornecedores/${r.fornecedor.id}`, { replace: true })
      } else {
        const f = await api<Ficha>(`/fornecedores/${id}`)
        setFicha(f)
        setCampos(doFornecedor(f))
        setModo('ver')
      }
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setSalvando(false)
    }
  }

  const voltar = (
    <Link to="/fornecedores" className="voltar">
      {Icone.voltar(16)} Fornecedores
    </Link>
  )
  if (!novo && !ficha)
    return erro ? (
      <>
        {voltar}
        <div className="alerta alerta-erro">{erro}</div>
      </>
    ) : (
      <Carregando />
    )

  const campo = (k: keyof Campos, rotulo: string, props: Record<string, unknown> = {}) => (
    <label className="campo">
      <span>{rotulo}</span>
      <input value={campos[k] ?? ''} onChange={(e) => setCampos((c) => ({ ...c, [k]: e.target.value }))} disabled={travado} {...props} />
    </label>
  )

  return (
    <>
      {voltar}
      <div className="cabecalho">
        <div>
          <h1>{novo ? 'Novo fornecedor' : ficha!.nome}</h1>
          {ficha && (
            <div className="sub">
              {ficha.qtd_registros} {ficha.qtd_registros === 1 ? 'registro' : 'registros'}
            </div>
          )}
        </div>
        {travado && (
          <button className="btn btn-primario" onClick={editar}>
            {Icone.lapis()} Editar
          </button>
        )}
      </div>

      <form className="cartao" onSubmit={salvar} noValidate>
        {!novo && (
          <div className={`modo-aviso${travado ? '' : ' editando'}`}>
            {travado ? (
              <>{Icone.cadeado(16)} Modo visualização. Clique em "Editar" para alterar.</>
            ) : (
              <>{Icone.lapis(16)} Editando. Ao mudar o nome, ele é atualizado em todos os registros deste fornecedor.</>
            )}
          </div>
        )}
        <div className="grade">
          {campo('nome', 'Nome *', { maxLength: 200, required: true })}
          {campo('cnpj', 'CNPJ', { maxLength: 30 })}
          {campo('contato', 'Contato', { maxLength: 200 })}
          {campo('telefone', 'Telefone', { maxLength: 60, type: 'tel' })}
          {campo('email', 'E-mail', { maxLength: 254, type: 'email' })}
        </div>
        <label className="campo" style={{ marginTop: 12 }}>
          <span>Observações</span>
          <textarea value={campos.observacoes ?? ''} onChange={(e) => setCampos((c) => ({ ...c, observacoes: e.target.value }))} disabled={travado} rows={3} />
        </label>
        {erro && <div className="alerta alerta-erro">{erro}</div>}
        {!travado && (
          <div className="acoes-barra">
            <button type="button" className="btn" onClick={cancelar} disabled={salvando}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primario" disabled={salvando}>
              {salvando ? 'Salvando…' : 'Salvar'}
            </button>
          </div>
        )}
      </form>

      {ficha && (
        <div className="cartao">
          <h2>Valores registrados</h2>
          {ficha.valores.length === 0 ? (
            <div className="vazio">Nenhum valor registrado para este fornecedor.</div>
          ) : (
            <div className="tabela-caixa">
              <table className="tabela responsiva">
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Produto</th>
                    <th>Marca</th>
                    <th>Unid.</th>
                    <th className="num">Qtd.</th>
                    <th className="num">Valor unit.</th>
                    <th>Unidade H3</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {ficha.valores.map((v) => (
                    <tr key={v.item_id} className="clicavel" onClick={() => navegar(`/registros/${v.registro_id}`)}>
                      <td data-rotulo="Data">
                        {fmtData(v.data)}
                        {v.numero && <div className="fraco">nº {v.numero}</div>}
                      </td>
                      <td className="principal">
                        {v.produto}
                        {v.descricao && <div className="fraco">{v.descricao}</div>}
                      </td>
                      <td data-rotulo="Marca">{v.marca || '—'}</td>
                      <td data-rotulo="Unid.">{v.unidade_medida || '—'}</td>
                      <td data-rotulo="Qtd." className="num">
                        {fmtNumero(v.quantidade) || '—'}
                      </td>
                      <td data-rotulo="Valor unit." className="num">
                        <strong>{fmtMoeda(v.valor)}</strong>
                      </td>
                      <td data-rotulo="Unidade H3">{v.unidade}</td>
                      <td data-rotulo="Status">
                        <StatusSelo status={v.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  )
}
