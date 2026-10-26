# Limitações e próximos passos

O que o projeto ainda não faz, o que não foi possível verificar e o que vem a seguir.

[← Voltar ao README](../README.md)

## Limitações conhecidas

Estas são limitações reais do projeto como entregue, não promessas futuras.

- **Verificação parcial.** O código foi escrito num ambiente sem acesso à internet aberta. Por isso, **nunca foi testado contra a RAWG de verdade** (apenas contra simulações fiéis ao formato documentado: confira os formatos de campos como `results`, `rating`, `released` com sua chave antes de publicar) e o **waitress** não foi iniciado. O que já foi confirmado fora desse ambiente: o CI do GitHub executa `npm ci`, `npm test`, o build de produção do Vite e os testes de navegador sobre esse build (Ubuntu, Node 22), e o back-end passa em Python 3.11 e 3.13.
- **Cache da RAWG e limite de requisições ficam na memória do processo.** Reiniciar o app os esvazia, e **mais de um processo** (vários workers) teria contagens e caches separados. Para escalar além de um processo, troque por Redis ou similar.
- **SQLite** atende bem uma instância única; não é pensado para várias máquinas escrevendo no mesmo arquivo.
- **Enviar uma foto grande usa bastante memória por alguns instantes.** Um PNG de 25 megapixels pesa poucos KB, mas ocupa uns 170 MB ao ser decodificado. O limite de requisições por IP reduz o risco; numa hospedagem com pouca memória, diminua `MAX_PIXELS` em `backend/app/services/avatars.py` (fotos de celular de 12 megapixels cabem com folga em 16 milhões).
- **Fotos de perfil** ficam no próprio banco (pequenas, mas cada troca é uma gravação). O recorte é sempre um quadrado central: a pessoa não escolhe o enquadramento. O Pillow precisa estar instalado (vem no `requirements.txt`); sem ele, o envio responde que está indisponível e o resto do site funciona.
- **Sem troca nem recuperação de senha, sem verificação de e-mail e sem notificações**: o projeto não envia e-mails e a tela de configurações só edita nome, bio e foto, além de excluir a conta.
- **Sem moderação** (denunciar, bloquear, ocultar reviews). Antes de abrir o cadastro ao público, planeje isso.
- **A exclusão de conta é imediata e definitiva**: não há prazo para desistir, nem exportação dos dados antes, nem e-mail de confirmação. Cópias de segurança do banco feitas antes continuam com os dados.
- **Jogadas anteriores só podem ser excluídas**, não editadas, e não têm plataforma nem horas jogadas; a jogada atual continua sendo editada nas datas do diário.
- **O aviso de spoilers é uma marcação de quem escreve**: o servidor devolve o texto na resposta da API (quem quiser lê-lo por lá pode), e só o feed e a busca o omitem.
- **A prévia de links só existe quando o Flask serve o site** (o build). No `npm run dev`, o Vite entrega o HTML e não há prévia. Os aplicativos que mostram a prévia (WhatsApp, Discord, LinkedIn) só leem endereços públicos e guardam o resultado por um tempo, então uma mudança no perfil ou na lista pode demorar a aparecer lá, mesmo com a imagem já atualizada no servidor. A prévia de um jogo só tem título e capa se o servidor já conhece o jogo (alguém o registrou ou a página dele foi aberta há pouco); do contrário, mostra a prévia padrão, porque a prévia nunca chama a RAWG. Nunca foi conferido como cada um desses aplicativos desenha a prévia.
- **Nas imagens de compartilhamento, nomes e bios com emoji ou outros alfabetos** (japonês, árabe, russo, algumas letras latinas raras...) **não são desenhados**: as fontes embutidas só cobrem o alfabeto latino. O cartão do perfil mostra o `@usuario`, e a bio é omitida. O texto da página e a prévia em texto continuam normais.
- **O ranking "Mais bem avaliados" começa vazio.** Ele exige notas de três pessoas diferentes para o mesmo jogo, então num site novo, com poucas pessoas, a página mostra a explicação da regra por um bom tempo. É de propósito: preferimos não anunciar "o melhor jogo da comunidade" com base em uma única nota.
- **As capas dos jogos são recortes de imagens horizontais.** A RAWG entrega uma imagem larga (em geral uma captura de tela), não um pôster; o site a recorta no centro para caber nos cartões. Jogos cujo centro da imagem não mostra nada de reconhecível ficam com uma capa menos bonita. Nunca foi conferido com as imagens reais da RAWG.
- **A retrospectiva não tem gêneros nem horas jogadas**, porque o app não guarda esses dados. As datas de início e término são as do fuso de quem joga; notas, curtidas, seguidores e o histórico do diário têm hora em UTC, então algo feito bem na virada do ano pode cair no ano vizinho. A lista de zerados mostra até 12 jogos, dos de maior nota para os sem nota, e o ritmo só aparece com pelo menos dois zerados que tenham as duas datas.
- **Capas e imagens** são carregadas da CDN da RAWG, que impõe a própria política de uso; o site não as copia nem as redimensiona.
- **Sem internacionalização**: a interface está só em português do Brasil.
- **Sem testes automatizados de acessibilidade completos**: a auditoria feita foi manual (teclado, leitor de tela em estrutura, contraste) e por inspeção do DOM. Faça uma revisão com tecnologias assistivas reais antes de publicar.

## Próximos passos

Ideias priorizadas para as próximas versões (nenhuma está implementada; as jogadas, o aviso de spoilers, a foto enviada, a exclusão de conta, a prévia de links e a retrospectiva do ano já fazem parte da versão atual):

1. **Conta completa:** troca e recuperação de senha por e-mail, verificação de e-mail e exportação dos próprios dados antes de excluir a conta.
2. **Moderação:** denunciar e ocultar reviews, bloquear usuários.
3. **Diário mais fiel ao hábito de jogar:** editar jogadas anteriores, plataforma e horas por jogada e uma review por jogada.
4. **Retrospectiva e compartilhamento mais ricos:** gêneros e horas jogadas (exigem guardar esses dados por jogada), comparação com o ano anterior, imagens com mais conteúdo e suporte a nomes em outros alfabetos (fontes extras).
5. **Comunidade:** notificações, comentários em reviews e listas, importação da biblioteca da Steam.
6. **Escala:** cache e limite de requisições compartilhados entre processos, busca de texto nas reviews e, se necessário, outro banco no lugar do SQLite.
