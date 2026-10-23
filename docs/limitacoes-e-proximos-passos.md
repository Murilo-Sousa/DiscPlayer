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
- **Capas e imagens** são carregadas da CDN da RAWG, que impõe a própria política de uso; o site não as copia nem as redimensiona.
- **Sem internacionalização**: a interface está só em português do Brasil.
- **Sem testes automatizados de acessibilidade completos**: a auditoria feita foi manual (teclado, leitor de tela em estrutura, contraste) e por inspeção do DOM. Faça uma revisão com tecnologias assistivas reais antes de publicar.

## Próximos passos

Ideias priorizadas para as próximas versões (nenhuma está implementada; as jogadas, o aviso de spoilers, a foto enviada e a exclusão de conta já fazem parte da versão atual):

1. **Conta completa:** troca e recuperação de senha por e-mail, verificação de e-mail e exportação dos próprios dados antes de excluir a conta.
2. **Moderação:** denunciar e ocultar reviews, bloquear usuários.
3. **Diário mais fiel ao hábito de jogar:** editar jogadas anteriores, plataforma e horas por jogada e uma review por jogada.
4. **Compartilhamento:** prévia (título e capa) ao colar links de jogos, perfis e listas, e uma retrospectiva do ano para compartilhar.
5. **Comunidade:** notificações, comentários em reviews e listas, importação da biblioteca da Steam.
6. **Escala:** cache e limite de requisições compartilhados entre processos, busca de texto nas reviews e, se necessário, outro banco no lugar do SQLite.
