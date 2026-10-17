"""API HTTP para consultas e análises do banco de vendas."""

import os
import sqlite3
from contextlib import asynccontextmanager, closing
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query

from criar_banco import criar_banco


CAMINHO_BANCO = Path(
    os.environ.get("VENDAS_DB_PATH", Path(__file__).with_name("vendas.db"))
)


def consultar(
    caminho_banco: Path,
    sql: str,
    parametros: tuple[Any, ...] = (),
) -> list[dict[str, Any]]:
    """Executa uma consulta parametrizada e devolve as linhas como dicionários."""
    with closing(sqlite3.connect(caminho_banco)) as conexao:
        conexao.row_factory = sqlite3.Row
        return [
            dict(linha)
            for linha in conexao.execute(sql, parametros).fetchall()
        ]


def validar_intervalo_datas(
    data_inicio: date | None,
    data_fim: date | None,
) -> None:
    """Rejeita intervalos de consulta cuja data inicial seja posterior à final."""
    if data_inicio is not None and data_fim is not None and data_inicio > data_fim:
        raise HTTPException(
            status_code=422,
            detail="A data de início não pode ser posterior à data de fim.",
        )


def criar_app(caminho_banco: Path = CAMINHO_BANCO) -> FastAPI:
    """Configura as rotas HTTP e inicializa o banco se ele ainda não existir."""

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        """Gera o banco de exemplo na inicialização se o arquivo estiver ausente."""
        if not caminho_banco.exists():
            caminho_banco.parent.mkdir(parents=True, exist_ok=True)
            criar_banco(caminho_banco)
        yield

    app = FastAPI(
        title="API de Análise de Vendas",
        description=(
            "Consultas e análises de compras, clientes e produtos "
            "armazenados em SQLite."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/resumo-vendas")
    def resumo_vendas(
        valor_minimo: float | None = Query(default=None, ge=0),
        valor_maximo: float | None = Query(default=None, ge=0),
        cliente_id: int | None = Query(default=None, ge=1),
        data_inicio: date | None = None,
        data_fim: date | None = None,
    ) -> dict[str, Any]:
        """Lista compras e totais com filtros por valor, cliente e data."""
        validar_intervalo_datas(data_inicio, data_fim)
        if (
            valor_minimo is not None
            and valor_maximo is not None
            and valor_minimo > valor_maximo
        ):
            raise HTTPException(
                status_code=422,
                detail="O valor mínimo não pode ser maior que o valor máximo.",
            )

        condicoes = []
        parametros: list[Any] = []
        filtros = (
            ("c.valor_total >= ?", valor_minimo),
            ("c.valor_total <= ?", valor_maximo),
            ("c.id_cliente = ?", cliente_id),
            ("c.dt_compra >= ?", data_inicio.isoformat() if data_inicio else None),
            ("c.dt_compra <= ?", data_fim.isoformat() if data_fim else None),
        )
        for condicao, valor in filtros:
            if valor is not None:
                condicoes.append(condicao)
                parametros.append(valor)

        sql = """
            SELECT c.id, c.dt_compra, c.id_cliente, cl.nome AS nome_cliente,
                   c.valor_total
            FROM td_compra c
            JOIN tb_cliente cl ON cl.id = c.id_cliente
        """
        if condicoes:
            sql += " WHERE " + " AND ".join(condicoes)
        sql += " ORDER BY c.dt_compra DESC, c.id DESC"

        compras = consultar(caminho_banco, sql, tuple(parametros))
        valor_total = sum(compra["valor_total"] for compra in compras)
        return {
            "quantidade_compras": len(compras),
            "valor_total": round(valor_total, 2),
            "ticket_medio": round(valor_total / len(compras), 2) if compras else 0,
            "compras": compras,
        }

    @app.get("/analise-clientes")
    def analise_clientes(
        cidade: str | None = None,
        bairro: str | None = None,
        quantidade_compras_min: int = Query(default=0, ge=0),
        quantidade_compras_max: int | None = Query(default=None, ge=0),
        valor_compra_min: float = Query(default=0, ge=0),
        valor_compra_max: float | None = Query(default=None, ge=0),
        limite: int = Query(default=100, ge=1, le=500),
        deslocamento: int = Query(default=0, ge=0),
    ) -> dict[str, Any]:
        """Resume clientes e filtra por localidade e compras acumuladas."""
        if (
            quantidade_compras_max is not None
            and quantidade_compras_min > quantidade_compras_max
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    "A quantidade mínima de compras não pode exceder "
                    "a quantidade máxima."
                ),
            )
        if valor_compra_max is not None and valor_compra_min > valor_compra_max:
            raise HTTPException(
                status_code=422,
                detail="O valor mínimo não pode ser maior que o valor máximo.",
            )

        condicoes_localidade = []
        parametros_localidade: list[Any] = []
        if cidade is not None:
            condicoes_localidade.append("cl.cidade = ?")
            parametros_localidade.append(cidade)
        if bairro is not None:
            condicoes_localidade.append("cl.bairro = ?")
            parametros_localidade.append(bairro)

        condicoes = [
            "COUNT(DISTINCT co.id) >= ?",
            "COALESCE(SUM(co.valor_total), 0) >= ?",
        ]
        parametros: list[Any] = [
            *parametros_localidade,
            quantidade_compras_min,
            valor_compra_min,
        ]
        if quantidade_compras_max is not None:
            condicoes.append("COUNT(DISTINCT co.id) <= ?")
            parametros.append(quantidade_compras_max)
        if valor_compra_max is not None:
            condicoes.append("COALESCE(SUM(co.valor_total), 0) <= ?")
            parametros.append(valor_compra_max)

        sql = """
            SELECT COUNT(*) OVER() AS total_clientes,
                   cl.id, cl.nome, cl.email, cl.idade, cl.bairro, cl.cidade,
                   COUNT(DISTINCT co.id) AS quantidade_compras,
                   ROUND(COALESCE(SUM(co.valor_total), 0), 2) AS valor_total_compras,
                   ROUND(COALESCE(AVG(co.valor_total), 0), 2) AS ticket_medio
            FROM tb_cliente cl
            LEFT JOIN td_compra co ON co.id_cliente = cl.id
        """
        if condicoes_localidade:
            sql += " WHERE " + " AND ".join(condicoes_localidade)
        sql += (
            " GROUP BY cl.id HAVING "
            + " AND ".join(condicoes)
            + " ORDER BY valor_total_compras DESC, quantidade_compras DESC, cl.id"
            + " LIMIT ? OFFSET ?"
        )
        parametros.extend((limite, deslocamento))

        clientes = consultar(caminho_banco, sql, tuple(parametros))
        quantidade_clientes = clientes[0]["total_clientes"] if clientes else 0
        for cliente in clientes:
            del cliente["total_clientes"]
        return {
            "quantidade_clientes": quantidade_clientes,
            "clientes": clientes,
        }

    @app.get("/analise-produtos")
    def analise_produtos(
        limite: int = Query(default=10, ge=1, le=100),
    ) -> dict[str, Any]:
        """Classifica produtos por faturamento e unidades vendidas."""
        base_sql = """
            SELECT p.id, p.nome, p.categoria, p.preco,
                   COALESCE(SUM(i.quantidade), 0) AS unidades_vendidas,
                   COUNT(DISTINCT i.id_compra) AS quantidade_compras,
                   ROUND(COALESCE(SUM(i.quantidade * p.preco), 0), 2)
                       AS faturamento_total
            FROM tb_produto p
            LEFT JOIN tb_item_compra i ON i.id_produto = p.id
            GROUP BY p.id
        """
        return {
            "criterio_potencial": (
                "Maior potencial: maior faturamento; menor potencial: menor "
                "faturamento. Empates são resolvidos pelas unidades vendidas."
            ),
            "maior_potencial": consultar(
                caminho_banco,
                base_sql
                + " ORDER BY faturamento_total DESC, unidades_vendidas DESC, p.id"
                + " LIMIT ?",
                (limite,),
            ),
            "menor_potencial": consultar(
                caminho_banco,
                base_sql
                + " ORDER BY faturamento_total ASC, unidades_vendidas ASC, p.id"
                + " LIMIT ?",
                (limite,),
            ),
        }

    @app.get("/analise-compras")
    def analise_compras(
        data_inicio: date | None = None,
        data_fim: date | None = None,
    ) -> dict[str, Any]:
        """Resume quantidade de compras, clientes e valores no período."""
        validar_intervalo_datas(data_inicio, data_fim)
        condicoes = []
        parametros: list[Any] = []
        if data_inicio is not None:
            condicoes.append("dt_compra >= ?")
            parametros.append(data_inicio.isoformat())
        if data_fim is not None:
            condicoes.append("dt_compra <= ?")
            parametros.append(data_fim.isoformat())

        sql = """
            SELECT COUNT(*) AS quantidade_compras,
                   COUNT(DISTINCT id_cliente) AS quantidade_clientes,
                   ROUND(COALESCE(SUM(valor_total), 0), 2) AS valor_total,
                   ROUND(COALESCE(AVG(valor_total), 0), 2) AS ticket_medio
            FROM td_compra
        """
        if condicoes:
            sql += " WHERE " + " AND ".join(condicoes)
        return consultar(caminho_banco, sql, tuple(parametros))[0]

    return app


app = criar_app()
