import { NavLink, Outlet } from 'react-router-dom'
import { useSessao } from '../auth'
import { useTema } from '../tema'
import { Icone } from './ui'

export default function Layout() {
  const { usuario, sair } = useSessao()
  const { tema, alternar } = useTema()
  return (
    <>
      <header className="topo">
        <div className="topo-linha">
          <NavLink to="/" className="marca">
            <span className="marca-logo">H3</span>
            Cotações H3
          </NavLink>
          <nav className="abas" aria-label="Principal">
            <NavLink to="/" end>
              Registros
            </NavLink>
            <NavLink to="/produtos">Produtos</NavLink>
            <NavLink to="/fornecedores">Fornecedores</NavLink>
            {usuario?.perfil === 'admin' && <NavLink to="/admin">Admin</NavLink>}
          </nav>
          <div className="topo-acoes">
            <div className="usuario-info">
              <strong>{usuario?.nome}</strong>
              {usuario?.unidade.nome}
            </div>
            <button className="btn btn-icone" onClick={alternar} title={tema === 'claro' ? 'Tema escuro' : 'Tema claro'} aria-label="Alternar tema">
              {tema === 'claro' ? Icone.lua() : Icone.sol()}
            </button>
            <button className="btn btn-icone" onClick={sair} title="Sair" aria-label="Sair">
              {Icone.sair()}
            </button>
          </div>
        </div>
      </header>
      <main className="conteudo">
        <Outlet />
      </main>
    </>
  )
}
