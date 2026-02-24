Quero um programa em python que use QT5 e QMainWindow que me ajude a prender a pronunciar idiomas

* Escolhes um texto txt e carrego ele no string DATA e defines/indicas qual é o idioma do texto.
* Separas string por {",","\n",";","."} e se esta é menor a MAX_LENGTH, se o texto dividido supera  MAX_LENGTH, este obligatoriamente se divide em varios strings menores a MAX_LENGTH porem nao se cortam palavras so se pode cortar em blank spaces. Assmi no final o texto é separado em um lista de strings TEXT_LIST que se o concateno obtenho o mesmo string DATA.
* O programa vai me apresentar cada string TEXTO_REAL e vai me pedir leer e gravar o a leitura.
* O programa tem um botao para converter o TEXTO_REAL a audio (funcao fake, eu farei isso a mao depois, so faz um print("text to audio unimplemnted"))
* O programa tem um botao para gravar num arquivo de audio (cria um arquivo em temp usando a biblioteca de python).
* O programa tem um botao para ouvir o audio gravado.
* O programa tem um botao que envia o arquivo de audio a uma funcao que converte o audio a texto na string TEXTO_PRED(nao faças esta funcao deixa ela como dummy, eu farei essa funcao depois a mao, so faz que retorne um texto fixo para testar). O programa compara TEXTO_PRED e TEXTO_REAL, aqui nao sei como fazer afuncao comparar pois imaginemos que esqueco falar uma lavara deveria ser so um pequeno error ne? mas se comparo palavra por palavra em ordem isto pode dar error so pela posicao, poderia compara a frase como set nao como list, mas naos ei se esta seria a melhor opcao pois a ordem importa tambem ... Aceito sugerencias.
* Se eu quiser posso repetir as tentativas  de reconhecimento varias vezes, ou seja gravar de nuevo enviar e pontuar, quandod esistir presiono o botao "next" o meu melhor pontuacao é acumulado (numero de palavras acertadas) e se passa a oferecer a seguinte frase TEXTO_REAL.
* No final, quando todas as frases foram testadas, se conta a quantidade de palavras acertadas sobre a palavras totais e se da uma pontuacao

