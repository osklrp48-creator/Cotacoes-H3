import { useState, type FormEvent } from 'react'
import { useSessao } from '../auth'
import { useTema } from '../tema'

export default function Login() {
  const { entrar } = useSessao()
  useTema()
  const [email, setEmail] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState('')
  const [enviando, setEnviando] = useState(false)

  async function enviar(e: FormEvent) {
    e.preventDefault()
    setErro('')
    setEnviando(true)
    try {
      await entrar(email, senha)
    } catch (err) {
      setErro((err as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="login">
      <div className="cartao">
        <div className="marca">
          <span className="marca-logo">H3</span>
          Cotações H3
        </div>
        <p className="fraco" style={{ textAlign: 'center', margin: 0 }}>
          H3 Pharma Comércio e Serviços Ltda.
        </p>
        <form onSubmit={enviar}>
          <label className="campo">
            <span>E-mail</span>
            <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus />
          </label>
          <label className="campo">
            <span>Senha</span>
            <input type="password" autoComplete="current-password" value={senha} onChange={(e) => setSenha(e.target.value)} required />
          </label>
          {erro && <div className="alerta alerta-erro">{erro}</div>}
          <button className="btn btn-primario" disabled={enviando}>
            {enviando ? 'Entrando…' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}
