# WMusic Steams

Programa para Windows e Mac que pega uma música (MP3, WAV, FLAC, M4A, MP4, MOV…) e entrega:

- **Stems**: Voz, Bateria, Baixo, Guitarra, Teclas e Outros, separados por IA no seu computador (sem internet).
- **Letra** com o tempo de cada palavra, acendendo na hora em que é cantada.
- **Pad**: um canal novo que acompanha os acordes da música, para servir de base.
- **Acordes e tom** da música na tela, com o próximo acorde.
- **Player multitrack** para ensaio e ao vivo: volume, mute, solo, pan, loop de trecho e saída separada por canal na placa de som (1-2, 3-4…).

## Sem defasagem (o principal)

1. **Leitura certa do arquivo**: o "silêncio de codificador" que MP3, AAC, MP4 e MOV têm no começo é descartado; a amostra 0 é a amostra 0 da música. Nada é reamostrado na leitura.
2. **Soma igual ao original**: depois da separação, o programa mede e corrige qualquer atraso do modelo e fecha a conta no canal "Outros". Todos os stems juntos dão a música original, amostra por amostra (teste de nulo, mostrado no topo da tela).
3. **Um relógio só**: todas as trilhas tocam dentro do mesmo motor de áudio, na mesma posição. Mute, solo e volume mexem só no ganho, nunca no tempo.
4. **Exportação alinhada**: todos os WAV exportados começam no mesmo ponto e têm o mesmo comprimento. Arrastou para a DAW, está em fase.

## Como usar

1. **Nova música** (ou arraste o arquivo para a janela).
2. Escolha a qualidade, o idioma da letra e o timbre do pad. Se quiser, cole a letra: ajuda a acertar as palavras.
3. Espere a separação (alguns minutos por música, dependendo do computador).
4. Toque: barra de espaço toca e pausa; clique na forma de onda para ir a um ponto; arraste para marcar um loop.
5. **Exportar** gera os WAV 24 bits de cada trilha, a letra (.lrc) e os acordes (.txt).

As músicas processadas ficam na pasta **Música / WMusic Steams** e aparecem na **Biblioteca**.

## Instalação

- **Windows com placa NVIDIA**: use o pacote **Windows-NVIDIA** (separação muitas vezes mais rápida). Precisa do driver da NVIDIA atualizado.
- **Windows sem NVIDIA**: use o pacote **Windows** (só processador; os canais extras deixam a separação bem mais lenta).
- Nos dois: descompacte o zip e abra `WMusic Steams.exe`.
- **Mac (Apple Silicon)**: abra o .dmg e arraste para Aplicativos. Na primeira vez, clique com o botão direito no app e em **Abrir** (o app ainda não é assinado pela Apple).

## Créditos (código aberto)

Separação: modelo Hybrid Transformer Demucs de 6 stems (Meta, MIT) pela biblioteca python-audio-separator (MIT). Letra: Whisper small (OpenAI, MIT) com faster-whisper (MIT). Interface: Qt for Python (LGPL). Áudio: PortAudio (MIT), libsndfile (LGPL), FFmpeg (LGPL).

## Licença
- Sem serial, o programa funciona em **teste grátis: separa 3 músicas**. Tocar as músicas já separadas continua livre.
- O botão da chave, no alto da tela, mostra o **código do computador** (ex.: AB12-CD34). Para comprar, o cliente paga no Pix e manda o comprovante e esse código no WhatsApp.
- O serial de venda (`WMST-…`) é feito para aquele computador: não ativa em outro. Para um 2º computador do mesmo cliente, gere outro serial com o mesmo id.
- Serial de **presente**: ilimitado, não vence; pode ou não ser preso a um computador.
- Serial de **beta tester**: tem data de validade (15, 30, 60 ou 90 dias ou uma data); pode ser preso a um computador ou não. Quando vence, o programa volta para o modo teste.
- Gerador: `ferramentas/gerador-celular.html` (celular) ou `ferramentas/gerar_serial.py` (computador). A chave privada fica só com o Heitor, fora do GitHub.
- Cancelar um serial: coloque o id em `REVOGADOS` (`wmsteams/licenca.py`) na próxima versão.
