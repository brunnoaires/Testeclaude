/**
 * Formulario de pesquisa falso, de tres paginas, usado para testar o motor
 * de preenchimento sem tocar em nenhum site real.
 *
 *   node test/mock-survey.js [porta]
 */

import http from 'node:http';

const shell = (title, body) => `<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><title>${title}</title>
<style>body{font-family:system-ui;margin:40px;max-width:680px}
fieldset{border:1px solid #ccc;margin:18px 0;padding:12px}
legend{font-weight:600}label{display:block;margin:4px 0}
button{padding:10px 18px;font-size:15px;margin-top:16px}
.erro{color:#b00;font-weight:600}</style></head>
<body>${body}</body></html>`;

const likert = (name, legend, options) => `
<fieldset>
  <legend>${legend}</legend>
  ${options
    .map(
      (o, i) =>
        `<label><input type="radio" name="${name}" value="${i}" required> ${o}</label>`
    )
    .join('\n  ')}
</fieldset>`;

const NEG_TO_POS = ['Muito insatisfeito', 'Insatisfeito', 'Neutro', 'Satisfeito', 'Muito satisfeito'];
const POS_TO_NEG = ['Concordo totalmente', 'Concordo', 'Neutro', 'Discordo', 'Discordo totalmente'];

const pages = {
  '/': () =>
    shell(
      'Pesquisa — inicio',
      `<h1>Pesquisa de satisfacao (simulada)</h1>
     <form method="POST" action="/p2">
       <label>CNPJ <input type="text" name="cnpj" required></label>
       <label>Numero do pedido <input type="text" name="pedido" required></label>
       <label>Valor da compra <input type="text" name="valor"></label>
       <button type="submit">Continuar</button>
     </form>`
    ),

  '/p2': () =>
    shell(
      'Pesquisa — pagina 2',
      `<h1>Sobre sua visita</h1>
     <form method="POST" action="/p3">
       ${likert('q1', 'Qual seu nivel de satisfacao com o atendimento?', NEG_TO_POS)}
       ${likert('q2', 'Qual seu nivel de satisfacao com a limpeza do restaurante?', NEG_TO_POS)}
       ${likert('q3', 'Qual seu nivel de satisfacao com a rapidez do servico?', NEG_TO_POS)}
       <button type="submit">Proximo</button>
     </form>`
    ),

  '/p3': () =>
    shell(
      'Pesquisa — pagina 3',
      `<h1>Ultimas perguntas</h1>
     <form method="POST" action="/fim">
       ${likert('q4', 'O pedido saiu como voce esperava?', POS_TO_NEG)}
       <fieldset>
         <legend>Qual foi o tipo de atendimento?</legend>
         <label><input type="radio" name="canal" value="balcao" required> Balcão</label>
         <label><input type="radio" name="canal" value="drive"> Drive-thru</label>
         <label><input type="radio" name="canal" value="totem"> Totem</label>
       </fieldset>
       <label>Comentario (opcional)<br><textarea name="obs" rows="4" cols="50"></textarea></label>
       <button type="submit">Enviar</button>
     </form>`
    ),

  '/fim': () =>
    shell(
      'Pesquisa — obrigado',
      `<h1>Obrigado pela sua participacao!</h1>
     <p>Seu codigo de validacao e <strong>TESTE-1234</strong>.</p>`
    ),
};

const port = Number(process.argv[2] || 8787);

http
  .createServer((req, res) => {
    const path = new URL(req.url, `http://localhost:${port}`).pathname;
    const render = pages[path];
    if (!render) {
      res.writeHead(404, { 'content-type': 'text/plain' });
      return res.end('nao encontrado');
    }
    // Formularios navegam por POST; o corpo e descartado, isto e so um mock.
    let body = '';
    req.on('data', (c) => (body += c));
    req.on('end', () => {
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' });
      res.end(render());
    });
  })
  .listen(port, () => {
    console.log(`mock-survey em http://localhost:${port}/`);
  });
