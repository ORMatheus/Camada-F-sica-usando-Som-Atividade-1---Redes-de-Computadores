# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Testes da linha de comando (main.py), sem microfone nem alto-falante.

Usamos só os comandos "simular", que fazem emissor -> ruído -> receptor
dentro do computador. capsys captura o que o programa imprime no terminal.
"""

import numpy as np
import pytest

import main
import metodo1_emissor
import metodo1_receptor
from config import INTERVALO_BATIDAS, PAUSA_ENTRE_QUADROS


# ---------------------------------------------------------------- Método 1

def test_quadros_para_instantes_poe_pausa_entre_quadros():
    # quadro [1]: batidas em 0.0 e INTERVALO_BATIDAS; o próximo começa PAUSA depois da última
    assert metodo1_emissor.quadros_para_instantes([[1], [0]]) == pytest.approx(
        [0.0, INTERVALO_BATIDAS, INTERVALO_BATIDAS + PAUSA_ENTRE_QUADROS])


def test_quadros_para_instantes_sem_quadros():
    assert metodo1_emissor.quadros_para_instantes([]) == []


def test_quadros_juntos_voltam_separados():
    # Se a pausa entre quadros estivesse curta, o receptor juntaria dois quadros num só
    quadros = [[0, 1, 0, 0, 0, 0, 0, 1, 0], [1, 1, 1, 1, 1, 1, 1, 1, 0]]
    instantes = metodo1_emissor.quadros_para_instantes(quadros)
    assert metodo1_receptor.instantes_para_quadros(instantes) == quadros


def test_adicionar_ruido_mantem_tamanho_e_tipo():
    sinal = np.zeros(1000, dtype=np.float32)
    com_ruido = main.adicionar_ruido(sinal, 0.02)
    assert len(com_ruido) == 1000
    assert com_ruido.dtype == np.float32
    assert 0.01 < np.std(com_ruido) < 0.03


def test_simular_metodo1_sucesso(capsys):
    main.executar("m1-simular", texto="Oi")
    saida = capsys.readouterr().out
    assert saida.count("[SUCESSO]") == 2
    assert "FALHA" not in saida
    assert "Texto recebido: 'Oi'" in saida


def test_simular_metodo1_com_erro(capsys):
    main.executar("m1-simular", texto="Oi", erro=True)
    saida = capsys.readouterr().out
    assert "[FALHA DE TRANSMISSÃO]" in saida
    assert "paridade não confere" in saida
    assert "Texto recebido: '?i'" in saida
    assert "1 sucesso(s) / 1 falha(s)" in saida


def test_bit_invalido_conta_como_falha(capsys, monkeypatch):
    # O dado 0100000? com o último bit inválido (-1) ainda tem paridade "certa"
    # para validar_quadro; o resumo tem que contar FALHA mesmo assim.
    quadro_com_bit_invalido = [0, 1, 0, 0, 0, 0, 0, metodo1_receptor.BIT_INVALIDO, 1]
    monkeypatch.setattr(metodo1_receptor, "decodificar_audio",
                        lambda sinal: [quadro_com_bit_invalido])
    main.executar("m1-simular", texto="A")
    saida = capsys.readouterr().out
    assert "bit inválido" in saida
    assert "0 sucesso(s) / 1 falha(s)" in saida
    assert "Texto recebido: '?'" in saida


def test_quadros_perdidos_contam_como_falha(capsys, monkeypatch):
    # Ruído forte demais: o receptor não detecta nada. Não pode sair "0 falha(s)".
    monkeypatch.setattr(metodo1_receptor, "decodificar_audio", lambda sinal: [])
    main.executar("m1-simular", texto="Oi")
    saida = capsys.readouterr().out
    assert "[FALHA DE TRANSMISSÃO] 2 quadro(s)" in saida
    assert "0 sucesso(s) / 2 falha(s)" in saida


def test_metodo1_nao_ascii_da_mensagem_amigavel(capsys):
    main.executar("m1-simular", texto="Olá")  # não pode levantar exceção
    saida = capsys.readouterr().out
    assert "Erro na entrada" in saida
    assert "ASCII" in saida


def test_texto_vazio_da_mensagem_amigavel(capsys):
    for comando in main.COMANDOS_COM_TEXTO:
        main.executar(comando, texto="", erro=True)
        assert "texto está vazio" in capsys.readouterr().out


def test_ruido_negativo_da_mensagem_amigavel(capsys):
    main.executar("m1-simular", texto="A", ruido=-1.0)
    assert "não pode ser negativo" in capsys.readouterr().out


def test_duracao_zero_da_mensagem_amigavel(capsys):
    main.executar("m2-receber", duracao=0.0)
    assert "maior que zero" in capsys.readouterr().out


# ---------------------------------------------------------------- Método 2

def test_simular_metodo2_sucesso_com_acentos(capsys):
    main.executar("m2-simular", texto="Olá, mundo")
    saida = capsys.readouterr().out
    assert "[SUCESSO]" in saida
    assert "Olá, mundo" in saida


def test_simular_metodo2_com_erro(capsys):
    main.executar("m2-simular", texto="Olá, mundo", erro=True)
    saida = capsys.readouterr().out
    assert "[FALHA DE TRANSMISSÃO]" in saida
    assert "[SUCESSO]" not in saida


def test_metodo2_mensagem_grande_demais(capsys):
    main.executar("m2-simular", texto="x" * 300)
    saida = capsys.readouterr().out
    assert "Erro na entrada" in saida
    assert "ASCII" not in saida  # a dica do Método 1 não se aplica aqui


# ---------------------------------------------------------------- Linha de comando e menu

def test_parser_le_opcoes():
    args = main.criar_parser().parse_args(["m1-simular", "Oi", "--erro", "--ruido", "0.05"])
    assert args.comando == "m1-simular"
    assert args.texto == "Oi"
    assert args.erro is True
    assert args.ruido == 0.05


def test_parser_valores_padrao():
    args = main.criar_parser().parse_args(["m2-receber"])
    assert args.duracao == main.DURACAO_RECEPCAO_M2
    args = main.criar_parser().parse_args(["m1-enviar", "A"])
    assert args.guiado is False
    assert args.erro is False


def test_main_pela_linha_de_comando(capsys):
    main.main(["m1-simular", "A"])
    assert "[SUCESSO]" in capsys.readouterr().out


def test_menu_interativo(capsys, monkeypatch):
    # opção inválida, depois simula o Método 1 com "A" (Enter = ruído padrão) e sai
    respostas = iter(["9", "3", "A", "n", "", "0"])
    monkeypatch.setattr("builtins.input", lambda pergunta="": next(respostas))
    main.main([])
    saida = capsys.readouterr().out
    assert "Opção inválida." in saida
    assert "[SUCESSO]" in saida


def test_menu_numero_invalido_usa_padrao(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda pergunta="": "abc")
    assert main.perguntar_numero("Ruído", 0.02) == 0.02
