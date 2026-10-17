"""Testes HTTP para os endpoints de análise de vendas."""

import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from fastapi.testclient import TestClient

from api import criar_app
from criar_banco import criar_banco


class TestApiVendas(unittest.TestCase):
    """Valida filtros, agregações e ordenações da API com banco de teste."""

    def setUp(self) -> None:
        """Cria um banco isolado e inicia o cliente HTTP para cada teste."""
        self.diretorio = tempfile.TemporaryDirectory()
        self.caminho_banco = Path(self.diretorio.name) / "vendas.db"
        criar_banco(self.caminho_banco)
        self.cliente = TestClient(criar_app(self.caminho_banco))
        self.cliente.__enter__()

    def tearDown(self) -> None:
        """Fecha o cliente HTTP e remove o banco temporário do teste."""
        self.cliente.__exit__(None, None, None)
        self.diretorio.cleanup()

    def test_resumo_vendas_filtra_por_cliente_valor_e_data(self) -> None:
        """Confirma que os filtros combinados limitam as compras retornadas."""
        resposta = self.cliente.get(
            "/resumo-vendas",
            params={
                "cliente_id": 1,
                "valor_minimo": 0,
                "valor_maximo": 100000,
                "data_inicio": "2025-01-01",
                "data_fim": "2025-12-31",
            },
        )

        self.assertEqual(resposta.status_code, 200)
        resultado = resposta.json()
        self.assertGreater(resultado["quantidade_compras"], 0)
        for compra in resultado["compras"]:
            self.assertEqual(compra["id_cliente"], 1)
            self.assertLessEqual(compra["valor_total"], 100000)

    def test_resumo_vendas_rejeita_intervalos_invalidos(self) -> None:
        """Retorna erro de validação para filtros contraditórios."""
        resposta = self.cliente.get(
            "/resumo-vendas",
            params={"valor_minimo": 200, "valor_maximo": 100},
        )
        self.assertEqual(resposta.status_code, 422)

        resposta_datas = self.cliente.get(
            "/analise-compras",
            params={"data_inicio": "2025-12-31", "data_fim": "2025-01-01"},
        )
        self.assertEqual(resposta_datas.status_code, 422)

    def test_analise_clientes_filtra_por_localidade_e_gasto(self) -> None:
        """Filtra clientes pela localidade e pelos valores agregados de compra."""
        resposta = self.cliente.get(
            "/analise-clientes",
            params={
                "cidade": "São Paulo",
                "bairro": "Centro",
                "quantidade_compras_min": 1,
                "valor_compra_min": 0,
                "limite": 1,
            },
        )

        self.assertEqual(resposta.status_code, 200)
        resultado = resposta.json()
        clientes = resultado["clientes"]
        self.assertGreater(resultado["quantidade_clientes"], len(clientes))
        self.assertEqual(len(clientes), 1)
        for cliente in clientes:
            self.assertEqual(cliente["cidade"], "São Paulo")
            self.assertEqual(cliente["bairro"], "Centro")
            self.assertGreaterEqual(cliente["quantidade_compras"], 1)

    def test_analise_produtos_ordena_potencial(self) -> None:
        """Confirma os rankings de produtos por faturamento."""
        resposta = self.cliente.get("/analise-produtos", params={"limite": 5})

        self.assertEqual(resposta.status_code, 200)
        resultado = resposta.json()
        melhores = resultado["maior_potencial"]
        piores = resultado["menor_potencial"]
        self.assertEqual(len(melhores), 5)
        self.assertEqual(len(piores), 5)
        self.assertGreaterEqual(
            melhores[0]["faturamento_total"],
            melhores[-1]["faturamento_total"],
        )
        with closing(sqlite3.connect(self.caminho_banco)) as conexao:
            total_produtos = conexao.execute(
                "SELECT COUNT(*) FROM tb_produto"
            ).fetchone()[0]
        self.assertEqual(total_produtos, 120)

    def test_api_cria_banco_ao_iniciar_quando_arquivo_nao_existe(self) -> None:
        """Inicializa e popula um banco ausente no primeiro acesso à API."""
        caminho_novo = Path(self.diretorio.name) / "novo.db"
        with TestClient(criar_app(caminho_novo)) as cliente:
            resposta = cliente.get("/analise-produtos", params={"limite": 1})

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(caminho_novo.exists())
        with closing(sqlite3.connect(caminho_novo)) as conexao:
            total_produtos = conexao.execute(
                "SELECT COUNT(*) FROM tb_produto"
            ).fetchone()[0]
        self.assertEqual(total_produtos, 120)

    def test_analise_compras_respeita_periodo_e_conta_clientes_distintos(
        self,
    ) -> None:
        """Compara a agregação da API com o intervalo consultado no SQLite."""
        resposta = self.cliente.get(
            "/analise-compras",
            params={"data_inicio": "2025-01-01", "data_fim": "2025-01-31"},
        )

        self.assertEqual(resposta.status_code, 200)
        with closing(sqlite3.connect(self.caminho_banco)) as conexao:
            esperado = conexao.execute(
                """
                SELECT COUNT(*), COUNT(DISTINCT id_cliente), ROUND(SUM(valor_total), 2)
                FROM td_compra
                WHERE dt_compra BETWEEN ? AND ?
                """,
                ("2025-01-01", "2025-01-31"),
            ).fetchone()
        self.assertEqual(resposta.json()["quantidade_compras"], esperado[0])
        self.assertEqual(resposta.json()["quantidade_clientes"], esperado[1])
        self.assertEqual(resposta.json()["valor_total"], esperado[2])


if __name__ == "__main__":
    unittest.main()
