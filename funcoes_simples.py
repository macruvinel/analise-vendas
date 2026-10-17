"""Calcula juros compostos e valor presente líquido (VPL)."""


# Calcula e retorna o montante com juros compostos.
def calcular_juros_compostos(capital: float, taxa: float, periodos: int) -> float:
    return capital * (1 + taxa) ** periodos


# Calcula o VPL com os fluxos ordenados do período zero em diante.
def calcular_vpl(taxa: float, fluxos_caixa: list[float]) -> float:
    if not fluxos_caixa:
        raise ValueError("Informe ao menos um fluxo de caixa.")
    if taxa <= -1:
        raise ValueError("A taxa de desconto deve ser maior que -100%.")

    return sum(
        fluxo / (1 + taxa) ** periodo
        for periodo, fluxo in enumerate(fluxos_caixa)
    )


# Solicita os dados, executa os dois cálculos e exibe os resultados.
def main() -> None:
    capital = float(input("Capital inicial: "))
    taxa_juros = float(input("Taxa de juros por período (%): ")) / 100
    periodos = int(input("Número de períodos: "))
    if capital < 0 or taxa_juros <= -1 or periodos < 0:
        raise ValueError(
            "Capital e períodos não podem ser negativos; a taxa deve ser maior que -100%."
        )

    montante = calcular_juros_compostos(capital, taxa_juros, periodos)
    print(f"Montante com juros compostos: {montante:.2f}")
    print(f"Juros acumulados: {montante - capital:.2f}")

    taxa_desconto = float(input("Taxa de desconto para o VPL (%): ")) / 100
    entradas = input(
        "Fluxos de caixa separados por vírgula (inclua o investimento inicial primeiro): "
    )
    fluxos_caixa = [float(valor.strip()) for valor in entradas.split(",")]
    vpl = calcular_vpl(taxa_desconto, fluxos_caixa)
    print(f"VPL: {vpl:.2f}")


# Executa a função principal se o arquivo for executado diretamente.
if __name__ == "__main__":
    main()
