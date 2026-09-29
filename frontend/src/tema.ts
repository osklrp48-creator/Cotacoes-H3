import { useEffect, useState } from 'react'

export type Tema = 'claro' | 'escuro'

function temaInicial(): Tema {
  const salvo = document.documentElement.dataset.tema
  if (salvo === 'claro' || salvo === 'escuro') return salvo
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'escuro' : 'claro'
}

export function useTema() {
  const [tema, setTema] = useState<Tema>(temaInicial)
  useEffect(() => {
    document.documentElement.dataset.tema = tema
    try {
      localStorage.setItem('tema', tema)
    } catch {
      /* navegação privada: ignora */
    }
  }, [tema])
  return { tema, alternar: () => setTema((t) => (t === 'claro' ? 'escuro' : 'claro')) }
}

