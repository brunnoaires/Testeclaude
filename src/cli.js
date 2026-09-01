#!/usr/bin/env node
/**
 * mcsurvey-assist — preenchimento assistido de formulario de pesquisa.
 *
 * Modelo de uso: o operador roda o comando, acompanha o navegador abrindo,
 * ve cada campo sendo preenchido a partir da sua propria configuracao,
 * preenche a mao o que a ferramenta nao souber, e confirma o envio final
 * no terminal. Uma execucao envia no maximo uma pesquisa.
 */

import { chromium } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { loadConfig } from './config.js';
import { snapshot, fingerprint } from './enumerate.js';
import { fillPage, advance, pickNavButton, short } from './filler.js';
import { confirmSubmit, confirmStep, waitForOperator } from './confirm.js';

const MAX_PAGES = 40;
const DONE = /obrigad|conclu[ií]|finaliz|agradec|thank you|c[oó]digo de valida/i;

function parseArgs(argv) {
  const args = { command: argv[2], config: 'config.json', out: 'runs', headless: false, dryRun: false, step: false };
  for (let i = 3; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--config' || a === '-c') args.config = argv[++i];
    else if (a === '--out' || a === '-o') args.out = argv[++i];
    else if (a === '--url') args.url = argv[++i];
    else if (a === '--headless') args.headless = true;
    else if (a === '--dry-run' || a === '-n') args.dryRun = true;
    else if (a === '--step') args.step = true;
    else if (a === '--help' || a === '-h') args.help = true;
    else throw new Error(`argumento desconhecido: ${a}`);
  }
  return args;
}

function usage() {
  console.log(`
mcsurvey-assist — preenchimento assistido, um envio por execucao

  node src/cli.js inspect [opcoes]   abre o formulario e imprime a estrutura
                                     dos campos de cada pagina, sem preencher
                                     nem enviar nada
  node src/cli.js fill [opcoes]      preenche conforme a config e para no
                                     envio final para voce confirmar

Opcoes:
  -c, --config <arquivo>   caminho da config (padrao: config.json)
  -o, --out <dir>          onde salvar screenshots e logs (padrao: runs/)
      --url <endereco>     sobrescreve a url da config
      --headless           roda sem janela (nao recomendado: voce nao ve o
                           que esta sendo preenchido)
  -n, --dry-run            preenche mas nunca clica no envio final
      --step               pede confirmacao a cada troca de pagina
  -h, --help               esta ajuda

O envio final sempre exige confirmacao digitada no terminal. Nao ha flag para
desativar isso.
`);
}

async function run() {
  const args = parseArgs(process.argv);

  if (args.help || !args.command) {
    usage();
    process.exit(args.command ? 0 : 1);
  }
  if (!['inspect', 'fill'].includes(args.command)) {
    console.error(`comando desconhecido: ${args.command}`);
    usage();
    process.exit(1);
  }

  // O inspect nunca envia, entao ele e um dry-run por construcao.
  if (args.command === 'inspect') args.dryRun = true;

  const config = await loadConfig(args.config);
  const url = args.url || config.url;

  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const outDir = join(args.out, stamp);
  await mkdir(outDir, { recursive: true });

  const lines = [];
  const log = (msg) => {
    console.log(msg);
    lines.push(msg);
  };

  log(`# ${args.command} — ${new Date().toISOString()}`);
  log(`# url: ${url}`);
  if (args.dryRun) log('# modo dry-run: nenhum envio sera feito');

  // Por padrao usa o Chromium que veio com o Playwright. `executablePath` na
  // config (ou MCSA_CHROMIUM no ambiente) aponta para um binario ja instalado,
  // util quando a versao do pacote nao bate com a do browser da maquina.
  const executablePath = config.browser?.executablePath || process.env.MCSA_CHROMIUM || undefined;
  const browser = await chromium.launch({
    headless: args.headless,
    executablePath,
    args: ['--disable-blink-features=AutomationControlled'],
  });
  // Contexto limpo e comum: sem proxy, sem user-agent forjado, sem
  // fingerprint alterado. A requisicao sai com a identidade real da maquina.
  const context = await browser.newContext({
    locale: config.browser?.locale || 'pt-BR',
    viewport: config.browser?.viewport || { width: 1280, height: 900 },
  });
  const page = await context.newPage();

  const summary = [];
  let submitted = false;

  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });
    await page.waitForTimeout(1500);

    for (let n = 1; n <= MAX_PAGES; n++) {
      let snap = await snapshot(page);
      await page.screenshot({ path: join(outDir, `p${String(n).padStart(2, '0')}.png`), fullPage: true });

      log(`\n--- pagina ${n} ---`);
      log(`titulo: ${snap.heading || snap.title || '(sem titulo)'}`);
      log(`campos: ${snap.controls.length} | botoes: ${snap.buttons.length}`);
      if (snap.errors.length) log(`avisos na pagina: ${snap.errors.join(' | ')}`);

      if (args.command === 'inspect') {
        for (const c of snap.controls) {
          log(`  [${c.kind}] ${short(c.question)}${c.required ? ' *' : ''}`);
          if (c.options) {
            for (const o of c.options) log(`      ${o.index}. ${o.label}${o.checked ? '  <- marcado' : ''}`);
          }
          if (c.placeholder) log(`      placeholder: ${c.placeholder}`);
        }
        log(`  botoes: ${snap.buttons.map((b) => `"${b.label}"`).join(', ') || '(nenhum)'}`);
      }

      const finished = DONE.test(snap.heading || '') || DONE.test(snap.title || '');
      if (finished && !snap.controls.length) {
        log('\n[fim] pagina de conclusao detectada.');
        break;
      }

      // O inspect tambem preenche: sem isso as paginas com campo obrigatorio
      // nao avancam e voce so consegue ver a primeira. O que ele nunca faz e
      // clicar num botao classificado como envio.
      const { filled, skipped } = await fillPage(snap.frame, snap, config, log);

      const blocking = skipped.filter((s) => s.kind !== 'checkbox-group');
      if (blocking.length) {
        await waitForOperator(blocking);
        snap = await snapshot(page); // recaptura o que o operador digitou
      }

      summary.push({
        page: n,
        url: snap.url,
        heading: snap.heading,
        filled,
        skipped,
      });

      const button = pickNavButton(snap.buttons);
      if (!button) {
        log('\n[fim] nenhum botao de avanco encontrado nesta pagina.');
        break;
      }

      if (button.kind === 'submit') {
        if (args.dryRun) {
          log(`\n[dry-run] envio final ("${button.label}") nao executado.`);
          break;
        }
        const ok = await confirmSubmit(summary, { buttonLabel: button.label });
        if (!ok) {
          log('\n[cancelado] envio nao confirmado pelo operador. Nada foi enviado.');
          break;
        }
      } else if (args.step) {
        const ok = await confirmStep(button.label);
        if (!ok) {
          log('\n[cancelado] avanco interrompido pelo operador.');
          break;
        }
      }

      log(`\n> clicando em "${button.label}"`);
      const before = fingerprint(snap);
      const next = await advance(page, snap.frame, button, before);

      if (!next) {
        const after = await snapshot(page);
        if (after.errors.length) {
          log(`[!] a pagina nao avancou. Validacao: ${after.errors.join(' | ')}`);
        } else {
          log('[!] a pagina nao avancou e nenhuma mensagem de erro foi encontrada.');
        }
        await page.screenshot({ path: join(outDir, `p${String(n).padStart(2, '0')}-bloqueado.png`), fullPage: true });
        log('    Corrija no navegador e rode de novo, ou use --step para acompanhar passo a passo.');
        break;
      }

      if (button.kind === 'submit') {
        submitted = true;
        log('\n[enviado] a pesquisa foi enviada.');
        await page.waitForTimeout(2000);
        await page.screenshot({ path: join(outDir, 'final.png'), fullPage: true });
        const done = await snapshot(page);
        log(`pagina final: ${done.heading || done.title}`);
        // Muitas pesquisas mostram um codigo de validacao no fim.
        const body = await page.evaluate(() => document.body.innerText).catch(() => '');
        const code = body.match(/\b[A-Z0-9]{4,8}[- ]?[A-Z0-9]{4,8}\b/);
        if (code) log(`possivel codigo na tela: ${code[0]}`);
        break;
      }

      if (n === MAX_PAGES) log(`\n[!] limite de ${MAX_PAGES} paginas atingido.`);
    }
  } finally {
    await writeFile(join(outDir, 'log.txt'), lines.join('\n'), 'utf8');
    await writeFile(join(outDir, 'summary.json'), JSON.stringify({ url, submitted, summary }, null, 2), 'utf8');
    log(`\nartefatos em ${outDir}/`);
    if (!args.headless && process.stdin.isTTY) {
      console.log('Feche a janela do navegador ou pressione Ctrl+C para encerrar.');
      await page.waitForTimeout(config.browser?.holdMs ?? 8000);
    }
    await browser.close();
  }
}

run().catch((err) => {
  console.error(`\nerro: ${err.message}`);
  process.exit(1);
});
