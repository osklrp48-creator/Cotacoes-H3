import { lazy, StrictMode, Suspense } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { ProvedorSessao, useSessao } from './auth'
import Layout from './componentes/Layout'
import { Carregando, ProvedorUI } from './componentes/ui'
import Admin from './paginas/Admin'
import FornecedorFicha from './paginas/FornecedorFicha'
import Fornecedores from './paginas/Fornecedores'
import Login from './paginas/Login'
import Produtos from './paginas/Produtos'
import RegistroForm from './paginas/RegistroForm'
import Registros from './paginas/Registros'
import './estilos.css'

// O detalhe do produto usa a biblioteca de gráficos; carrega só quando for aberto.
const ProdutoDetalhe = lazy(() => import('./paginas/ProdutoDetalhe'))

function Rotas() {
  const { usuario, carregando } = useSessao()
  if (carregando) return <Carregando />
  if (!usuario) return <Login />
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Registros />} />
        <Route path="registros/novo" element={<RegistroForm key="novo" />} />
        <Route path="registros/:id" element={<RegistroForm />} />
        <Route path="produtos" element={<Produtos />} />
        <Route
          path="produtos/ver"
          element={
            <Suspense fallback={<Carregando />}>
              <ProdutoDetalhe />
            </Suspense>
          }
        />
        <Route path="fornecedores" element={<Fornecedores />} />
        <Route path="fornecedores/:id" element={<FornecedorFicha />} />
        {usuario.perfil === 'admin' && <Route path="admin" element={<Admin />} />}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <ProvedorUI>
        <ProvedorSessao>
          <Rotas />
        </ProvedorSessao>
      </ProvedorUI>
    </BrowserRouter>
  </StrictMode>,
)
