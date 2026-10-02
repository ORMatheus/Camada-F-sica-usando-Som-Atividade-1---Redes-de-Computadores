# SPDX-License-Identifier: MIT
# Copyright (c) 2026 <nomes da equipe>
# Camada Física usando Som - Atividade 1 de Redes de Computadores
"""Constantes compartilhadas pelo emissor e pelo receptor.
 
Ficam num lugar só para que emissor e receptor nunca discordem do ritmo.
Ajuste INTERVALO_BATIDAS e SILENCIO_BITS.
"""
 
# Áudio
TAXA_AMOSTRAGEM = 44100                                      # amostras por segundo
DURACAO_JANELA = 0.010                                       # 10 ms
AMOSTRAS_POR_JANELA = int(TAXA_AMOSTRAGEM * DURACAO_JANELA)  # 441
 
# Ritmo do Método 1 
INTERVALO_BATIDAS = 0.25  # s, entre as 2 batidas de um bit 1
SILENCIO_BITS = 0.8       # s, da última batida de um bit até a 1ª batida do próximo
 
# Receptor do Método 1
LIMITE_GRUPO = (INTERVALO_BATIDAS + SILENCIO_BITS) / 2  # "ainda é o mesmo bit?"
PERIODO_REFRATARIO = 0.08                               # "ainda é a mesma batida?"
TIMEOUT_QUADRO = 2.0                                    # descarta quadro incompleto

# Emissor do Método 1
PAUSA_ENTRE_QUADROS = TIMEOUT_QUADRO + 0.5  # s, garante que o receptor feche o quadro anterior

# Detector de batidas do Método 1
LIMIAR_MINIMO = 0.01   # RMS mínimo (sinal entre -1 e 1) para algo contar como batida
FATOR_LIMIAR = 4.0     # batida = RMS da janela > FATOR_LIMIAR * ruído de fundo
JANELAS_RUIDO = 100    # janelas (100 x 10 ms = 1 s) usadas para estimar o ruído de fundo
JANELAS_AQUECIMENTO = 10        # primeiras janelas (100 ms) só medem o ruído, sem detectar
DURACAO_MAXIMA_BATIDA = 0.3     # s; som alto por mais tempo que isso é ruído, não batida
FATOR_SUBIDA = 2.0     # batida = janela pelo menos 2x mais forte que a de 20 ms atrás


