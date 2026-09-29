export type Perfil = 'admin' | 'usuario'
export type Status = 'recebida' | 'em_analise' | 'aprovada' | 'recusada'

export interface Unidade {
  id: number
  nome: string
  ativo: boolean
}

export interface Usuario {
  id: number
  nome: string
  email: string
  perfil: Perfil
  ativo: boolean
  unidade: Unidade
}

export interface Item {
  id?: number
  produto: string
  marca: string | null
  unidade_medida: string
  quantidade: number | null
  valor_unitario: number
}

export interface Registro {
  id: number
  fornecedor_id: number | null
  fornecedor: string | null
  data_recebimento: string
  unidade: { id: number; nome: string }
  usuario: { id: number; nome: string }
  cnpj: string | null
  contato: string | null
  telefone: string | null
  email: string | null
  numero: string | null
  status: Status
  condicao_pagamento: string | null
  prazo_entrega: string | null
  frete: 'CIF' | 'FOB' | null
  valor_frete: number | null
  referencia_interna: string | null
  observacoes: string | null
  criado_em: string
  atualizado_em: string
  itens: Item[]
}

export interface RegistroResumo {
  id: number
  data_recebimento: string
  fornecedor: string
  unidade: string
  usuario: string
  numero: string | null
  status: Status
  qtd_itens: number
  itens_resumo: string
}

export interface Ponto {
  valor: number
  fornecedor: string
  data: string
}

export interface ProdutoResumo {
  nome: string
  chave: string
  unidade_medida: string
  marcas: string[]
  qtd_valores: number
  menor: Ponto
  ultimo: Ponto
  maior: Ponto
}

export interface ValorProduto {
  item_id: number
  registro_id: number
  data: string
  fornecedor: string
  fornecedor_id: number | null
  produto: string
  marca: string | null
  quantidade: number | null
  valor: number
  unidade: string
  diferenca_pct: number | null
}

export interface ProdutoDetalhe extends ProdutoResumo {
  valores: ValorProduto[]
}

export interface Fornecedor {
  id: number
  nome: string
  cnpj: string | null
  contato: string | null
  telefone: string | null
  email: string | null
  observacoes: string | null
}

export interface FornecedorLista extends Fornecedor {
  qtd_registros: number
  ultimo_registro: string | null
}

export interface ValorFornecedor {
  item_id: number
  registro_id: number
  data: string
  numero: string | null
  status: Status
  unidade: string
  produto: string
  marca: string | null
  unidade_medida: string
  quantidade: number | null
  valor: number
}

export interface FornecedorFicha extends Fornecedor {
  qtd_registros: number
  valores: ValorFornecedor[]
}

export interface LeituraIA {
  fornecedor: string
  cnpj: string
  contato: string
  telefone: string
  email: string
  numero: string
  data: string
  pagamento: string
  entrega: string
  frete: 'CIF' | 'FOB' | ''
  valorFrete: number
  obs: string
  itens: { produto: string; marca: string; unidade: string; qtd: number; valorUnit: number }[]
}

export class ErroApi extends Error {
  status: number
  constructor(mensagem: string, status: number) {
    super(mensagem)
    this.status = status
  }
}

let aoExpirar: (() => void) | null = null
export function definirAoExpirar(fn: () => void) {
  aoExpirar = fn
}

const MENSAGENS: Record<number, string> = {
  403: 'Você não tem permissão para esta ação.',
  404: 'Não encontrado.',
  413: 'Arquivo grande demais.',
  500: 'Erro no servidor. Tente novamente em instantes.',
  502: 'Servidor indisponível. Tente novamente em instantes.',
  503: 'Serviço indisponível no momento.',
  504: 'O servidor demorou para responder. Tente novamente.',
}

export async function api<T = unknown>(
  caminho: string,
  opcoes: { metodo?: string; corpo?: unknown; params?: Record<string, string | number | undefined | null> } = {},
): Promise<T> {
  const url = new URL('/api' + caminho, window.location.origin)
  for (const [k, v] of Object.entries(opcoes.params ?? {})) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v))
  }
  const init: RequestInit = { method: opcoes.metodo ?? 'GET', credentials: 'include', headers: {} }
  if (opcoes.corpo instanceof FormData) {
    init.body = opcoes.corpo
  } else if (opcoes.corpo !== undefined) {
    init.body = JSON.stringify(opcoes.corpo)
    ;(init.headers as Record<string, string>)['Content-Type'] = 'application/json'
  }

  let resp: Response
  try {
    resp = await fetch(url, init)
  } catch {
    throw new ErroApi('Sem conexão com o servidor. Verifique sua internet e tente de novo.', 0)
  }
  if (resp.status === 204) return undefined as T
  const dados = await resp.json().catch(() => null)
  if (!resp.ok) {
    if (resp.status === 401 && !caminho.startsWith('/auth/')) aoExpirar?.()
    const detalhe = dados && typeof dados.detail === 'string' ? dados.detail : null
    throw new ErroApi(detalhe ?? MENSAGENS[resp.status] ?? `Erro inesperado (${resp.status}).`, resp.status)
  }
  return dados as T
}

export const STATUS_ROTULO: Record<Status, string> = {
  recebida: 'Recebida',
  em_analise: 'Em análise',
  aprovada: 'Aprovada',
  recusada: 'Recusada',
}
