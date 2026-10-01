/**
 * Logo da H3 Pharma. No tema escuro usa a versão com o verde-escuro trocado por claro (troca via CSS).
 * "empilhada": símbolo em cima do nome (tela de login). "horizontal": símbolo ao lado do nome (cabeçalho).
 */
function Par({ claro, escuro, altura }: { claro: string; escuro: string; altura: number }) {
  return (
    <span className="logo-h3" style={{ height: altura }}>
      <img src={claro} alt="" className="logo-tema-claro" />
      <img src={escuro} alt="" className="logo-tema-escuro" />
    </span>
  )
}

export default function LogoH3({ altura = 32, formato = 'horizontal' }: { altura?: number; formato?: 'horizontal' | 'empilhada' }) {
  if (formato === 'empilhada') {
    return (
      <span role="img" aria-label="H3 Pharma">
        <Par claro="/logo-h3.svg" escuro="/logo-h3-escuro.svg" altura={altura} />
      </span>
    )
  }
  return (
    <span className="logo-horizontal" role="img" aria-label="H3 Pharma">
      <Par claro="/simbolo.svg" escuro="/simbolo-escuro.svg" altura={altura} />
      <Par claro="/logo-texto.svg" escuro="/logo-texto-escuro.svg" altura={Math.round(altura * 0.6)} />
    </span>
  )
}
