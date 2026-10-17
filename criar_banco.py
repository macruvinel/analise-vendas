"""Cria e popula um banco SQLite de exemplo para vendas pela internet."""

import random
import sqlite3
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path


CAMINHO_BANCO = Path(__file__).with_name("vendas.db")


def criar_tabelas(conexao: sqlite3.Connection) -> None:
    """Cria as tabelas de produtos, clientes, compras e itens de compra."""
    conexao.executescript(
        """
        CREATE TABLE IF NOT EXISTS tb_produto (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            categoria TEXT NOT NULL,
            preco REAL NOT NULL CHECK (preco >= 0)
        );

        CREATE TABLE IF NOT EXISTS tb_cliente (
            id INTEGER PRIMARY KEY,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            idade INTEGER NOT NULL CHECK (idade >= 18),
            bairro TEXT NOT NULL,
            cidade TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS td_compra (
            id INTEGER PRIMARY KEY,
            dt_compra TEXT NOT NULL,
            id_cliente INTEGER NOT NULL,
            valor_total REAL NOT NULL CHECK (valor_total >= 0),
            FOREIGN KEY (id_cliente) REFERENCES tb_cliente (id)
        );

        CREATE TABLE IF NOT EXISTS tb_item_compra (
            id INTEGER PRIMARY KEY,
            id_compra INTEGER NOT NULL,
            id_produto INTEGER NOT NULL,
            quantidade INTEGER NOT NULL CHECK (quantidade > 0),
            FOREIGN KEY (id_compra) REFERENCES td_compra (id),
            FOREIGN KEY (id_produto) REFERENCES tb_produto (id),
            UNIQUE (id_compra, id_produto)
        );

        CREATE INDEX IF NOT EXISTS idx_compra_cliente
            ON td_compra (id_cliente);
        CREATE INDEX IF NOT EXISTS idx_item_compra_compra
            ON tb_item_compra (id_compra);
        CREATE INDEX IF NOT EXISTS idx_item_compra_produto
            ON tb_item_compra (id_produto);
        """
    )


def popular_tabelas(conexao: sqlite3.Connection) -> None:
    """Insere dados de exemplo de forma reproduzível e segura para reexecução."""
    aleatorio = random.Random(2026)
    categorias = [
        "Eletrônicos",
        "Casa",
        "Livros",
        "Esporte",
        "Moda",
        "Beleza",
        "Brinquedos",
        "Papelaria",
    ]
    produtos = [
        (
            produto_id,
            f"Produto {produto_id:03}",
            categorias[(produto_id - 1) % len(categorias)],
            aleatorio.randint(599, 250000) / 100,
        )
        for produto_id in range(1, 121)
    ]
    nomes = [
        "Ana", "Bruno", "Carla", "Diego", "Elisa", "Felipe",
        "Gabriela", "Heitor", "Isabela", "João", "Karen", "Lucas",
    ]
    sobrenomes = [
        "Almeida", "Barbosa", "Costa", "Dias", "Esteves", "Freitas",
        "Gomes", "Lima", "Mendes", "Nunes", "Oliveira", "Pereira",
    ]
    bairros = [
        "Centro", "Jardim América", "Vila Nova", "Santa Clara",
        "Boa Vista", "São José",
    ]
    cidades = [
        "São Paulo", "Campinas", "Curitiba", "Recife",
        "Belo Horizonte", "Porto Alegre",
    ]
    clientes = [
        (
            cliente_id,
            f"{nomes[(cliente_id - 1) % len(nomes)]} "
            f"{sobrenomes[(cliente_id - 1) // len(nomes)]}",
            f"cliente{cliente_id:03}@exemplo.com",
            aleatorio.randint(18, 80),
            bairros[(cliente_id - 1) % len(bairros)],
            cidades[(cliente_id - 1) % len(cidades)],
        )
        for cliente_id in range(1, 121)
    ]

    conexao.executemany(
        """
        INSERT OR IGNORE INTO tb_produto (id, nome, categoria, preco)
        VALUES (?, ?, ?, ?)
        """,
        produtos,
    )
    conexao.executemany(
        """
        INSERT OR IGNORE INTO tb_cliente (id, nome, email, idade, bairro, cidade)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        clientes,
    )

    precos_em_centavos = {
        produto_id: round(preco * 100) for produto_id, _, _, preco in produtos
    }
    data_inicial = date(2025, 1, 1)
    itens = []
    proximo_id_item = 1
    for compra_id in range(1, 241):
        quantidade_produtos = aleatorio.randint(1, 4)
        produtos_escolhidos = aleatorio.sample(range(1, 121), quantidade_produtos)
        itens_compra = [
            (produto_id, aleatorio.randint(1, 5))
            for produto_id in produtos_escolhidos
        ]
        total_centavos = sum(
            precos_em_centavos[produto_id] * quantidade
            for produto_id, quantidade in itens_compra
        )
        dt_compra = data_inicial + timedelta(days=aleatorio.randint(0, 364))
        conexao.execute(
            """
            INSERT OR IGNORE INTO td_compra (id, dt_compra, id_cliente, valor_total)
            VALUES (?, ?, ?, ?)
            """,
            (
                compra_id,
                dt_compra.isoformat(),
                aleatorio.randint(1, 120),
                total_centavos / 100,
            ),
        )
        for produto_id, quantidade in itens_compra:
            itens.append((proximo_id_item, compra_id, produto_id, quantidade))
            proximo_id_item += 1

    conexao.executemany(
        """
        INSERT OR IGNORE INTO tb_item_compra (id, id_compra, id_produto, quantidade)
        VALUES (?, ?, ?, ?)
        """,
        itens,
    )


def criar_banco(caminho: Path = CAMINHO_BANCO) -> None:
    """Cria o banco SQLite no caminho informado e popula as tabelas de exemplo."""
    with closing(sqlite3.connect(caminho)) as conexao:
        with conexao:
            conexao.execute("PRAGMA foreign_keys = ON")
            criar_tabelas(conexao)
            popular_tabelas(conexao)


def main() -> None:
    """Gera o banco de vendas e mostra a quantidade de registros por tabela."""
    criar_banco()
    with closing(sqlite3.connect(CAMINHO_BANCO)) as conexao:
        for tabela in (
            "tb_produto",
            "tb_cliente",
            "td_compra",
            "tb_item_compra",
        ):
            total = conexao.execute(
                f"SELECT COUNT(*) FROM {tabela}"
            ).fetchone()[0]
            print(f"{tabela}: {total} registros")
    print(f"Banco criado em: {CAMINHO_BANCO}")


if __name__ == "__main__":
    main()
