import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { STATUS_ROTULO, type Status } from '../api'

/* ---------- Ícones ---------- */
const svg = (d: ReactNode, tam = 18) => (
  <svg width={tam} height={tam} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {d}
  </svg>
)
export const Icone = {
  lixeira: (t?: number) => svg(<><path d="M3 6h18" /><path d="M8 6V4h8v2" /><path d="M19 6l-1 14H6L5 6" /><path d="M10 11v6M14 11v6" /></>, t),
  mais: (t?: number) => svg(<path d="M12 5v14M5 12h14" />, t),
  voltar: (t?: number) => svg(<path d="M15 18l-6-6 6-6" />, t),
  lapis: (t?: number) => svg(<><path d="M12 20h9" /><path d="M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z" /></>, t),
  sol: (t?: number) => svg(<><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>, t),
  lua: (t?: number) => svg(<path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z" />, t),
  sair: (t?: number) => svg(<><path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" /><path d="M16 17l5-5-5-5M21 12H9" /></>, t),
  brilho: (t?: number) => svg(<path d="M12 3l1.9 5.1L19 10l-5.1 1.9L12 17l-1.9-5.1L5 10l5.1-1.9zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z" />, t),
  arquivo: (t?: number) => svg(<><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><path d="M14 2v6h6" /></>, t),
  cadeado: (t?: number) => svg(<><rect x="4" y="11" width="16" height="10" rx="2" /><path d="M8 11V7a4 4 0 018 0v4" /></>, t),
}

export function Carregando({ texto = 'Carregando…' }: { texto?: string }) {
  return (
    <div className="carregando" role="status">
      <span className="girando" /> {texto}
    </div>
  )
}

export function StatusSelo({ status }: { status: Status }) {
  return <span className={`status status-${status}`}>{STATUS_ROTULO[status]}</span>
}

export function Modal({ children, largo, aoFechar }: { children: ReactNode; largo?: boolean; aoFechar?: () => void }) {
  useEffect(() => {
    const tecla = (e: KeyboardEvent) => e.key === 'Escape' && aoFechar?.()
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [aoFechar])
  return (
    <div className="modal-fundo" onMouseDown={(e) => e.target === e.currentTarget && aoFechar?.()}>
      <div className={`modal${largo ? ' largo' : ''}`} role="dialog" aria-modal="true">
        {children}
      </div>
    </div>
  )
}

/* ---------- Confirmação (Sim/Não) ---------- */
interface PedidoConfirmacao {
  titulo: string
  mensagem?: string
  sim?: string
  nao?: string
  perigo?: boolean
}
type Confirmar = (p: PedidoConfirmacao) => Promise<boolean>
const ConfirmarCtx = createContext<Confirmar>(async () => false)
export const useConfirmar = () => useContext(ConfirmarCtx)

/* ---------- Avisos rápidos ---------- */
type Avisar = (texto: string, tipo?: 'ok' | 'erro') => void
const AvisoCtx = createContext<Avisar>(() => {})
export const useAvisar = () => useContext(AvisoCtx)

export function ProvedorUI({ children }: { children: ReactNode }) {
  const [pedido, setPedido] = useState<PedidoConfirmacao | null>(null)
  const resolver = useRef<(v: boolean) => void>(undefined)
  const [avisos, setAvisos] = useState<{ id: number; texto: string; tipo: 'ok' | 'erro' }[]>([])
  const botaoSim = useRef<HTMLButtonElement>(null)

  const confirmar = useCallback<Confirmar>(
    (p) =>
      new Promise((ok) => {
        resolver.current = ok
        setPedido(p)
      }),
    [],
  )
  const responder = (v: boolean) => {
    resolver.current?.(v)
    setPedido(null)
  }
  const avisar = useCallback<Avisar>((texto, tipo = 'ok') => {
    const id = Date.now() + Math.random()
    setAvisos((a) => [...a, { id, texto, tipo }])
    setTimeout(() => setAvisos((a) => a.filter((x) => x.id !== id)), tipo === 'erro' ? 6000 : 3500)
  }, [])

  useEffect(() => {
    if (pedido) botaoSim.current?.focus()
  }, [pedido])

  return (
    <ConfirmarCtx.Provider value={confirmar}>
      <AvisoCtx.Provider value={avisar}>
        {children}
        {pedido && (
          <Modal aoFechar={() => responder(false)}>
            <h2>{pedido.titulo}</h2>
            {pedido.mensagem && <p>{pedido.mensagem}</p>}
            <div className="acoes">
              <button className="btn" onClick={() => responder(false)}>
                {pedido.nao ?? 'Não'}
              </button>
              <button ref={botaoSim} className={`btn ${pedido.perigo ? 'btn-perigo-cheio' : 'btn-primario'}`} onClick={() => responder(true)}>
                {pedido.sim ?? 'Sim'}
              </button>
            </div>
          </Modal>
        )}
        <div className="avisos" aria-live="polite">
          {avisos.map((a) => (
            <div key={a.id} className={`aviso ${a.tipo === 'erro' ? 'erro' : ''}`}>
              {a.texto}
            </div>
          ))}
        </div>
      </AvisoCtx.Provider>
    </ConfirmarCtx.Provider>
  )
}

/** Adia a atualização de um valor (para buscas enquanto o usuário digita). */
export function useAtrasado<T>(valor: T, ms = 300): T {
  const [v, setV] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setV(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return v
}
