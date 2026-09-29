import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { api, definirAoExpirar, type Usuario } from './api'

interface Sessao {
  usuario: Usuario | null
  carregando: boolean
  entrar: (email: string, senha: string) => Promise<void>
  sair: () => Promise<void>
}

const SessaoCtx = createContext<Sessao>(null as unknown as Sessao)
export const useSessao = () => useContext(SessaoCtx)

export function ProvedorSessao({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null)
  const [carregando, setCarregando] = useState(true)

  useEffect(() => {
    definirAoExpirar(() => setUsuario(null))
    api<Usuario>('/auth/me')
      .then(setUsuario)
      .catch(() => setUsuario(null))
      .finally(() => setCarregando(false))
  }, [])

  const entrar = useCallback(async (email: string, senha: string) => {
    setUsuario(await api<Usuario>('/auth/login', { metodo: 'POST', corpo: { email, senha } }))
  }, [])

  const sair = useCallback(async () => {
    await api('/auth/logout', { metodo: 'POST' }).catch(() => {})
    setUsuario(null)
  }, [])

  return <SessaoCtx.Provider value={{ usuario, carregando, entrar, sair }}>{children}</SessaoCtx.Provider>
}
