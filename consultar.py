"""Vê AI · Consulta sobre acessibilidade para pessoas com deficiência visual.

    python consultar.py                                  # abre a conversa no terminal
    python consultar.py "Qual a largura mínima da faixa livre?"
    python consultar.py "Qual a largura mínima da faixa livre?" --comparar
"""
from app.consultar import main

if __name__ == "__main__":
    raise SystemExit(main())
