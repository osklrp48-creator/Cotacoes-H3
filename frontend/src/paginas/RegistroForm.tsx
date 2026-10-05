import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, STATUS_ROTULO, type FornecedorLista, type LeituraIA, type Registro, type Status, type Unidade } from '../api'
import { useSessao } from '../auth'
import ImportarCotacao from '../componentes/ImportarCotacao'
import { Carregando, Icone, StatusSelo, useAvisar, useConfirmar } from '../componentes/ui'
import { casasDecimais, fmtDataHora, hoje, lerNumero, numeroParaCampo } from '../formato'

interface ItemForm {
  uid: string
  produto: string
  descricao: string
  marca: string
  unidade_medida: string
  quantidade: string
  valor_unitario: string
}

interface Formulario {
  fornecedor: string
  data_recebimento: string
  unidade_id: string
  cnpj: string
  contato: string
  telefone: string
  email: string
  numero: string
  status: Status
  condicao_pagamento: string
  prazo_entrega: string
  frete: '' | 'CIF' | 'FOB'
  valor_frete: string
  referencia_interna: string
  observacoes: string
  itens: ItemForm[]
}

type CampoTexto = Exclude<keyof Formulario, 'itens'>
type CampoItem = Exclude<keyof ItemForm, 'uid'>

const DETALHES: CampoTexto[] = [
  'cnpj', 'contato', 'telefone', 'email', 'numero', 'condicao_pagamento', 'prazo_entrega',
  'frete', 'valor_frete', 'referencia_interna', 'observacoes',
]
const UNIDADES_SUGERIDAS = ['UN', 'CX', 'FR', 'AMP', 'PCT', 'CP', 'KG', 'G', 'L', 'ML', 'RL', 'GL', 'TB', 'BIS', 'PAR']

const LIMITE_DESCRICAO = 4000

let contador = 0
const novoUid = () => `i${++contador}`
const itemVazio = (): ItemForm => ({ uid: novoUid(), produto: '', descricao: '', marca: '', unidade_medida: '', quantidade: '', valor_unitario: '' })
const itemPreenchido = (i: ItemForm) =>
  !!(i.produto.trim() || i.descricao.trim() || i.marca.trim() || i.quantidade.trim() || i.valor_unitario.trim())

function formVazio(unidadeId: number): Formulario {
  return {
    fornecedor: '', data_recebimento: hoje(), unidade_id: String(unidadeId), cnpj: '', contato: '', telefone: '',
    email: '', numero: '', status: 'recebida', condicao_pagamento: '', prazo_entrega: '', frete: '', valor_frete: '',
    referencia_interna: '', observacoes: '', itens: [itemVazio()],
  }
}

function formDoRegistro(r: Registro): Formulario {
  return {
    fornecedor: r.fornecedor ?? '',
    data_recebimento: r.data_recebimento,
    unidade_id: String(r.unidade.id),
    cnpj: r.cnpj ?? '',
    contato: r.contato ?? '',
    telefone: r.telefone ?? '',
    email: r.email ?? '',
    numero: r.numero ?? '',
    status: r.status,
    condicao_pagamento: r.condicao_pagamento ?? '',
    prazo_entrega: r.prazo_entrega ?? '',
    frete: r.frete ?? '',
    valor_frete: numeroParaCampo(r.valor_frete),
    referencia_interna: r.referencia_interna ?? '',
    observacoes: r.observacoes ?? '',
    itens: r.itens.map((i) => ({
      uid: novoUid(),
      produto: i.produto,
      descricao: i.descricao ?? '',
      marca: i.marca ?? '',
      unidade_medida: i.unidade_medida,
      quantidade: numeroParaCampo(i.quantidade),
      valor_unitario: numeroParaCampo(i.valor_unitario),
    })),
  }
}

/** Valida e monta o corpo da requisição. Retorna uma mensagem de erro se algo estiver errado. */
function montarCorpo(f: Formulario, admin: boolean): { corpo?: object; erro?: string } {
  if (!f.data_recebimento) return { erro: 'Informe a data de recebimento.' }
  const itens = []
  const preenchidos = f.itens.filter(itemPreenchido)
  for (const [n, i] of preenchidos.entries()) {
    const rot = `Item ${n + 1}`
    if (!i.produto.trim()) return { erro: `${rot}: informe o produto.` }
    if (!i.valor_unitario.trim()) return { erro: `${rot}: informe o valor unitário.` }
    const valor = lerNumero(i.valor_unitario)
    if (valor === null || Number.isNaN(valor)) return { erro: `${rot}: valor unitário inválido.` }
    if (casasDecimais(i.valor_unitario) > 4) return { erro: `${rot}: use no máximo 4 casas decimais no valor unitário.` }
    const qtd = lerNumero(i.quantidade)
    if (Number.isNaN(qtd)) return { erro: `${rot}: quantidade inválida.` }
    itens.push({
      produto: i.produto.trim(),
      descricao: i.descricao.trim() || null,
      marca: i.marca.trim() || null,
      unidade_medida: i.unidade_medida.trim().toUpperCase() || null,
      quantidade: qtd === null ? null : Math.round(qtd * 1000) / 1000,
      valor_unitario: valor,
    })
  }
  if (!itens.length) return { erro: 'Informe pelo menos um item com produto e valor unitário.' }
  const frete = lerNumero(f.valor_frete)
  if (Number.isNaN(frete)) return { erro: 'Valor do frete inválido.' }
  const txt = (v: string) => v.trim() || null
  return {
    corpo: {
      fornecedor: txt(f.fornecedor),
      data_recebimento: f.data_recebimento,
      unidade_id: admin ? Number(f.unidade_id) : undefined,
      cnpj: txt(f.cnpj),
      contato: txt(f.contato),
      telefone: txt(f.telefone),
      email: txt(f.email),
      numero: txt(f.numero),
      status: f.status,
      condicao_pagamento: txt(f.condicao_pagamento),
      prazo_entrega: txt(f.prazo_entrega),
      frete: f.frete || null,
      valor_frete: frete === null ? null : Math.round(frete * 100) / 100,
      referencia_interna: txt(f.referencia_interna),
      observacoes: txt(f.observacoes),
      itens,
    },
  }
}

export default function RegistroForm() {
  const { id } = useParams()
  const novo = !id
  const navegar = useNavigate()
  const confirmar = useConfirmar()
  const avisar = useAvisar()
  const { usuario } = useSessao()
  const admin = usuario?.perfil === 'admin'

  const [registro, setRegistro] = useState<Registro | null>(null)
  const [form, setForm] = useState<Formulario>(() => formVazio(usuario!.unidade.id))
  const [modo, setModo] = useState<'ver' | 'editar'>(novo ? 'editar' : 'ver')
  const [ia, setIa] = useState<Set<string>>(new Set())
  const [avisoIa, setAvisoIa] = useState('')
  const [maisAberto, setMaisAberto] = useState(false)
  const [erro, setErro] = useState('')
  const [salvando, setSalvando] = useState(false)
  const [carregando, setCarregando] = useState(!novo)
  const [fornecedores, setFornecedores] = useState<string[]>([])
  const [unidades, setUnidades] = useState<Unidade[]>([])

  const travado = modo === 'ver'

  useEffect(() => {
    api<FornecedorLista[]>('/fornecedores').then((l) => setFornecedores(l.map((f) => f.nome))).catch(() => {})
    if (admin) api<Unidade[]>('/unidades').then(setUnidades).catch(() => {})
  }, [admin])

  useEffect(() => {
    if (novo) return
    setCarregando(true)
    api<Registro>(`/registros/${id}`)
      .then((r) => {
        setRegistro(r)
        setForm(formDoRegistro(r))
        setModo('ver')
        setMaisAberto(DETALHES.some((c) => r[c as keyof Registro]) || r.status !== 'recebida')
      })
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false))
  }, [id, novo])

  const tirarIa = (chave: string) =>
    setIa((s) => {
      if (!s.has(chave)) return s
      const n = new Set(s)
      n.delete(chave)
      return n
    })

  function mudar<K extends CampoTexto>(campo: K, valor: Formulario[K]) {
    setForm((f) => ({ ...f, [campo]: valor }))
    tirarIa(campo)
  }

  function mudarItem(uid: string, campo: CampoItem, valor: string) {
    setForm((f) => ({ ...f, itens: f.itens.map((i) => (i.uid === uid ? { ...i, [campo]: valor } : i)) }))
    tirarIa(`${uid}.${campo}`)
  }

  function removerItem(uid: string) {
    setForm((f) => {
      const itens = f.itens.filter((i) => i.uid !== uid)
      return { ...f, itens: itens.length ? itens : [itemVazio()] }
    })
  }

  async function aplicarLeitura(d: LeituraIA) {
    const marcados = new Set<string>()
    const cabecalho: Partial<Formulario> = {}
    const pares: [CampoTexto, string][] = [
      ['fornecedor', d.fornecedor], ['cnpj', d.cnpj], ['contato', d.contato], ['telefone', d.telefone],
      ['email', d.email], ['numero', d.numero], ['data_recebimento', d.data], ['condicao_pagamento', d.pagamento],
      ['prazo_entrega', d.entrega], ['frete', d.frete], ['observacoes', d.obs],
      ['valor_frete', d.valorFrete > 0 ? numeroParaCampo(d.valorFrete) : ''],
    ]
    for (const [campo, valor] of pares) {
      if (valor) {
        ;(cabecalho as Record<string, string>)[campo] = valor
        marcados.add(campo)
      }
    }
    const novos: ItemForm[] = d.itens.map((i) => {
      const item: ItemForm = {
        uid: novoUid(),
        produto: i.produto,
        descricao: i.descricao ?? '',
        marca: i.marca,
        unidade_medida: i.unidade,
        quantidade: i.qtd > 0 ? numeroParaCampo(i.qtd) : '',
        valor_unitario: i.valorUnit > 0 ? numeroParaCampo(i.valorUnit) : '',
      }
      for (const c of ['produto', 'descricao', 'marca', 'unidade_medida', 'quantidade', 'valor_unitario'] as CampoItem[]) {
        if (item[c]) marcados.add(`${item.uid}.${c}`)
      }
      return item
    })

    let substituir = true
    if (novos.length && form.itens.some(itemPreenchido)) {
      substituir = await confirmar({
        titulo: 'Substituir os itens já digitados?',
        mensagem: `A IA encontrou ${novos.length} ${novos.length === 1 ? 'item' : 'itens'}. "Sim" substitui os itens atuais; "Não" adiciona ao final.`,
      })
    }
    setForm((f) => ({
      ...f,
      ...cabecalho,
      itens: novos.length ? (substituir ? novos : [...f.itens.filter(itemPreenchido), ...novos]) : f.itens,
    }))
    setIa(marcados)
    if (DETALHES.some((c) => marcados.has(c))) setMaisAberto(true)
    const semValor = d.itens.filter((i) => !(i.valorUnit > 0)).length
    setAvisoIa(
      `A IA preencheu ${marcados.size} ${marcados.size === 1 ? 'campo' : 'campos'} (destacados em amarelo) com ${novos.length} ${novos.length === 1 ? 'item' : 'itens'}. Confira tudo antes de salvar.` +
        (semValor ? ` ${semValor} ${semValor === 1 ? 'item ficou' : 'itens ficaram'} sem valor unitário.` : '') +
        (!d.data ? ' A data não foi encontrada: confira a data de recebimento.' : ''),
    )
  }

  async function editar() {
    if (await confirmar({ titulo: 'Editar este registro?', mensagem: 'Os campos serão liberados para alteração.' })) {
      setModo('editar')
    }
  }

  async function cancelar() {
    if (novo) {
      navegar('/')
      return
    }
    setForm(formDoRegistro(registro!))
    setIa(new Set())
    setAvisoIa('')
    setErro('')
    setModo('ver')
  }

  async function excluir() {
    const ok = await confirmar({
      titulo: 'Excluir este registro?',
      mensagem: 'O registro e todos os seus itens serão apagados. Essa ação não pode ser desfeita.',
      sim: 'Excluir',
      nao: 'Cancelar',
      perigo: true,
    })
    if (!ok) return
    try {
      await api(`/registros/${id}`, { metodo: 'DELETE' })
      avisar('Registro excluído.')
      navegar('/')
    } catch (e) {
      avisar((e as Error).message, 'erro')
    }
  }

  async function salvar(e: FormEvent) {
    e.preventDefault()
    if (travado) return
    const { corpo, erro: problema } = montarCorpo(form, admin)
    if (problema) {
      setErro(problema)
      return
    }
    setErro('')
    setSalvando(true)
    try {
      const r = await api<Registro>(novo ? '/registros' : `/registros/${id}`, { metodo: novo ? 'POST' : 'PUT', corpo })
      avisar('Registro salvo.')
      setIa(new Set())
      setAvisoIa('')
      if (novo) {
        navegar(`/registros/${r.id}`, { replace: true })
      } else {
        setRegistro(r)
        setForm(formDoRegistro(r))
        setModo('ver')
      }
    } catch (e) {
      setErro((e as Error).message)
    } finally {
      setSalvando(false)
    }
  }

  if (carregando) return <Carregando />
  if (!novo && !registro)
    return (
      <>
        <Link to="/" className="voltar">
          {Icone.voltar(16)} Registros
        </Link>
        <div className="alerta alerta-erro">{erro || 'Registro não encontrado.'}</div>
      </>
    )

  const cls = (chave: string) => (ia.has(chave) ? 'ia-preenchido' : undefined)
  const texto = (campo: CampoTexto, rotulo: ReactNode, props: Record<string, unknown> = {}) => (
    <label className="campo">
      <span>{rotulo}</span>
      <input
        value={form[campo] as string}
        onChange={(e) => mudar(campo, e.target.value as never)}
        disabled={travado}
        className={cls(campo)}
        {...props}
      />
    </label>
  )

  return (
    <>
      <Link to="/" className="voltar">
        {Icone.voltar(16)} Registros
      </Link>
      <div className="cabecalho">
        <div>
          <h1>{novo ? 'Registrar valores' : registro?.fornecedor || 'Não informado'}</h1>
          {registro && (
            <div className="sub">
              Registro nº {registro.id} · {registro.unidade.nome} · <StatusSelo status={registro.status} />
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
            {travado ? <>{Icone.cadeado(16)} Modo visualização. Clique em "Editar" para alterar.</> : <>{Icone.lapis(16)} Editando registro.</>}
          </div>
        )}

        {!travado && <ImportarCotacao aoLer={aplicarLeitura} />}
        {avisoIa && <div className="alerta alerta-ia">{avisoIa}</div>}

        <div className="grade-2">
          {texto('fornecedor', <>Quem passou o valor <span className="dica">(opcional)</span></>, {
            list: 'lista-fornecedores',
            placeholder: 'Empresa, loja ou pessoa. Ex.: João (WhatsApp)',
            maxLength: 200,
          })}
          {texto('data_recebimento', 'Data de recebimento *', { type: 'date', required: true })}
        </div>
        <datalist id="lista-fornecedores">
          {fornecedores.map((n) => (
            <option key={n} value={n} />
          ))}
        </datalist>

        {admin && (
          <div className="grade" style={{ marginTop: 12 }}>
            <label className="campo">
              <span>Unidade</span>
              <select value={form.unidade_id} onChange={(e) => mudar('unidade_id', e.target.value)} disabled={travado}>
                {unidades.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.nome}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        <div className="secao-titulo">
          <h2>Itens</h2>
          <span className="fraco">{form.itens.filter(itemPreenchido).length} preenchido(s)</span>
        </div>
        <div>
          {form.itens.map((i, n) => (
            <div className="item-linha" key={i.uid}>
              <span className="item-num">Item {n + 1}</span>
              <label className="campo item-produto">
                <span>Produto *</span>
                <input value={i.produto} onChange={(e) => mudarItem(i.uid, 'produto', e.target.value)} disabled={travado} className={cls(`${i.uid}.produto`)} maxLength={300} />
              </label>
              <label className="campo">
                <span>Marca</span>
                <input value={i.marca} onChange={(e) => mudarItem(i.uid, 'marca', e.target.value)} disabled={travado} className={cls(`${i.uid}.marca`)} maxLength={120} />
              </label>
              <label className="campo">
                <span>Unid.</span>
                <input
                  value={i.unidade_medida}
                  onChange={(e) => mudarItem(i.uid, 'unidade_medida', e.target.value.toUpperCase())}
                  disabled={travado}
                  className={cls(`${i.uid}.unidade_medida`)}
                  list="lista-unidades"
                  maxLength={20}
                  placeholder="UN"
                />
              </label>
              <label className="campo">
                <span>Qtd.</span>
                <input value={i.quantidade} onChange={(e) => mudarItem(i.uid, 'quantidade', e.target.value)} disabled={travado} className={cls(`${i.uid}.quantidade`)} inputMode="decimal" />
              </label>
              <label className="campo">
                <span>Valor unit. (R$) *</span>
                <input
                  value={i.valor_unitario}
                  onChange={(e) => mudarItem(i.uid, 'valor_unitario', e.target.value)}
                  disabled={travado}
                  className={cls(`${i.uid}.valor_unitario`)}
                  inputMode="decimal"
                  placeholder="0,00"
                />
              </label>
              {!travado ? (
                <button type="button" className="btn btn-icone" onClick={() => removerItem(i.uid)} title="Remover item" aria-label={`Remover item ${n + 1}`}>
                  {Icone.lixeira()}
                </button>
              ) : (
                <span />
              )}
              {(!travado || i.descricao) && (
                <label className="campo item-descricao">
                  <span>
                    Descrição <span className="dica">(opcional)</span>
                  </span>
                  <textarea
                    value={i.descricao}
                    onChange={(e) => mudarItem(i.uid, 'descricao', e.target.value)}
                    disabled={travado}
                    className={cls(`${i.uid}.descricao`)}
                    maxLength={LIMITE_DESCRICAO}
                    rows={Math.min(8, Math.max(1, Math.ceil(i.descricao.length / 110), i.descricao.split('\n').length))}
                    placeholder="Ex.: caixa com 10 comprimidos, apresentação, especificação técnica"
                  />
                  {!travado && i.descricao.length > LIMITE_DESCRICAO - 400 && (
                    <span className="dica">
                      {i.descricao.length.toLocaleString('pt-BR')} de {LIMITE_DESCRICAO.toLocaleString('pt-BR')} caracteres
                    </span>
                  )}
                </label>
              )}
            </div>
          ))}
        </div>
        <datalist id="lista-unidades">
          {UNIDADES_SUGERIDAS.map((u) => (
            <option key={u} value={u} />
          ))}
        </datalist>
        {!travado && (
          <button type="button" className="btn" style={{ marginTop: 10 }} onClick={() => setForm((f) => ({ ...f, itens: [...f.itens, itemVazio()] }))}>
            {Icone.mais()} Adicionar item
          </button>
        )}

        <details className="mais" open={maisAberto} onToggle={(e) => setMaisAberto((e.target as HTMLDetailsElement).open)}>
          <summary>Mais detalhes (opcional)</summary>
          <div className="grade">
            {texto('cnpj', 'CNPJ', { maxLength: 30, inputMode: 'numeric' })}
            {texto('contato', 'Contato', { maxLength: 200 })}
            {texto('telefone', 'Telefone', { maxLength: 60, type: 'tel' })}
            {texto('email', 'E-mail', { maxLength: 254, type: 'email' })}
            {texto('numero', 'Nº da cotação', { maxLength: 60 })}
            <label className="campo">
              <span>Status</span>
              <select value={form.status} onChange={(e) => mudar('status', e.target.value as Status)} disabled={travado}>
                {(Object.keys(STATUS_ROTULO) as Status[]).map((s) => (
                  <option key={s} value={s}>
                    {STATUS_ROTULO[s]}
                  </option>
                ))}
              </select>
            </label>
            {texto('condicao_pagamento', 'Condição de pagamento', { maxLength: 200, placeholder: 'Ex.: 28 dias' })}
            {texto('prazo_entrega', 'Prazo de entrega', { maxLength: 200, placeholder: 'Ex.: 5 dias úteis' })}
            <label className="campo">
              <span>Frete</span>
              <select value={form.frete} onChange={(e) => mudar('frete', e.target.value as Formulario['frete'])} disabled={travado} className={cls('frete')}>
                <option value="">Não informado</option>
                <option value="CIF">CIF (por conta do fornecedor)</option>
                <option value="FOB">FOB (por conta da H3)</option>
              </select>
            </label>
            {texto('valor_frete', 'Valor do frete (R$)', { inputMode: 'decimal', placeholder: '0,00' })}
            {texto('referencia_interna', 'Referência interna', { maxLength: 120 })}
          </div>
          <label className="campo" style={{ marginTop: 12 }}>
            <span>Observações</span>
            <textarea value={form.observacoes} onChange={(e) => mudar('observacoes', e.target.value)} disabled={travado} className={cls('observacoes')} rows={3} />
          </label>
        </details>

        {registro && (
          <div className="meta">
            <span>Registrado por {registro.usuario.nome}</span>
            <span>Criado em {fmtDataHora(registro.criado_em)}</span>
            <span>Atualizado em {fmtDataHora(registro.atualizado_em)}</span>
          </div>
        )}

        {erro && <div className="alerta alerta-erro">{erro}</div>}

        {!travado && (
          <div className="acoes-barra">
            {!novo && (
              <button type="button" className="btn btn-perigo esquerda" onClick={excluir} disabled={salvando}>
                {Icone.lixeira()} Excluir
              </button>
            )}
            <button type="button" className="btn" onClick={cancelar} disabled={salvando}>
              Cancelar
            </button>
            <button type="submit" className="btn btn-primario" disabled={salvando}>
              {salvando ? 'Salvando…' : 'Salvar'}
            </button>
          </div>
        )}
      </form>
    </>
  )
}
