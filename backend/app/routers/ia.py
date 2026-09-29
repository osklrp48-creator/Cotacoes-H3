from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import usuario_atual
from ..models import UsoIA, Usuario
from ..services.ia import extracao, leitor

router = APIRouter(prefix="/ia", tags=["ia"])


@router.post("/ler-cotacao")
def ler_cotacao(
    arquivo: UploadFile | None = File(default=None),
    texto: str | None = Form(default=None),
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(usuario_atual),
):
    """Lê uma cotação (arquivo ou texto) e devolve os campos para PRÉ-PREENCHER o formulário.

    Nada é salvo em registros: o usuário confere e salva pelo formulário.
    """
    limite_mb = get_settings().ia_max_mb
    try:
        if arquivo is not None and arquivo.filename:
            dados = arquivo.file.read(limite_mb * 1024 * 1024 + 1)
            conteudo = extracao.preparar_arquivo(arquivo.filename, dados, limite_mb)
        elif texto and texto.strip():
            conteudo = extracao.preparar_texto(texto)
        else:
            raise extracao.ArquivoInvalido("Escolha um arquivo ou cole o texto da cotação.")
    except extracao.ArquivoInvalido as exc:
        raise HTTPException(422, str(exc)) from exc

    def registrar_uso(entrada: int, saida: int, sucesso: bool) -> None:
        db.add(
            UsoIA(
                usuario_id=usuario.id,
                unidade_id=usuario.unidade_id,
                tipo_entrada=conteudo.tipo,
                modelo=get_settings().anthropic_model,
                tokens_entrada=entrada,
                tokens_saida=saida,
                sucesso=sucesso,
            )
        )
        db.commit()

    try:
        resultado = leitor.ler_cotacao(conteudo.blocos)
    except leitor.IAIndisponivel as exc:
        if exc.status != 503:  # 503 = IA não configurada/chave inválida: não houve consumo
            registrar_uso(getattr(exc, "tokens_entrada", 0), getattr(exc, "tokens_saida", 0), False)
        raise HTTPException(exc.status, str(exc)) from exc

    registrar_uso(resultado.tokens_entrada, resultado.tokens_saida, True)
    return resultado.dados
