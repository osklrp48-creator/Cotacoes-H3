const moeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
})
const numero = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 4 })
const inteiro = new Intl.NumberFormat('pt-BR')

export const fmtMoeda = (v: number | null | undefined) => (v === null || v === undefined ? '—' : moeda.format(v))
export const fmtNumero = (v: number | null | undefined) => (v === null || v === undefined ? '' : numero.format(v))
export const fmtInteiro = (v: number) => inteiro.format(v)

/** "2026-09-15" → "15/09/2026" (sem fuso horário). */
export function fmtData(iso: string | null | undefined): string {
  if (!iso) return ''
  const [a, m, d] = iso.slice(0, 10).split('-')
  return `${d}/${m}/${a}`
}

export function fmtDataHora(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

export function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return ''
  if (v === 0) return 'menor'
  return '+' + v.toLocaleString('pt-BR', { maximumFractionDigits: 1 }) + '%'
}

/** Número digitado no padrão brasileiro ("1.234,50") ou com ponto ("12.5") → number. */
export function lerNumero(texto: string): number | null {
  let t = texto.trim().replace(/\s|R\$/g, '')
  if (!t) return null
  if (t.includes(',')) t = t.replace(/\./g, '').replace(',', '.')
  if (!/^\d*\.?\d*$/.test(t) || t === '.') return NaN
  return Number(t)
}

export function casasDecimais(texto: string): number {
  const t = texto.trim()
  const sep = t.includes(',') ? ',' : '.'
  const i = t.lastIndexOf(sep)
  return i === -1 ? 0 : t.length - i - 1
}

/** number → texto para campo de formulário ("12,5"). */
export function numeroParaCampo(v: number | null | undefined): string {
  if (v === null || v === undefined) return ''
  return String(v).replace('.', ',')
}

export function hoje(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}
